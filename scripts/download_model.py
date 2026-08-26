#!/usr/bin/env python3
"""
Model Download & Resumable Chunked Ingestion Script
---------------------------------------------------
Downloads and verifies large quantized GGUF language model weights (e.g. Qwen 3.8 27B)
from Hugging Face with multi-threaded chunking and resumable state tracking.
"""
from __future__ import annotations

import os
import sys
import time
import json
import signal
import urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
DEFAULT_HF_URL = os.getenv(
    "MODEL_HF_URL",
    "https://huggingface.co/Qwen/Qwen3.8-27B-GGUF/resolve/main/qwen3.8-27b-q6_k.gguf"
)
MODEL_HF_URL = DEFAULT_HF_URL
MODEL_NAME = os.getenv("OPENAI_MODEL", "qwen3.8-27b-q6_k.gguf")
if not MODEL_NAME.endswith(".gguf"):
    MODEL_NAME = f"{MODEL_NAME.replace(':', '-')}.gguf"

OUTPUT_PATH = os.path.join(MODELS_DIR, MODEL_NAME)
PROGRESS_PATH = os.path.join(MODELS_DIR, f"{MODEL_NAME}.progress")
NUM_WORKERS = 24
CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB chunks for finer-grained resumption

current_signed_url = None
url_lock = threading.Lock()
global_tracker = None

def get_fresh_url():
    global current_signed_url
    with url_lock:
        req = urllib.request.Request(MODEL_HF_URL, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            current_signed_url = resp.geturl()
            content_length = int(resp.headers.get("Content-Length", 0))
            return current_signed_url, content_length

def get_current_url():
    global current_signed_url
    if not current_signed_url:
        return get_fresh_url()[0]
    return current_signed_url

def save_progress(tracker):
    if not tracker:
        return
    try:
        temp_progress = PROGRESS_PATH + ".tmp"
        data = {
            "completed_chunks": list(tracker["completed_chunks"]),
            "total_chunks": tracker["total_chunks"],
            "total_size": tracker["total_size"],
            "chunk_size": CHUNK_SIZE
        }
        with open(temp_progress, "w") as f:
            json.dump(data, f)
        if os.path.exists(PROGRESS_PATH):
            os.remove(PROGRESS_PATH)
        os.rename(temp_progress, PROGRESS_PATH)
    except Exception:
        pass

def load_progress(total_chunks, total_size):
    if os.path.exists(PROGRESS_PATH):
        try:
            with open(PROGRESS_PATH, "r") as f:
                data = json.load(f)
                if data.get("total_size") == total_size and data.get("chunk_size") == CHUNK_SIZE:
                    return set(data.get("completed_chunks", []))
        except Exception:
            pass
    return set()

def download_chunk_with_retry(chunk_idx, start_byte, end_byte, file_path, file_lock, progress_tracker, progress_lock):
    max_retries = 15
    expected_len = end_byte - start_byte + 1
    
    for attempt in range(max_retries):
        try:
            url = get_current_url()
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Range": f"bytes={start_byte}-{end_byte}"
                }
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = resp.read()
                if len(data) != expected_len:
                    raise IOError(f"Incomplete chunk {chunk_idx}: got {len(data)}, expected {expected_len}")
                
                with file_lock:
                    with open(file_path, "r+b") as f:
                        f.seek(start_byte)
                        f.write(data)
                
                with progress_lock:
                    progress_tracker["completed_chunks"].add(chunk_idx)
                    progress_tracker["downloaded_bytes"] += len(data)
                    save_progress(progress_tracker)
                return True
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                get_fresh_url()
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
            
    raise RuntimeError(f"Failed to download chunk {chunk_idx} after {max_retries} attempts")

def signal_handler(sig, frame):
    global global_tracker
    print("\n[!] Process interrupted. Saving progress state...", flush=True)
    if global_tracker:
        save_progress(global_tracker)
    sys.exit(0)

def main():
    global global_tracker
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    print(f"Resolving model URL from Hugging Face...")
    fresh_url, total_size = get_fresh_url()
    gb_size = total_size / (1024 * 1024 * 1024)
    print(f"Target: {OUTPUT_PATH}")
    print(f"Total size: {gb_size:.2f} GB ({total_size:,} bytes)")
    
    # Pre-allocate file if needed
    if not os.path.exists(OUTPUT_PATH) or os.path.getsize(OUTPUT_PATH) != total_size:
        print("Pre-allocating target file...")
        with open(OUTPUT_PATH, "wb") as f:
            f.seek(total_size - 1)
            f.write(b"\0")
            
    ranges = []
    for start in range(0, total_size, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE - 1, total_size - 1)
        ranges.append((start, end))
        
    total_chunks = len(ranges)
    completed_set = load_progress(total_chunks, total_size)
    print(f"[*] Resuming download: {len(completed_set)}/{total_chunks} chunks already saved.")
    
    initial_downloaded = sum(ranges[idx][1] - ranges[idx][0] + 1 for idx in completed_set)
    progress_tracker = {
        "completed_chunks": completed_set,
        "downloaded_bytes": initial_downloaded,
        "total_chunks": total_chunks,
        "total_size": total_size
    }
    global_tracker = progress_tracker
    
    pending_indices = [i for i in range(total_chunks) if i not in completed_set]
    if not pending_indices:
        print("[*] All chunks already downloaded!")
    else:
        print(f"[*] Downloading remaining {len(pending_indices)} chunks across {NUM_WORKERS} threads...")
        file_lock = threading.Lock()
        progress_lock = threading.Lock()
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = {
                executor.submit(
                    download_chunk_with_retry,
                    idx, ranges[idx][0], ranges[idx][1],
                    OUTPUT_PATH, file_lock, progress_tracker, progress_lock
                ): idx
                for idx in pending_indices
            }
            
            last_reported = 0
            while True:
                done_count = sum(1 for f in futures if f.done())
                elapsed = time.time() - start_time
                with progress_lock:
                    downloaded = progress_tracker["downloaded_bytes"]
                speed_mb = ((downloaded - initial_downloaded) / (1024 * 1024)) / max(elapsed, 0.1)
                pct = (downloaded / total_size) * 100
                cur_gb = downloaded / (1024 * 1024 * 1024)
                
                if elapsed - last_reported >= 4 or done_count == len(futures):
                    total_done = len(progress_tracker["completed_chunks"])
                    print(f"[{pct:5.1f}%] {cur_gb:5.2f} / {gb_size:.2f} GB | Speed: {speed_mb:5.1f} MB/s | Chunks: {total_done}/{total_chunks}", flush=True)
                    last_reported = elapsed
                    
                if done_count == len(futures):
                    break
                time.sleep(2)
                
            for future in as_completed(futures):
                future.result()
                
    if os.path.exists(PROGRESS_PATH):
        os.remove(PROGRESS_PATH)
        
    final_gb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024 * 1024)
    print(f"\n[OK] Model successfully downloaded and verified!")
    print(f"Location: {OUTPUT_PATH} (Size: {final_gb:.2f} GB)")

if __name__ == "__main__":
    main()

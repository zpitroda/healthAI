#!/usr/bin/env python3
"""
llama.cpp CUDA Auto-Installer for Windows (RTX 5090 / CUDA Optimized)
-------------------------------------------------------------------
Downloads and extracts the latest official CUDA-accelerated llama.cpp binary release
directly into the local project folder (./llama.cpp/).
"""
from __future__ import annotations

import os
import sys
import json
import zipfile
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LLAMA_DIR = os.path.join(PROJECT_ROOT, "llama.cpp")

def get_latest_cuda_release_urls() -> tuple[str, str]:
    """Queries GitHub API for latest llama.cpp release asset URLs for win-cuda-12.4-x64."""
    api_url = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=5"
    req = urllib.request.Request(api_url, headers={"User-Agent": "HealthAI-Installer"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        releases = json.loads(resp.read().decode("utf-8"))

    bin_url = None
    cudart_url = None

    for rel in releases:
        assets = rel.get("assets", [])
        for a in assets:
            name = a.get("name", "")
            download_url = a.get("browser_download_url", "")
            if "cudart-llama-bin-win-cuda-12.4-x64.zip" in name:
                cudart_url = download_url
            elif "bin-win-cuda-12.4-x64.zip" in name and not name.startswith("cudart-"):
                bin_url = download_url
            elif "bin-win-cuda-cu12.4-x64.zip" in name:
                bin_url = download_url

        if cudart_url or bin_url:
            break

    # Fallback to direct latest known build if API rate-limited
    if not cudart_url and not bin_url:
        cudart_url = "https://github.com/ggml-org/llama.cpp/releases/download/b10644/cudart-llama-bin-win-cuda-12.4-x64.zip"
        bin_url = "https://github.com/ggml-org/llama.cpp/releases/download/b10644/llama-b10644-bin-win-cuda-12.4-x64.zip"

    return cudart_url or bin_url, bin_url


def download_and_extract(url: str, target_dir: str):
    os.makedirs(target_dir, exist_ok=True)
    filename = url.split("/")[-1]
    zip_path = os.path.join(target_dir, filename)

    print(f"[*] Downloading: {filename} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    with urllib.request.urlopen(req, timeout=60) as resp, open(zip_path, "wb") as out_f:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        last_pct = -1
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = int((downloaded / total) * 100)
                if pct != last_pct and pct % 10 == 0:
                    print(f"    [{pct:3d}%] {downloaded / (1024*1024):.1f} / {total / (1024*1024):.1f} MB", flush=True)
                    last_pct = pct

    print(f"[*] Extracting into {target_dir} ...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(target_dir)

    if os.path.exists(zip_path):
        os.remove(zip_path)


def main():
    print("=" * 60)
    print("  healthAI - llama.cpp CUDA Binary Setup (RTX 5090 / CUDA 12)")
    print("=" * 60)

    server_exe = os.path.join(LLAMA_DIR, "llama-server.exe")
    if os.path.exists(server_exe):
        print(f"[OK] llama-server.exe already installed at: {server_exe}")
        return 0

    print("[*] Finding latest CUDA-accelerated Windows binaries from ggml-org/llama.cpp...")
    try:
        cudart_url, bin_url = get_latest_cuda_release_urls()
        
        # 1. Download and extract main binary zip (contains llama-server.exe, llama-cli.exe, ggml.dll, llama.dll)
        if bin_url:
            print(f"[*] Downloading llama.cpp binaries: {bin_url}")
            download_and_extract(bin_url, LLAMA_DIR)
        
        # 2. Download and extract cudart zip (contains CUDA 12.4 cublas/cudart runtime DLLs)
        if cudart_url and cudart_url != bin_url:
            print(f"[*] Downloading CUDA runtime libraries: {cudart_url}")
            download_and_extract(cudart_url, LLAMA_DIR)

        if os.path.exists(server_exe):
            print(f"\n[OK] Successfully installed llama-server.exe and CUDA runtimes to: {LLAMA_DIR}")
            return 0
        else:
            # Check subdirectories if zip extracted into a nested folder
            for root, _, files in os.walk(LLAMA_DIR):
                if "llama-server.exe" in files:
                    # Move files up to LLAMA_DIR
                    for f in files:
                        src = os.path.join(root, f)
                        dst = os.path.join(LLAMA_DIR, f)
                        if not os.path.exists(dst):
                            os.rename(src, dst)
                    if os.path.exists(server_exe):
                        print(f"\n[OK] Successfully configured llama-server.exe at: {server_exe}")
                        return 0
            
            print("[!] Error: llama-server.exe was not found after extraction.")
            return 1
    except Exception as e:
        print(f"[!] Installation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

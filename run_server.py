"""
healthAI Server Launcher
-----------------------
Starts the FastAPI uvicorn development/production server with options for
custom port, host, reload mode, and automatic browser opening.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path
import uvicorn

BASE_DIR = Path(__file__).resolve().parent

def main() -> None:
    # Ensure stdout handles utf-8 if supported or replace problematic chars
    if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="healthAI Server Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host IP to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", dest="reload", action="store_true", default=True, help="Enable auto-reload on code changes (default: True)")
    parser.add_argument("--no-reload", dest="reload", action="store_false", help="Disable auto-reload")
    parser.add_argument("--open-browser", action="store_true", help="Automatically open the dashboard in your default browser")
    args = parser.parse_args()

    # Probe port availability and fallback if occupied
    import socket
    target_port = args.port
    for p in [target_port, 8001, 8002, 8088]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((args.host, p))
                target_port = p
                break
            except OSError:
                continue

    url = f"http://{args.host}:{target_port}"
    print("=" * 60)
    print("  [healthAI] Pharmacology Lab & Protocol Engine")
    print(f"  * Dashboard:        {url}")
    print(f"  * Admin Catalog:    {url}/admin")
    print(f"  * Knowledge Graph:  {url}/graph")
    print(f"  * API Docs:         {url}/docs")
    print(f"  * Health Status:    {url}/health")
    print("=" * 60)

    if args.open_browser:
        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=target_port,
        reload=args.reload,
        app_dir=str(BASE_DIR),
    )

if __name__ == "__main__":
    main()

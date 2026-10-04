#!/usr/bin/env python3
"""
Launch both HTTP (port 8000) and HTTPS (port 8443) servers for the AI Kitchen Assistant.
The HTTPS server enables mobile camera access which requires secure context.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CERT_DIR = PROJECT_ROOT / "certs"
HTTP_PORT = 8000
HTTPS_PORT = 8443

def main():
    cert_file = CERT_DIR / "localhost.pem"
    key_file = CERT_DIR / "localhost-key.pem"

    if not cert_file.exists() or not key_file.exists():
        print("Certificates not found. Run the cert generation script first.")
        sys.exit(1)

    # Change to project root
    os.chdir(PROJECT_ROOT)

    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

    # Launch HTTP server
    http_cmd = [
        str(venv_python), "-m", "uvicorn",
        "server.app:app",
        "--host", "0.0.0.0",
        "--port", str(HTTP_PORT),
        "--log-level", "info"
    ]

    # Launch HTTPS server
    https_cmd = [
        str(venv_python), "-m", "uvicorn",
        "server.app:app",
        "--host", "0.0.0.0",
        "--port", str(HTTPS_PORT),
        "--ssl-certfile", str(cert_file),
        "--ssl-keyfile", str(key_file),
        "--log-level", "info"
    ]

    print("Starting servers...")
    print(f"  HTTP  : http://0.0.0.0:{HTTP_PORT}")
    print(f"  HTTPS : https://0.0.0.0:{HTTPS_PORT}")
    print("Press Ctrl+C to stop both servers")

    http_proc = subprocess.Popen(http_cmd)
    https_proc = subprocess.Popen(https_cmd)

    def signal_handler(sig, frame):
        print("\nShutting down servers...")
        http_proc.terminate()
        https_proc.terminate()
        http_proc.wait(timeout=5)
        https_proc.wait(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)
            if http_proc.poll() is not None:
                print("HTTP server stopped unexpectedly")
                break
            if https_proc.poll() is not None:
                print("HTTPS server stopped unexpectedly")
                break
    except KeyboardInterrupt:
        pass
    finally:
        http_proc.terminate()
        https_proc.terminate()


if __name__ == "__main__":
    main()
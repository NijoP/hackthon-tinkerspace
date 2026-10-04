#!/usr/bin/env python3
"""Create a local CA and an HTTPS certificate for this laptop's LAN IP.

Phones only allow camera access (getUserMedia) on secure origins, so the phone page
and the dashboard are served over HTTPS on :8443. This script uses the `openssl`
CLI (ships with Git for Windows) and writes everything to certs/ (git-ignored).

  python scripts/make_certs.py            # auto-detect LAN IP
  python scripts/make_certs.py 10.0.0.12  # explicit IP

Afterwards, optionally install certs/laptop-ca.crt on the phone as a trusted CA,
or simply accept the browser warning once on each device.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERTS = ROOT / "certs"


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def run(*args: str) -> None:
    subprocess.run(["openssl", *args], check=True, cwd=CERTS, stdout=subprocess.DEVNULL)


def main() -> None:
    if not shutil.which("openssl"):
        raise SystemExit("openssl not found. Install Git for Windows or OpenSSL and retry.")
    ip = sys.argv[1] if len(sys.argv) > 1 else lan_ip()
    CERTS.mkdir(exist_ok=True)
    (CERTS / "openssl-san.cnf").write_text(
        "[req]\ndistinguished_name = dn\nreq_extensions = v3\nprompt = no\n"
        f"[dn]\nCN = {ip}\n"
        f"[v3]\nsubjectAltName = IP:{ip},IP:127.0.0.1,DNS:localhost\n"
        "basicConstraints = CA:FALSE\nkeyUsage = digitalSignature, keyEncipherment\n"
        "extendedKeyUsage = serverAuth\n",
        encoding="utf-8",
    )
    if not (CERTS / "laptop-ca.key").exists():
        run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "825",
            "-keyout", "laptop-ca.key", "-out", "laptop-ca.crt", "-subj", "/CN=Kitchen Memory Local CA")
    run("req", "-newkey", "rsa:2048", "-nodes", "-keyout", "localhost-key.pem",
        "-out", "server.csr", "-config", "openssl-san.cnf")
    run("x509", "-req", "-in", "server.csr", "-CA", "laptop-ca.crt", "-CAkey", "laptop-ca.key",
        "-CAcreateserial", "-out", "localhost.pem", "-days", "825",
        "-extfile", "openssl-san.cnf", "-extensions", "v3")
    print(f"Certificate for {ip} written to {CERTS}")


if __name__ == "__main__":
    main()

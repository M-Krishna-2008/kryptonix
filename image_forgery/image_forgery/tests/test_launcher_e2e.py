"""
Test launcher port fallback, status reporting, and health endpoint response.
"""

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent


def test_launcher():
    print("=== Testing launch.py Port Fallback & Server Execution ===", flush=True)

    # 1. Occupy port 8000 with a dummy socket to test fallback
    dummy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    dummy_sock.bind(("127.0.0.1", 8000))
    dummy_sock.listen(1)
    print("-> Successfully occupied port 8000 with dummy socket listener.", flush=True)

    # 2. Spawn launch.py asking for port 8000
    py_exe = sys.executable
    cmd = [
        py_exe,
        "-u",
        str(MODULE_ROOT / "launch.py"),
        "--no-browser",
        "--port", "8000"
    ]

    print("-> Starting launch.py (should detect port 8000 busy and fallback to 8001)...", flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)

    try:
        # Wait for fallback port 8001 to respond
        ready = False
        health_data = None
        for _ in range(25):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:8001/api/image_forgery/health", timeout=1.0) as resp:
                    if resp.status == 200:
                        health_data = json.loads(resp.read().decode())
                        ready = True
                        break
            except Exception:
                continue

        if not ready:
            err = proc.stderr.read() if proc.stderr else ""
            out = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"Server on port 8001 did not respond! stderr: {err}, stdout: {out}")

        print(f"-> Fallback port 8001 responded successfully: {health_data}", flush=True)
        assert health_data["status"] == "ok"
        assert health_data["module"] == "image_forgery"

        # Check engines status endpoint on port 8001
        with urllib.request.urlopen("http://127.0.0.1:8001/api/image_forgery/engines", timeout=1.0) as resp:
            eng_data = json.loads(resp.read().decode())
            print(f"-> Engines status verified: {list(eng_data.keys())}", flush=True)
            assert "trufor" in eng_data
            assert "metadata" in eng_data

        # Check root UI index
        with urllib.request.urlopen("http://127.0.0.1:8001/", timeout=1.0) as resp:
            content = resp.read().decode()
            assert "image-forgery-root" in content
            print("-> Root UI HTML verified on port 8001!", flush=True)

        print("\n=======================================================", flush=True)
        print("LAUNCHER PORT FALLBACK & HEALTH TESTS PASSED!", flush=True)
        print("=======================================================", flush=True)

    finally:
        print("-> Cleaning up test processes...", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        dummy_sock.close()
        print("-> Done.", flush=True)


if __name__ == "__main__":
    test_launcher()

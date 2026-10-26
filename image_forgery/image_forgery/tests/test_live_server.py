"""
Live server end-to-end integration test with real HTTP socket requests.
Spawns uvicorn on localhost, exercises all contractual endpoints with real uploads,
verifies JSON schemas and responses, and cleanly shuts down.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path
import urllib.error
import urllib.request
import uvicorn

MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from main_standalone import app

PORT = 8089
BASE_URL = f"http://127.0.0.1:{PORT}"


def main():
    import asyncio
    print(f"Starting standalone uvicorn server on port {PORT} in background thread...", flush=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    server_thread = threading.Thread(target=run_loop, daemon=True)
    server_thread.start()

    try:
        # Wait for server to come up
        ready = False
        for _ in range(25):
            time.sleep(0.3)
            try:
                with urllib.request.urlopen(f"{BASE_URL}/api/image_forgery/health", timeout=1) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                continue

        if not ready:
            raise RuntimeError("Server failed to respond to /health within timeout")

        print("-> Server online!", flush=True)

        # 1. Health check
        print("\n1. Testing GET /api/image_forgery/health...")
        with urllib.request.urlopen(f"{BASE_URL}/api/image_forgery/health") as resp:
            data = json.loads(resp.read().decode())
            print(f"   [200 OK] Response: {data}")
            assert data["status"] == "ok"
            assert data["module"] == "image_forgery"

        # 2. Engines check
        print("\n2. Testing GET /api/image_forgery/engines...")
        with urllib.request.urlopen(f"{BASE_URL}/api/image_forgery/engines") as resp:
            data = json.loads(resp.read().decode())
            print(f"   [200 OK] Engines found: {list(data.keys())}")
            assert "trufor" in data and "metadata" in data and "ela" in data

        # 3. Static UI check
        print("\n3. Testing GET / (Static UI Index)...")
        with urllib.request.urlopen(f"{BASE_URL}/") as resp:
            html = resp.read().decode()
            print(f"   [200 OK] Received {len(html)} characters. Contains root container: {'image-forgery-root' in html}")
            assert "image-forgery-root" in html

        # 4. Analyze endpoint with real multipart upload
        print("\n4. Testing POST /api/image_forgery/analyze (Multipart file upload)...")
        sample_path = MODULE_ROOT / "tests" / "samples" / "spliced.jpg"
        with open(sample_path, "rb") as f:
            file_bytes = f.read()

        boundary = "----ForensicTestBoundary7MA4YWxkTrZu0gW"
        body = bytearray()
        # Form field: file
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="file"; filename="{sample_path.name}"\r\n'.encode())
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(file_bytes)
        body.extend(b"\r\n")
        # Form field: options
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="options"\r\n\r\n')
        body.extend(b'{"engines": ["trufor", "metadata", "ela"], "max_side": 512, "use_cuda": false}\r\n')
        body.extend(f"--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            f"{BASE_URL}/api/image_forgery/analyze",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST"
        )

        with urllib.request.urlopen(req) as resp:
            res_json = json.loads(resp.read().decode())
            print(f"   [200 OK] Analysis verdict: {res_json['verdict']}, Confidence: {res_json['overall_confidence']}")
            print(f"   Findings count: {len(res_json['findings'])}, Artifacts dir: {res_json['artifacts_dir']}")
            assert res_json["module"] == "image_forgery"
            assert res_json["verdict"] in ("authentic", "suspicious", "likely_tampered", "inconclusive")
            assert len(res_json["findings"]) > 0

        # 5. Artifacts endpoint
        print("\n5. Testing GET /api/image_forgery/artifacts/{filename}...")
        sha_dir = res_json["evidence_file"]["sha256"][:12]
        for art_name in ["annotated.png", "trufor_overlay.png", "trufor_map.png", "trufor_confidence.png", "ela.png"]:
            art_url = f"{BASE_URL}/api/image_forgery/artifacts/{sha_dir}/{art_name}"
            with urllib.request.urlopen(art_url) as resp:
                content_type = resp.headers.get("Content-Type")
                art_bytes = resp.read()
                print(f"   [200 OK] Fetched {art_name} ({len(art_bytes)} bytes). Content-Type: {content_type}")
                assert content_type == "image/png"
                assert len(art_bytes) > 0

        # 6. Path Traversal Security check
        print("\n6. Testing Path Traversal Attack Rejection...")
        traversal_url = f"{BASE_URL}/api/image_forgery/artifacts/../../main_standalone.py"
        try:
            with urllib.request.urlopen(traversal_url) as resp:
                raise AssertionError("Path traversal succeeded unexpectedly!")
        except urllib.error.HTTPError as e:
            print(f"   [BLOCKED] Server correctly rejected path traversal attempt with HTTP {e.code}")
            assert e.code in (403, 404)

        print("\n=======================================================")
        print("ALL LIVE END-TO-END HTTP TESTS PASSED PERFECTLY!")
        print("=======================================================")

    finally:
        print("Shutting down uvicorn server thread...", flush=True)
        server.should_exit = True
        server_thread.join(timeout=3)
        print("Server stopped cleanly.", flush=True)


if __name__ == "__main__":
    main()

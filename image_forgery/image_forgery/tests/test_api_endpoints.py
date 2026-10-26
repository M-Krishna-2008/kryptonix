"""
API End-to-end integration tests using httpx.AsyncClient with ASGITransport.
Tests all contractual endpoints, uploads, artifacts, and path traversal protection.
"""

import asyncio
import sys
from pathlib import Path
import httpx

# Add module parent to sys.path
MODULE_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = MODULE_ROOT.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from image_forgery.main_standalone import app


async def run_tests_async():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("1. Testing GET /api/image_forgery/health...", flush=True)
        resp = await client.get("/api/image_forgery/health")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        data = resp.json()
        assert data["status"] == "ok" and data["module"] == "image_forgery"
        print(f"   -> Health check PASSED: {data}", flush=True)

        print("2. Testing GET /api/image_forgery/engines...", flush=True)
        resp = await client.get("/api/image_forgery/engines")
        assert resp.status_code == 200, f"Engines endpoint failed: {resp.status_code}"
        engines = resp.json()
        assert "trufor" in engines and "ela" in engines and "metadata" in engines
        print(f"   -> Engines endpoint PASSED: {list(engines.keys())}", flush=True)

        print("3. Testing POST /api/image_forgery/analyze (multipart upload)...", flush=True)
        sample_file = MODULE_ROOT / "tests" / "samples" / "spliced.jpg"
        with open(sample_file, "rb") as f:
            file_bytes = f.read()

        resp = await client.post(
            "/api/image_forgery/analyze",
            files={"file": ("spliced.jpg", file_bytes, "image/jpeg")},
            data={"options": '{"engines": ["metadata", "ela"]}'}
        )
        assert resp.status_code == 200, f"Analyze upload failed: {resp.status_code} {resp.text}"
        result = resp.json()
        assert result["module"] == "image_forgery"
        assert "verdict" in result
        assert "overall_confidence" in result
        assert "findings" in result
        print(f"   -> Analyze PASSED: Verdict={result['verdict']}, Confidence={result['overall_confidence']}, Findings={len(result['findings'])}", flush=True)

        print("4. Testing GET /api/image_forgery/artifacts/{filename}...", flush=True)
        sha_dir = result["evidence_file"]["sha256"][:12]
        art_resp = await client.get(f"/api/image_forgery/artifacts/{sha_dir}/annotated.png")
        assert art_resp.status_code == 200, f"Artifact fetch failed: {art_resp.status_code}"
        assert len(art_resp.content) > 0
        assert art_resp.headers["content-type"] == "image/png"
        print(f"   -> Artifact fetch PASSED: received {len(art_resp.content)} bytes of image/png", flush=True)

        print("5. Testing Path Traversal Protection...", flush=True)
        trav_resp = await client.get("/api/image_forgery/artifacts/../../main_standalone.py")
        assert trav_resp.status_code in (403, 404), f"Path traversal not blocked! Status: {trav_resp.status_code}"
        print(f"   -> Path Traversal Security check PASSED (Blocked with status {trav_resp.status_code})", flush=True)

        print("6. Testing GET / (Root serving index.html)...", flush=True)
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "image-forgery-root" in root_resp.text
        print("   -> Root static UI serve PASSED", flush=True)

    print("\n==========================================", flush=True)
    print("ALL API END-TO-END TESTS PASSED!", flush=True)
    print("==========================================", flush=True)


if __name__ == "__main__":
    asyncio.run(run_tests_async())

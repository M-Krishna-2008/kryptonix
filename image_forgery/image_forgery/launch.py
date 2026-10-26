"""
Launcher for Image Forgery Detection Module.
Pure Python orchestrator: checks status, selects port, creates directories,
starts standalone server, opens browser, and handles graceful shutdown.
"""

import argparse
import hashlib
import os
import socket
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("PORT", 8000))

TRUFOR_WEIGHTS_PATH = MODULE_ROOT / "models" / "trufor" / "trufor.pth.tar"
TRUFOR_EXPECTED_SIZE = 281496429
TRUFOR_EXPECTED_SHA256 = "ac1d90e329a72e0d66e8665e123a19e94bfae3209c3ef8a4f9ca3b91578c7844"
TRUFOR_MIRROR_URLS = [
    "https://huggingface.co/spaces/FraudDetection/trufor-splicing-detecto/resolve/main/TruFor_train_test/pretrained_models/trufor.pth.tar",
    "https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip"
]


def verify_weights(model_path: Path = TRUFOR_WEIGHTS_PATH) -> bool:
    """Verify presence, file size, and SHA-256 checksum of model weights."""
    if not model_path.exists():
        return False
    if model_path.stat().st_size != TRUFOR_EXPECTED_SIZE:
        return False
    h = hashlib.sha256()
    with open(model_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest().lower() == TRUFOR_EXPECTED_SHA256.lower()


def download_weights(model_path: Path = TRUFOR_WEIGHTS_PATH, max_retries: int = 3) -> bool:
    """Download TruFor weights with resume support, progress reporting, and hash check."""
    if verify_weights(model_path):
        print(f"  [OK] Model weights already verified at {model_path}", flush=True)
        return True

    model_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = model_path.with_suffix(".part")

    print(f"  Downloading TruFor pretrained weights ({TRUFOR_EXPECTED_SIZE / (1024*1024):.1f} MB)...", flush=True)

    for attempt in range(1, max_retries + 1):
        for url in TRUFOR_MIRROR_URLS:
            if not url.endswith(".tar"):
                continue
            print(f"  Attempt {attempt}/{max_retries} via {url[:60]}...", flush=True)
            try:
                existing_size = part_path.stat().st_size if part_path.exists() else 0
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                if 0 < existing_size < TRUFOR_EXPECTED_SIZE:
                    req.add_header("Range", f"bytes={existing_size}-")
                    mode = "ab"
                else:
                    mode = "wb"
                    existing_size = 0

                with urllib.request.urlopen(req, timeout=30) as resp:
                    status = resp.status
                    if status == 200:
                        mode = "wb"
                        existing_size = 0
                        downloaded = 0
                    else:
                        downloaded = existing_size

                    total_size = TRUFOR_EXPECTED_SIZE
                    t_last_print = time.time()

                    with open(part_path, mode) as f:
                        while True:
                            chunk = resp.read(512 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)

                            now = time.time()
                            if now - t_last_print >= 1.0 or downloaded >= total_size:
                                pct = min(100.0, (downloaded / total_size) * 100)
                                mb_down = downloaded / (1024 * 1024)
                                mb_tot = total_size / (1024 * 1024)
                                sys.stdout.write(f"\r  Progress: [{pct:5.1f}%] {mb_down:6.1f} / {mb_tot:.1f} MB")
                                sys.stdout.flush()
                                t_last_print = now

                    print()  # newline after progress

                # Verify downloaded part
                if part_path.stat().st_size == TRUFOR_EXPECTED_SIZE:
                    h = hashlib.sha256()
                    with open(part_path, "rb") as f:
                        while c := f.read(1024 * 1024):
                            h.update(c)
                    if h.hexdigest().lower() == TRUFOR_EXPECTED_SHA256.lower():
                        if model_path.exists():
                            model_path.unlink()
                        part_path.rename(model_path)
                        print("  [SUCCESS] TruFor model weights verified and installed.")
                        return True
                    else:
                        print(f"  [ERROR] SHA-256 hash mismatch! Got {h.hexdigest()}, expected {TRUFOR_EXPECTED_SHA256}")
                        part_path.unlink(missing_ok=True)
            except Exception as err:
                print(f"\n  [WARN] Download error: {err}")
                time.sleep(2)

    print("\n" + "=" * 65)
    print("  ERROR: Automatic model weight download could not be completed.")
    print("  Please download the file manually and place it at:")
    print(f"    {model_path}")
    print("  Source URLs:")
    for u in TRUFOR_MIRROR_URLS:
        print(f"    - {u}")
    print(f"  Required Size:    {TRUFOR_EXPECTED_SIZE} bytes")
    print(f"  Expected SHA-256: {TRUFOR_EXPECTED_SHA256}")
    print("=" * 65 + "\n")
    return False


def print_status_table():
    """Print system status, PyTorch hardware accelerator, and engine readiness."""
    print("\n" + "=" * 65, flush=True)
    print("      PS-05 Image Forgery Forensic Platform Status", flush=True)
    print("=" * 65, flush=True)
    print(f"  Python Version:     {sys.version.split()[0]}", flush=True)

    # Check PyTorch & CUDA
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "None (CPU Mode)"
        print(f"  PyTorch Version:    {torch.__version__}", flush=True)
        print(f"  CUDA Available:     {cuda_ok} ({gpu_name})", flush=True)
    except ImportError:
        print("  PyTorch Version:    Not installed (classical forensics mode)", flush=True)
        print("  CUDA Available:     False", flush=True)

    print("-" * 65, flush=True)
    print("  Engine Readiness:", flush=True)

    # TruFor check
    if verify_weights(TRUFOR_WEIGHTS_PATH):
        print("  [READY]     TruFor: Weights verified at models/trufor/trufor.pth.tar", flush=True)
    else:
        print("  [AVAILABLE] TruFor: NOT FOUND - place file at models/trufor/trufor.pth.tar", flush=True)

    # Classical checks
    print("  [READY]     Metadata & EXIF Forensics (Pillow + piexif)", flush=True)
    print("  [READY]     JPEG Quantization Table Analysis", flush=True)
    print("  [READY]     Error Level Analysis (ELA)", flush=True)
    print("  [READY]     Copy-Move Keypoint Matching (OpenCV SIFT/ORB)", flush=True)
    print("=" * 65 + "\n", flush=True)


def is_port_in_use(host: str, port: int) -> bool:
    """Check if TCP port is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_available_port(host: str, start_port: int, max_attempts: int = 20) -> int:
    """Find available port starting from start_port up to start_port + max_attempts."""
    for p in range(start_port, start_port + max_attempts + 1):
        if not is_port_in_use(host, p):
            return p
    return start_port


def wait_for_server(url: str, timeout: float = 15.0) -> bool:
    """Poll health endpoint until server responds or timeout occurs."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def main():
    parser = argparse.ArgumentParser(description="Image Forgery Forensic Launcher")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--dry-run", action="store_true", help="Audit system readiness and exit")
    parser.add_argument("--check-weights", action="store_true", help="Verify presence and checksum of model weights")
    parser.add_argument("--download-weights", action="store_true", help="Download model weights if missing and exit")
    args = parser.parse_args()

    if args.check_weights:
        ok = verify_weights(TRUFOR_WEIGHTS_PATH)
        if ok:
            print("Model weights verified successfully.")
            sys.exit(0)
        else:
            print("Model weights missing or checksum mismatch.")
            sys.exit(1)

    if args.download_weights:
        ok = download_weights(TRUFOR_WEIGHTS_PATH)
        sys.exit(0 if ok else 1)

    # 1. Print status table
    print_status_table()

    if args.dry_run:
        # Check system readiness
        weights_ok = verify_weights(TRUFOR_WEIGHTS_PATH)
        try:
            import torch
            import cv2
            import PIL
            import uvicorn
            import fastapi
            deps_ok = True
        except ImportError as e:
            print(f"[FAIL] Missing dependency during dry run: {e}")
            deps_ok = False

        if weights_ok and deps_ok:
            print("[DRY-RUN] System audit PASSED: All requirements satisfied.")
            sys.exit(0)
        else:
            print("[DRY-RUN] System audit FAILED: Missing weights or dependencies.")
            sys.exit(1)

    # 2. Ensure weights are present (auto-download if missing)
    if not verify_weights(TRUFOR_WEIGHTS_PATH):
        print("TruFor model weights missing. Attempting automated download...")
        download_weights(TRUFOR_WEIGHTS_PATH)

    # 3. Ensure evidence upload and artifact directories exist
    upload_dir = Path(os.environ.get("UPLOAD_DIR", str(MODULE_ROOT / "uploads")))
    artifact_dir = Path(os.environ.get("ARTIFACT_DIR", str(MODULE_ROOT / "artifacts" / "image_forgery")))
    upload_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # 4. Find open port
    target_port = find_available_port(args.host, args.port)
    if target_port != args.port:
        print(f"Notice: Port {args.port} was busy. Automatically switched to port {target_port}.")

    # 5. Import uvicorn & main app
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn is not installed in the environment.")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    # Add MODULE_ROOT to sys.path so standalone imports work seamlessly
    if str(MODULE_ROOT) not in sys.path:
        sys.path.insert(0, str(MODULE_ROOT))

    server_url = f"http://{args.host}:{target_port}"
    health_url = f"{server_url}/api/image_forgery/health"
    docs_url = f"{server_url}/docs"

    try:
        from main_standalone import app
    except ImportError:
        from image_forgery.main_standalone import app

    config = uvicorn.Config(
        app,
        host=args.host,
        port=target_port,
        log_level="info"
    )
    server = uvicorn.Server(config)

    banner = f"""
=================================================================
  PS-05 Image Forgery Forensic Platform is running!
  Web UI:      {server_url}
  Health:      {health_url}
  API docs:    {docs_url}
  Press Ctrl+C in this window to stop the server
=================================================================
"""
    print(banner, flush=True)

    # Spawn thread to open browser when ready
    if not args.no_browser:
        import threading
        def open_when_ready():
            if wait_for_server(health_url):
                print(f"-> Server online! Opening browser at {server_url}...", flush=True)
                webbrowser.open(server_url)

        t = threading.Thread(target=open_when_ready, daemon=True)
        t.start()

    # Run server
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nServer stopped with error: {e}")


if __name__ == "__main__":
    main()

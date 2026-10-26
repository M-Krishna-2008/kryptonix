"""
Adapter for the TruFor forensic engine.
Handles availability check, image applicability, and subprocess orchestration.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from .base import BaseEngine, EngineOutput
from .config import MODULE_ROOT, SUBPROCESS_TIMEOUT_SEC, TRUFOR_HIGH_SCORE_THRESHOLD, TRUFOR_LOW_SCORE_THRESHOLD


class TruForEngine(BaseEngine):
    name: str = "trufor"

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = models_dir or (MODULE_ROOT / "models" / "trufor")
        self.weights_path = self.models_dir / "trufor.pth.tar"
        self.manifest_path = MODULE_ROOT / "models" / "MANIFEST.json"

    def check_available(self) -> Tuple[bool, str]:
        """Verify weights exist and match manifest checksum if manifest present."""
        if not self.weights_path.exists():
            return False, f"Weights file missing: {self.weights_path}. Place trufor.pth.tar in models/trufor/."

        # Check sha256 if manifest exists
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                expected_sha = manifest.get("trufor", {}).get("sha256")
                if expected_sha:
                    h = hashlib.sha256()
                    with open(self.weights_path, "rb") as wf:
                        while chunk := wf.read(65536):
                            h.update(chunk)
                    computed_sha = h.hexdigest().lower()
                    if computed_sha != expected_sha.lower():
                        return False, f"TruFor weights SHA-256 mismatch (expected {expected_sha}, got {computed_sha})"
            except Exception as e:
                return False, f"Error validating weights manifest: {str(e)}"

        return True, "Weights verified and available"

    def applicable(self, image_info: Dict[str, Any]) -> Tuple[bool, str]:
        """TruFor operates on all RGB still image formats."""
        fmt = image_info.get("format")
        if fmt in ("JPEG", "PNG", "TIFF", "WEBP", "BMP"):
            return True, f"Applicable to format {fmt}"
        return False, f"Format {fmt} not supported by TruFor"

    def run(self, image_path: Path, work_dir: Path, opts: Dict[str, Any]) -> EngineOutput:
        """
        Run TruFor in an isolated subprocess.
        Handles timeout and OOM retry with reduced max_side or CPU.
        """
        python_exe = os.environ.get("ENGINE_PYTHON_TRUFOR", sys.executable)
        runner_script = MODULE_ROOT / "engines" / "run_trufor.py"
        out_npz = work_dir / "trufor_out.npz"

        max_side = opts.get("max_side", 1024)
        device = "cuda" if opts.get("use_cuda", True) else "cpu"

        # Attempt execution with fallback on CUDA OOM
        attempts = [(device, max_side), (device, 512), ("cpu", 512)]
        last_error = ""

        t0 = time.time()
        for dev, side in attempts:
            cmd = [
                python_exe,
                str(runner_script),
                "--input", str(image_path),
                "--output-npz", str(out_npz),
                "--weights", str(self.weights_path),
                "--device", dev,
                "--max-side", str(side)
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=SUBPROCESS_TIMEOUT_SEC
                )
                if proc.returncode == 0 and out_npz.exists():
                    runtime = time.time() - t0
                    return self._process_output(out_npz, image_path, work_dir, dev, side, runtime)
                else:
                    err_msg = proc.stderr.strip() or proc.stdout.strip()
                    last_error = err_msg
                    if "out of memory" in err_msg.lower() or "cuda oom" in err_msg.lower():
                        continue  # retry with lower side or CPU
                    else:
                        break  # Non-OOM error, stop retrying
            except subprocess.TimeoutExpired:
                last_error = f"TruFor inference timed out after {SUBPROCESS_TIMEOUT_SEC} seconds"
                break
            except Exception as e:
                last_error = str(e)
                break

        # If failed, return empty output with error in extras
        runtime = time.time() - t0
        with Image.open(image_path) as im:
            orig_w, orig_h = im.size

        return EngineOutput(
            anomaly_map=np.zeros((orig_h, orig_w), dtype=np.float32),
            global_score=None,
            score_is_native=True,
            extras={"error": last_error},
            runtime_sec=runtime,
            device="none",
            scale_factor=1.0
        )

    def _process_output(
        self,
        npz_path: Path,
        image_path: Path,
        work_dir: Path,
        device: str,
        max_side: int,
        runtime: float
    ) -> EngineOutput:
        """Parse .npz, generate artifacts, resize maps to original dimensions."""
        data = np.load(npz_path)
        raw_map = data.get("map")
        raw_conf = data.get("conf")
        score = float(data["score"]) if "score" in data else None

        with Image.open(image_path) as im:
            orig_w, orig_h = im.size

        # Scale factor
        orig_max = max(orig_w, orig_h)
        scale_factor = float(max_side / orig_max) if orig_max > max_side else 1.0

        # Resize anomaly map to original dimensions
        if raw_map.shape[:2] != (orig_h, orig_w):
            anomaly_map = cv2.resize(raw_map, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        else:
            anomaly_map = raw_map.astype(np.float32)

        anomaly_map = np.clip(anomaly_map, 0.0, 1.0).astype(np.float32)

        # Confidence map
        confidence_map = None
        if raw_conf is not None:
            if raw_conf.shape[:2] != (orig_h, orig_w):
                confidence_map = cv2.resize(raw_conf, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            else:
                confidence_map = raw_conf.astype(np.float32)
            confidence_map = np.clip(confidence_map, 0.0, 1.0).astype(np.float32)

            # Save confidence artifact
            conf_vis = (confidence_map * 255).astype(np.uint8)
            conf_color = cv2.applyColorMap(conf_vis, cv2.COLORMAP_VIRIDIS)
            cv2.imwrite(str(work_dir / "trufor_confidence.png"), conf_color)

        # Save heatmap
        map_vis = (anomaly_map * 255).astype(np.uint8)
        map_color = cv2.applyColorMap(map_vis, cv2.COLORMAP_JET)
        cv2.imwrite(str(work_dir / "trufor_map.png"), map_color)

        # Save overlay onto original image
        orig_bgr = cv2.imread(str(image_path))
        if orig_bgr is not None:
            overlay = cv2.addWeighted(orig_bgr, 0.6, map_color, 0.4, 0)
            cv2.imwrite(str(work_dir / "trufor_overlay.png"), overlay)

        return EngineOutput(
            anomaly_map=anomaly_map,
            global_score=score,
            score_is_native=True,
            confidence_map=confidence_map,
            extras={"score": score},
            runtime_sec=runtime,
            device=device,
            scale_factor=scale_factor
        )

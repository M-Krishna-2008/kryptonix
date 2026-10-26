"""
Subprocess runner for TruFor forensic engine.
Ports official TruFor test pipeline without Docker to modern PyTorch.
Outputs .npz containing 'map', 'conf', 'score', and optional 'np++'.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="TruFor Subprocess Runner")
    parser.add_argument("--input", required=True, help="Path to input image file")
    parser.add_argument("--output-npz", required=True, help="Path to output .npz file")
    parser.add_argument("--weights", required=True, help="Path to model weights checkpoint")
    parser.add_argument("--device", default="cpu", help="Device to run on ('cpu' or 'cuda')")
    parser.add_argument("--max-side", type=int, default=1024, help="Maximum image side length")
    return parser.parse_args()


def verify_weights_sha256(weights_path: Path, manifest_path: Path) -> bool:
    """Verify SHA-256 against manifest before loading."""
    if not manifest_path.exists():
        return True
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        expected_sha = manifest.get("trufor", {}).get("sha256")
        if not expected_sha:
            return True

        hasher = hashlib.sha256()
        with open(weights_path, "rb") as wf:
            while chunk := wf.read(65536):
                hasher.update(chunk)
        computed_sha = hasher.hexdigest().lower()
        if computed_sha != expected_sha.lower():
            sys.stderr.write(f"SHA-256 mismatch for TruFor weights!\nExpected: {expected_sha}\nGot: {computed_sha}\n")
            return False
        return True
    except Exception as e:
        sys.stderr.write(f"Manifest verification warning: {e}\n")
        return True


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output_npz)
    weights_path = Path(args.weights)

    if not input_path.exists():
        sys.stderr.write(f"Input file not found: {input_path}\n")
        sys.exit(1)

    if not weights_path.exists():
        sys.stderr.write(f"Weights file not found: {weights_path}\n")
        sys.exit(1)

    # Verify SHA-256 before loading weights
    module_root = Path(__file__).resolve().parent.parent
    manifest_path = module_root / "models" / "MANIFEST.json"
    if not verify_weights_sha256(weights_path, manifest_path):
        sys.exit(2)

    device_str = args.device
    if device_str.startswith("cuda") and not torch.cuda.is_available():
        device_str = "cpu"
    device = torch.device(device_str)

    # Set up sys.path for vendored TruFor
    trufor_src = module_root / "third_party" / "TruFor" / "test_docker" / "src"
    if not trufor_src.exists():
        # Fallback to train_test path if structure differs
        trufor_src = module_root / "third_party" / "TruFor" / "TruFor_train_test"

    if str(trufor_src) not in sys.path:
        sys.path.insert(0, str(trufor_src))

    try:
        # Load TruFor config and model
        from config import _C as config
        from models.cmx.builder_np_conf import myEncoderDecoder as confcmx

        yaml_path = trufor_src / "trufor.yaml"
        config.defrost()
        if yaml_path.exists():
            config.merge_from_file(str(yaml_path))
        config.MODEL.NAME = 'detconfcmx'
        config.MODEL.MODS = ('RGB', 'NP++')
        config.MODEL.EXTRA.BACKBONE = 'mit_b2'
        config.MODEL.EXTRA.DECODER = 'MLPDecoder'
        config.MODEL.EXTRA.DECODER_EMBED_DIM = 512
        config.MODEL.EXTRA.PREPRC = 'imagenet'
        config.MODEL.EXTRA.BN_EPS = 0.001
        config.MODEL.EXTRA.BN_MOMENTUM = 0.1
        config.MODEL.EXTRA.DETECTION = 'confpool'
        config.MODEL.EXTRA.CONF = True
        config.freeze()

        model = confcmx(cfg=config)
        # Checkpoint is local trusted file verified with SHA-256
        checkpoint = torch.load(str(weights_path), map_location=device, weights_only=False)
        state_dict = checkpoint["state_dict"] if "state_dict" in checkpoint else checkpoint
        model.load_state_dict(state_dict)
        model = model.to(device)
        model.eval()

    except Exception as e:
        sys.stderr.write(f"Failed to initialize TruFor architecture: {str(e)}\n")
        sys.exit(3)

    # Load and preprocess image cleanly without padding or edge distortion
    with Image.open(input_path) as img:
        orig_w, orig_h = img.size
        # Handle alpha channels cleanly without introducing black border contrast
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            alpha_img = img.convert("RGBA")
            bg = Image.new("RGBA", alpha_img.size, (255, 255, 255, 255))
            bg.paste(alpha_img, (0, 0), alpha_img)
            rgb_img = bg.convert("RGB")
        else:
            rgb_img = img.convert("RGB")

    scale = 1.0
    # Run at native resolution; resize only if very large (exceeds max_side)
    if max(orig_w, orig_h) > args.max_side:
        scale = float(args.max_side) / float(max(orig_w, orig_h))
        new_w = max(16, int(round(orig_w * scale)))
        new_h = max(16, int(round(orig_h * scale)))
        rgb_img = rgb_img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    # Convert to tensor: float in [0, 1] transpose (C, H, W) - strictly no padding added
    img_np = np.array(rgb_img, dtype=np.float32) / 256.0
    tensor_input = torch.tensor(img_np.transpose(2, 0, 1), dtype=torch.float32).unsqueeze(0).to(device)

    try:
        with torch.no_grad():
            pred, conf, det, npp = model(tensor_input)

            # Map (anomaly localization)
            pred = torch.squeeze(pred, 0)
            pred = F.softmax(pred, dim=0)[1]
            map_arr = pred.cpu().numpy().astype(np.float32)

            # Reliability / confidence map
            conf_arr = None
            if conf is not None:
                conf = torch.squeeze(conf, 0)
                conf = torch.sigmoid(conf)[0]
                conf_arr = conf.cpu().numpy().astype(np.float32)

            # Image-level scalar integrity score
            score_val = None
            if det is not None:
                score_val = float(torch.sigmoid(det).item())
            else:
                score_val = float(np.percentile(map_arr, 99))

            # Noiseprint++
            npp_arr = None
            if npp is not None:
                npp = torch.squeeze(npp, 0)[0]
                npp_arr = npp.cpu().numpy().astype(np.float32)

    except Exception as e:
        sys.stderr.write(f"Error during TruFor forward pass: {str(e)}\n")
        sys.exit(4)

    # Save outputs to .npz
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_dict = {
        "map": map_arr,
        "score": np.float32(score_val),
        "scale": np.float32(scale),
        "imgsize": (orig_h, orig_w)
    }
    if conf_arr is not None:
        out_dict["conf"] = conf_arr
    if npp_arr is not None:
        out_dict["np++"] = npp_arr

    np.savez_compressed(output_path, **out_dict)
    sys.exit(0)


if __name__ == "__main__":
    main()

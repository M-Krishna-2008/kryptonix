"""Smoke test verifying train, calibrate, and analyze flow end-to-end.

SMOKE TEST ONLY, NOT A REAL DETECTOR.
Cleans up all temporary training weights after validation so best.pt is never a toy model by accident.
"""

import os
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import yaml
from tests.make_synthetic_clip import create_synthetic_clip
from ai_cctv_detection.analyzer import analyze
import ai_cctv_detection.analyzer as az

def run_pipeline():
    print("=" * 65)
    print(" STARTING PIPELINE SMOKE TEST (END-TO-END VERIFICATION)")
    print(" NOTICE: SMOKE TEST ONLY, NOT A REAL DETECTOR")
    print("=" * 65)

    # 1. Create synthetic video footage
    smoke_raw = Path("data_smoke")
    real_dir = smoke_raw / "real"
    fake_dir = smoke_raw / "fake"
    real_dir.mkdir(parents=True, exist_ok=True)
    fake_dir.mkdir(parents=True, exist_ok=True)

    print("\n[Step 1/5] Generating synthetic video clips...")
    c1 = create_synthetic_clip(real_dir / "cam1_authentic.mp4", num_frames=35, pattern="cctv")
    c2 = create_synthetic_clip(real_dir / "cam2_authentic.mp4", num_frames=35, pattern="cctv")
    f1 = create_synthetic_clip(fake_dir / "gen1_ai_video.mp4", num_frames=35, pattern="ai_simulated")
    f2 = create_synthetic_clip(fake_dir / "gen2_ai_video.mp4", num_frames=35, pattern="ai_simulated")
    print(f"Created 2 real clips and 2 AI clips in {smoke_raw}")

    # 2. Build dataset (split by video)
    print("\n[Step 2/5] Building dataset with video-level split...")
    from tools.build_dataset import main as build_dataset_main
    orig_argv = sys.argv
    sys.argv = ["build_dataset.py", str(real_dir), str(fake_dir), "--output-dir", "data_smoke_yolo", "--fps", "2.0"]
    build_dataset_main()

    # 3. Check metadata shortcut learning
    print("\n[Step 3/5] Running shortcut learning check on metadata...")
    from tools.metadata_check import main as metadata_check_main
    sys.argv = ["metadata_check.py", "--manifest", "data_smoke_yolo/manifest.json"]
    metadata_check_main()

    # 4. Train 1 epoch smoke model
    print("\n[Step 4/5] Running 1-epoch fine-tuning smoke test...")
    from tools.train import main as train_main
    smoke_weights = Path("models/smoke_best.pt")
    sys.argv = ["train.py", "--data-dir", "data_smoke_yolo", "--epochs", "1", "--batch", "4", "--workers", "0", "--output-weights", str(smoke_weights)]
    train_main()
    assert smoke_weights.is_file(), "Smoke weights were not created!"

    # 5. Fit Platt scaling calibration
    print("\n[Step 5/5] Running calibration fit...")
    from tools.calibrate import main as calibrate_main
    temp_calib_yaml = Path("ai_cctv_detection/configs/calibration_smoke.yaml")
    sys.argv = ["calibrate.py", "--model", str(smoke_weights), "--val-dir", "data_smoke_yolo/val", "--output-config", str(temp_calib_yaml)]
    calibrate_main()

    # 6. Run full inference test with smoke model
    print("\n[Step 6/6] Running analyzer.analyze() with smoke model...")
    az.BEST_MODEL_PATH = smoke_weights
    result = analyze(str(f1))
    print(f"Analysis Verdict: {result['verdict']}")
    print(f"Confidence: {result['overall_confidence']}")
    print(f"Artifacts: {len(result['findings'])} findings generated.")
    assert result["module"] == "ai_cctv_detection"
    assert len(result["evidence_file"]["sha256"]) == 64

    # Cleanup: delete smoke weights and temp data
    print("\n" + "=" * 65)
    print(" CLEANING UP SMOKE ARTIFACTS (FORENSIC HONESTY ENFORCEMENT)")
    if smoke_weights.is_file():
        smoke_weights.unlink()
        print(" [CLEANUP] Deleted models/smoke_best.pt")

    if temp_calib_yaml.is_file():
        temp_calib_yaml.unlink()

    shutil.rmtree(smoke_raw, ignore_errors=True)
    shutil.rmtree("data_smoke_yolo", ignore_errors=True)
    shutil.rmtree("runs_train", ignore_errors=True)
    az.BEST_MODEL_PATH = az.MODELS_DIR / "best.pt"
    print(" [CLEANUP] Cleaned up temporary test data and reset BEST_MODEL_PATH.")
    print(" [SUCCESS] Smoke test verified end-to-end pipeline flawlessly!")
    print(" NOTICE: SMOKE TEST ONLY, NOT A REAL DETECTOR - WEIGHTS SAFELY REMOVED")
    print("=" * 65)


if __name__ == "__main__":
    run_pipeline()

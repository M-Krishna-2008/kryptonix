"""
Script to generate reproducible test samples for offline testing of ai_image_detection.
Creates:
  1. sample_camera_authentic.jpg (Natural texture + Canon Camera EXIF tags + high Q)
  2. sample_ai_tampered.png (AI generator prompt tag + synthetic high-frequency gradient)
  3. sample_compressed_social.jpg (JPEG quality < 75, stripped EXIF, social media dimensions)
  4. sample_blurry_small.jpg (180x180 px, blurred)
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, PngImagePlugin

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def create_samples():
    print(f"[*] Generating test samples in {SAMPLES_DIR}...")

    # 1. Authentic Camera Photo Simulation
    w, h = 800, 600
    # Simulate natural sensor noise + texture
    x = np.linspace(0, 10, w)
    y = np.linspace(0, 10, h)
    xx, yy = np.meshgrid(x, y)
    pattern = (np.sin(xx) * np.cos(yy) * 80 + 128).astype(np.uint8)
    noise = np.random.normal(0, 4, (h, w)).astype(np.int16)
    sensor_img = np.clip(pattern.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    rgb = np.stack([sensor_img, (sensor_img * 0.9).astype(np.uint8), (sensor_img * 0.8).astype(np.uint8)], axis=2)
    img_real = Image.fromarray(rgb)

    # Attach camera EXIF
    exif = img_real.getexif()
    exif[0x010F] = "Canon"                    # Make
    exif[0x0110] = "Canon EOS 5D Mark IV"     # Model
    exif[0x9003] = "2026:05:12 14:22:10"      # DateTimeOriginal
    exif[0x829A] = (1, 125)                   # ExposureTime
    exif[0x829D] = (28, 10)                   # FNumber 2.8

    p_real = SAMPLES_DIR / "sample_camera_authentic.jpg"
    img_real.save(p_real, "JPEG", quality=95, exif=exif)
    print(f"  [+] Created {p_real.name}")

    # 2. AI Generated Simulation with Provenance Tag
    w, h = 768, 768
    # High-frequency synthetic diffusion pattern
    gx = np.linspace(-5, 5, w)
    gy = np.linspace(-5, 5, h)
    gxx, gyy = np.meshgrid(gx, gy)
    synth = np.sin(gxx**2 + gyy**2) * 120 + 128
    synth_rgb = np.stack([
        np.clip(synth, 0, 255).astype(np.uint8),
        np.clip(synth * 0.5 + 64, 0, 255).astype(np.uint8),
        np.clip(255 - synth, 0, 255).astype(np.uint8)
    ], axis=2)
    img_ai = Image.fromarray(synth_rgb)

    # Add PNG AI generator metadata
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Software", "Stable Diffusion v2.1")
    meta.add_text("parameters", "photorealistic portrait, 8k resolution, cinematic lighting Steps: 30, Sampler: DPM++ 2M")

    p_ai = SAMPLES_DIR / "sample_ai_tampered.png"
    img_ai.save(p_ai, "PNG", pnginfo=meta)
    print(f"  [+] Created {p_ai.name}")

    # 3. Compressed Social Media Re-upload
    w, h = 1080, 1350
    social_arr = np.random.randint(80, 180, (h, w, 3), dtype=np.uint8)
    img_social = Image.fromarray(social_arr)
    p_social = SAMPLES_DIR / "sample_compressed_social.jpg"
    # Low quality JPEG to trigger social_media_reupload heuristic (< 75)
    img_social.save(p_social, "JPEG", quality=62)
    print(f"  [+] Created {p_social.name}")

    # 4. Small / Blurry Image
    img_small = Image.new("RGB", (180, 180), color=(140, 140, 140))
    # Apply Gaussian blur
    img_small = img_small.filter(ImageFilter.GaussianBlur(radius=8))
    p_small = SAMPLES_DIR / "sample_blurry_small.jpg"
    img_small.save(p_small, "JPEG", quality=80)
    print(f"  [+] Created {p_small.name}")


if __name__ == "__main__":
    create_samples()

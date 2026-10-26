"""
Generate synthetic smoke test sample images for image_forgery module.
Creates:
- authentic.jpg: synthetic photo with camera EXIF, unedited
- spliced.jpg: pasted patch from different quality, Photoshop EXIF, date mismatch
- copymove.jpg: duplicated distinct keypoint region
- renamed.png: JPEG image with .png extension (format mismatch)
- tiny.jpg: image smaller than 64px
- corrupt.jpg: truncated corrupted file
- notimage.jpg: text file with image extension
"""

import io
from pathlib import Path
import numpy as np
import piexif
from PIL import Image, ImageDraw

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def make_authentic():
    w, h = 600, 450
    # Create smooth realistic landscape gradient
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            arr[y, x, 0] = int(120 + 80 * np.sin(x / 50.0))
            arr[y, x, 1] = int(140 + 60 * np.cos(y / 60.0))
            arr[y, x, 2] = int(180 + 50 * np.sin((x + y) / 70.0))

    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    draw.ellipse([150, 100, 300, 250], fill=(220, 180, 100), outline=(240, 200, 120))

    # Real camera EXIF
    zeroth_ifd = {
        piexif.ImageIFD.Make: b"Canon",
        piexif.ImageIFD.Model: b"EOS 5D Mark IV",
        piexif.ImageIFD.DateTime: b"2023:04:12 11:20:00"
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: b"2023:04:12 11:20:00",
        piexif.ExifIFD.DateTimeDigitized: b"2023:04:12 11:20:00",
    }
    exif_bytes = piexif.dump({"0th": zeroth_ifd, "Exif": exif_ifd})

    out_path = SAMPLES_DIR / "authentic.jpg"
    img.save(out_path, format="JPEG", quality=95, exif=exif_bytes)
    print(f"Generated: {out_path.name}")


def make_spliced():
    w, h = 600, 450
    base = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            base[y, x, 0] = int(100 + 40 * np.sin(x / 40.0))
            base[y, x, 1] = int(120 + 40 * np.sin(y / 40.0))
            base[y, x, 2] = int(140 + 40 * np.cos((x - y) / 40.0))

    base_img = Image.fromarray(base)

    # Patch generated separately and recompressed at lower quality
    pw, ph = 160, 140
    patch_arr = np.random.randint(50, 240, (ph, pw, 3), dtype=np.uint8)
    patch_img = Image.fromarray(patch_arr)
    patch_draw = ImageDraw.Draw(patch_img)
    patch_draw.rectangle([20, 20, 140, 120], fill=(255, 60, 60), outline=(255, 255, 255))

    buf = io.BytesIO()
    patch_img.save(buf, format="JPEG", quality=50)
    buf.seek(0)
    recompressed_patch = Image.open(buf)

    # Splice patch into base image at [360, 120]
    base_img.paste(recompressed_patch, (360, 120))

    # Photoshop editing EXIF
    zeroth_ifd = {
        piexif.ImageIFD.Make: b"Canon",
        piexif.ImageIFD.Model: b"EOS 5D Mark IV",
        piexif.ImageIFD.Software: b"Adobe Photoshop CC 2024 (Windows)",
        piexif.ImageIFD.DateTime: b"2024:01:15 16:35:10"
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: b"2023:04:12 11:20:00",
        piexif.ExifIFD.DateTimeDigitized: b"2023:04:12 11:20:00"
    }
    exif_bytes = piexif.dump({"0th": zeroth_ifd, "Exif": exif_ifd})

    out_path = SAMPLES_DIR / "spliced.jpg"
    base_img.save(out_path, format="JPEG", quality=95, exif=exif_bytes)
    print(f"Generated: {out_path.name}")


def make_copymove():
    w, h = 600, 450
    arr = np.full((h, w, 3), 180, dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Distinct complex geometric star stamp to trigger high SIFT features
    def draw_stamp(dx, dy):
        draw.ellipse([dx, dy, dx + 70, dy + 70], fill=(40, 90, 160), outline=(255, 255, 255))
        draw.line([dx + 10, dy + 35, dx + 60, dy + 35], fill=(255, 200, 0), width=3)
        draw.line([dx + 35, dy + 10, dx + 35, dy + 60], fill=(255, 200, 0), width=3)
        draw.rectangle([dx + 25, dy + 25, dx + 45, dy + 45], fill=(220, 40, 40))

    # Place source stamp and copy-moved duplicate
    draw_stamp(80, 100)
    draw_stamp(380, 240)

    out_path = SAMPLES_DIR / "copymove.jpg"
    img.save(out_path, format="JPEG", quality=95)
    print(f"Generated: {out_path.name}")


def make_renamed():
    # JPEG bytes saved as .png
    img = Image.new("RGB", (200, 200), color=(70, 130, 180))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    out_path = SAMPLES_DIR / "renamed.png"
    with open(out_path, "wb") as f:
        f.write(buf.getvalue())
    print(f"Generated: {out_path.name}")


def make_tiny():
    # 32x32 image (smaller than 64px limit)
    img = Image.new("RGB", (32, 32), color=(100, 150, 200))
    out_path = SAMPLES_DIR / "tiny.jpg"
    img.save(out_path, format="JPEG")
    print(f"Generated: {out_path.name}")


def make_corrupt():
    # Truncated broken JPEG
    out_path = SAMPLES_DIR / "corrupt.jpg"
    with open(out_path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
        f.write(b"CORRUPTED_TRUNCATED_BYTES" * 10)
    print(f"Generated: {out_path.name}")


def make_notimage():
    # Text file disguised as jpg
    out_path = SAMPLES_DIR / "notimage.jpg"
    with open(out_path, "wb") as f:
        f.write(b"This is a text file, not a valid image file. Forensic intake must safely reject it.")
    print(f"Generated: {out_path.name}")


def main():
    print(f"Generating test samples in {SAMPLES_DIR}...")
    make_authentic()
    make_spliced()
    make_copymove()
    make_renamed()
    make_tiny()
    make_corrupt()
    make_notimage()
    print("All smoke test samples created successfully.")


if __name__ == "__main__":
    main()

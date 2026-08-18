#!/usr/bin/env python3
"""
Photo -> self-typing ASCII portrait SVG.

Pipeline: rembg cutout -> bilateral filter -> CLAHE -> darkening curve
(v/255)^1.7 -> map to a 13-level ramp -> SVG with per-row clipPath wipe
animation (SMIL, fill="freeze", staggered by row).

Usage:
    python3 portrait.py --input photo.jpg --output ascii_portrait.svg \
        --cols 90 --display-width 460

Requires: pillow, numpy, opencv-python-headless, rembg, onnxruntime
"""
import argparse
import io
import numpy as np
from PIL import Image
import cv2

# Lightest -> darkest, 13 characters (leading space = background -> nothing)
RAMP = " .`:-=+*cs#%@"

# Grid geometry the guide's SVGs are built around.
CHAR_W = 7.74          # advance width in px for font-size 12.9 (0.600em)
FONT_SIZE = 12.9
LINE_HEIGHT_FACTOR = 1.0  # rows are packed at char cell height


def remove_background(img: Image.Image) -> Image.Image:
    """Cut the subject out onto a plain white background."""
    from rembg import remove
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cut = remove(buf.getvalue())
    fg = Image.open(io.BytesIO(cut)).convert("RGBA")

    white_bg = Image.new("RGBA", fg.size, (255, 255, 255, 255))
    composited = Image.alpha_composite(white_bg, fg)
    return composited.convert("RGB")


def process_to_gray(img: Image.Image, clahe_clip: float = 3.0) -> np.ndarray:
    """Bilateral filter -> CLAHE -> darkening curve. Returns 0-255 uint8 array."""
    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Smooth skin, keep edges
    smoothed = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # Local contrast so a flatly side-lit face doesn't collapse to one tone
    clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8))
    contrasted = clahe.apply(smoothed)

    # The fix: without this the face renders washed out and featureless
    normalized = contrasted.astype(np.float64) / 255.0
    darkened = np.power(normalized, 1.7) * 255.0
    return darkened.astype(np.uint8)


def to_ascii_rows(gray: np.ndarray, cols: int) -> list[str]:
    h, w = gray.shape
    rows = max(1, round(cols * (h / w) * 0.48))
    resized = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)

    # brightness -> ramp index (bright = high value = space/light end)
    idx = (resized.astype(np.float64) / 255.0 * (len(RAMP) - 1)).astype(int)
    idx = np.clip(idx, 0, len(RAMP) - 1)
    # invert: dark pixel (low value) -> dense char (end of ramp)
    idx = (len(RAMP) - 1) - idx

    lines = []
    for r in range(rows):
        line = "".join(RAMP[i] for i in idx[r])
        lines.append(line)
    return lines


def escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_svg(rows: list[str], display_width: int, fill: str = "currentColor") -> str:
    cols = max(len(r) for r in rows) if rows else 0
    width_px = cols * CHAR_W
    height_px = len(rows) * FONT_SIZE * LINE_HEIGHT_FACTOR

    scale = display_width / width_px if width_px else 1
    display_height = round(height_px * scale)

    parts = []
    parts.append(
        f'<svg viewBox="0 0 {width_px:.2f} {height_px:.2f}" '
        f'width="{display_width}" height="{display_height}" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="ramp-mono, monospace" '
        f'font-size="{FONT_SIZE}">'
    )
    parts.append(f'<style>text {{ fill: {fill}; white-space: pre; }}</style>')

    for i, row in enumerate(rows):
        y = (i + 1) * FONT_SIZE
        row_id = f"row{i}"
        clip_id = f"clip{i}"
        begin = round(i * 0.09, 2)
        text_escaped = escape_xml(row) if row.strip() else "&#160;"
        parts.append(f'<clipPath id="{clip_id}">')
        parts.append(
            f'  <rect x="0" y="{y - FONT_SIZE:.2f}" width="0" height="{FONT_SIZE:.2f}">'
        )
        parts.append(
            f'    <animate attributeName="width" from="0" to="{width_px:.2f}" '
            f'begin="{begin}s" dur="0.5s" fill="freeze" />'
        )
        parts.append("  </rect>")
        parts.append("</clipPath>")
        parts.append(f'<g clip-path="url(#{clip_id})">')
        parts.append(f'  <text x="0" y="{y:.2f}" xml:space="preserve">{text_escaped}</text>')
        parts.append("</g>")
        # cursor block riding the wipe edge
        parts.append(
            f'<rect y="{y - FONT_SIZE:.2f}" width="{CHAR_W:.2f}" height="{FONT_SIZE:.2f}" '
            f'fill="{fill}" opacity="0.85">'
        )
        parts.append(
            f'  <animate attributeName="x" from="0" to="{width_px:.2f}" '
            f'begin="{begin}s" dur="0.5s" fill="freeze" />'
        )
        parts.append(
            f'  <set attributeName="opacity" to="0" begin="{begin + 0.5}s" fill="freeze" />'
        )
        parts.append("</rect>")

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to source photo")
    ap.add_argument("--output", default="ascii_portrait.svg")
    ap.add_argument("--cols", type=int, default=90)
    ap.add_argument("--display-width", type=int, default=460)
    ap.add_argument("--clahe-clip", type=float, default=3.0)
    ap.add_argument("--fill", default="currentColor")
    ap.add_argument("--skip-rembg", action="store_true", help="Skip background removal (image already has a plain bg)")
    args = ap.parse_args()

    img = Image.open(args.input)

    if not args.skip_rembg:
        print("Removing background (first run downloads ~176MB model, cached after)...")
        img = remove_background(img)

    gray = process_to_gray(img, clahe_clip=args.clahe_clip)
    rows = to_ascii_rows(gray, cols=args.cols)
    svg = build_svg(rows, display_width=args.display_width, fill=args.fill)

    with open(args.output, "w") as f:
        f.write(svg)

    print(f"Wrote {args.output}: {len(rows)} rows x {args.cols} cols")


if __name__ == "__main__":
    main()

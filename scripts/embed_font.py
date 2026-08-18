#!/usr/bin/env python3
"""
Inline a woff2 font subset as a base64 data URI into an SVG's @font-face.

Usage:
    python3 embed_font.py --svg ascii_portrait.svg --font fonts/ramp.woff2 \
        --family ramp-mono --output ascii_portrait.svg
"""
import argparse
import base64


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", required=True)
    ap.add_argument("--font", required=True)
    ap.add_argument("--family", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.font, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    with open(args.svg, "r") as f:
        svg = f.read()

    face = (
        f'<defs><style>@font-face {{ font-family: \'{args.family}\'; '
        f'src: url(data:font/woff2;base64,{b64}) format(\'woff2\'); }}</style></defs>'
    )

    # insert right after the opening <svg ...> tag
    idx = svg.find(">") + 1
    out = svg[:idx] + face + svg[idx:]

    with open(args.output, "w") as f:
        f.write(out)

    print(f"Embedded {args.font} ({len(b64)} base64 chars) as font-family '{args.family}' -> {args.output}")


if __name__ == "__main__":
    main()

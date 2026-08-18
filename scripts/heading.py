#!/usr/bin/env python3
"""
Section heading as SVG: lowercase mono label + hairline rule to the right edge.
Remember: the alt text is what screen readers get, and GitHub's outline
will NOT pick these up as headings (no anchor links on images).

Usage:
    python3 heading.py "about" --width 460 --output headings/about.svg
"""
import argparse

FONT_FAMILY = "heading-mono, monospace"


def build_svg(label: str, width: int, height: int = 24) -> str:
    label = label.lower()
    text_w = len(label) * 8.5 + 4
    y_text = height / 2 + 4
    y_line = height / 2
    return f'''<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" \
xmlns="http://www.w3.org/2000/svg" font-family="{FONT_FAMILY}">
<style>text{{fill:currentColor}} line{{stroke:currentColor;stroke-opacity:.35}}</style>
<text x="0" y="{y_text}" font-size="13" letter-spacing="1.5">{label}</text>
<line x1="{text_w}" y1="{y_line}" x2="{width}" y2="{y_line}" stroke-width="1" />
</svg>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--width", type=int, default=460)
    ap.add_argument("--height", type=int, default=24)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    svg = build_svg(args.label, args.width, args.height)
    with open(args.output, "w") as f:
        f.write(svg)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

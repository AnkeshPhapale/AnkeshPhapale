#!/usr/bin/env bash
# Subset JetBrains Mono (SIL OFL) into small per-role woff2 files.
# JetBrains Mono is 600/1000 units per em -> exactly the 0.600em advance
# the portrait grid (CHAR_W = 7.74 @ font-size 12.9) assumes.
#
# Usage:
#   1. Download JetBrainsMono-Regular.ttf from https://github.com/JetBrains/JetBrainsMono
#      (grab the LICENSE.txt too — it must ship in the repo alongside the font)
#   2. pip install fonttools brotli
#   3. ./subset_fonts.sh JetBrainsMono-Regular.ttf ../fonts
set -euo pipefail

FONT="${1:?usage: subset_fonts.sh <path-to-ttf> <output-dir>}"
OUTDIR="${2:?usage: subset_fonts.sh <path-to-ttf> <output-dir>}"
mkdir -p "$OUTDIR"

# 1. Portrait ramp — 13 characters used by the ASCII grid
pyftsubset "$FONT" --text=' .`:-=+*cs#%@' \
  --flavor=woff2 --layout-features='' --no-hinting \
  -o "$OUTDIR/ramp.woff2"

# 2. Headings — lowercase letters + hyphen + space, adjust to your actual heading text
pyftsubset "$FONT" --text='abcdefghijklmnopqrstuvwxyz -' \
  --flavor=woff2 --layout-features='' --no-hinting \
  -o "$OUTDIR/headings.woff2"

# 3. Basic latin, for stats/body text graphics
pyftsubset "$FONT" --unicodes='U+0020-007E' \
  --flavor=woff2 --layout-features='' --no-hinting \
  -o "$OUTDIR/basic.woff2"

echo "Subsets written to $OUTDIR:"
ls -la "$OUTDIR"/*.woff2

cat <<'EOF'

Next: base64-encode each subset and inline it into the matching SVG's
<defs><style> block, e.g.:

  <defs>
    <style>
      @font-face {
        font-family: 'ramp-mono';
        src: url(data:font/woff2;base64,BASE64_HERE) format('woff2');
      }
      text { font-family: 'ramp-mono', monospace; }
    </style>
  </defs>

Generate the base64 with:
  base64 -w0 fonts/ramp.woff2

External font URLs will NOT work here — these SVGs load via an <img> tag,
and browsers refuse subresource fetches inside image documents. The
base64 data URI is the only path that works.
EOF

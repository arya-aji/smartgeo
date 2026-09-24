"""Generate a synthetic "photo of a map sheet" for smoke testing.

Produces a slightly rotated, light map sheet on a dark background with grid
lines and a 16-digit IDSUBSLS code, so the CV pipeline can be exercised
end-to-end.

Usage:
    python scripts/make-test-image.py out.jpg [idsubsls]
"""

from __future__ import annotations

import sys

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1700, 1300


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build(idsubsls: str) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), (28, 30, 34))
    draw = ImageDraw.Draw(img)

    # The sheet, intentionally not axis-aligned.
    quad = [(190, 140), (1500, 110), (1530, 1150), (170, 1180)]
    draw.polygon(quad, fill=(236, 233, 222), outline=(70, 70, 70), width=4)

    # Internal grid so the image has structure/edges.
    left, right, top, bottom = 200, 1520, 140, 1170
    for i in range(1, 12):
        x = left + i * (right - left) / 12
        draw.line([(x, top + 10), (x - 20, bottom - 10)], fill=(203, 200, 190), width=2)
    for j in range(1, 9):
        y = top + j * (bottom - top) / 9
        draw.line([(left + 10, y), (right - 10, y + 5)], fill=(203, 200, 190), width=2)

    # Title + ID code.
    title_font = _font(46)
    id_font = _font(92)
    draw.text((260, 190), "PETA WSS - LEMBAR DESA", fill=(20, 20, 20), font=title_font)
    draw.text((520, 900), idsubsls, fill=(5, 5, 5), font=id_font)

    return img


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "test-map.jpg"
    idsubsls = sys.argv[2] if len(sys.argv) > 2 else "3173030005003200"
    build(idsubsls).save(out, quality=92)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

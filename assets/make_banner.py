"""Draw assets/banner.png from code (Pillow). Maintainer tool, not part of the exercise.

    pip install pillow
    python assets/make_banner.py --font path/to/Inter-Variable.ttf --mono path/to/Mono.ttf

Colours are the series palette, taken from the Part 1 checklist graphic:
navy #0F172A, teal #0D9488, light teal #5EEAD4, slate #CBD5E1 / #64748B.
Without --font it falls back to Pillow's built-in font (works, looks plainer).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = "#0F172A"
NAVY_2 = "#1E293B"
TEAL = "#0D9488"
TEAL_LIGHT = "#5EEAD4"
SLATE = "#CBD5E1"
SLATE_DARK = "#64748B"
WHITE = "#FFFFFF"

S = 2  # draw at 2x for crisp text on high-DPI screens
W, H = 1280 * S, 360 * S
OUT = Path(__file__).resolve().parent / "banner.png"


def font(path: str | None, size: int, weight: str | None = None):
    if not path:
        return ImageFont.load_default(size * S)
    f = ImageFont.truetype(path, size * S)
    if weight:
        try:
            f.set_variation_by_name(weight)
        except (OSError, ValueError):
            pass
    return f


def tracked(draw, xy, text, fnt, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking * S
    return x


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font")
    ap.add_argument("--mono")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # faint grid, like graph paper on a whiteboard
    for x in range(0, W, 40 * S):
        d.line([(x, 0), (x, H)], fill="#131D33", width=1)
    for y in range(0, H, 40 * S):
        d.line([(0, y), (W, y)], fill="#131D33", width=1)

    left = 72 * S
    tracked(d, (left, 62 * S), "CTRL+ALT+DATA", font(a.font, 22, "Bold"), TEAL_LIGHT, 4)
    d.text((left, 100 * S), "Rebooting", font=font(a.font, 64, "ExtraBold"), fill=WHITE)
    d.text((left, 172 * S), "Data Engineering", font=font(a.font, 64, "ExtraBold"), fill=TEAL_LIGHT)
    d.text(
        (left, 262 * S),
        "Companion code for the 14-part series across 3 tracks by Kushagra Soni",
        font=font(a.font, 22, "Medium"),
        fill=SLATE,
    )

    # Track I (Parts 1-5) as a pipeline: Part 1 lit, the rest waiting
    x0, x1, y = 760 * S, 1190 * S, 150 * S
    d.line([(x0, y), (x1, y)], fill=SLATE_DARK, width=4 * S)
    labels = ["Pipelines", "Batch vs stream", "Lakehouse", "Quality", "AI agents"]
    small = font(a.font, 16, "SemiBold")
    for i, label in enumerate(labels):
        cx = x0 + (x1 - x0) * i // 4
        r = 17 * S
        if i == 0:
            d.ellipse([cx - r, y - r, cx + r, y + r], fill=TEAL, outline=TEAL_LIGHT, width=3 * S)
        else:
            d.ellipse([cx - r, y - r, cx + r, y + r], fill=NAVY, outline=SLATE_DARK, width=3 * S)
        wk = f"P{i + 1}"
        wf = font(a.font, 15, "Bold")
        d.text((cx - d.textlength(wk, font=wf) / 2, y - 9 * S), wk, font=wf, fill=WHITE if i == 0 else SLATE)
        d.text((cx - d.textlength(label, font=small) / 2, y + 30 * S), label, font=small,
               fill=TEAL_LIGHT if i == 0 else SLATE_DARK)

    # a terminal line, because this repo is meant to be run, not read
    box = [760 * S, 240 * S, 1190 * S, 292 * S]
    d.rounded_rectangle(box, radius=10 * S, fill=NAVY_2, outline="#334155", width=2)
    mono = font(a.mono, 17, "Medium")
    d.text((box[0] + 20 * S, box[1] + 15 * S), "$", font=mono, fill=TEAL_LIGHT)
    d.text((box[0] + 42 * S, box[1] + 15 * S), "python part1/run.py", font=mono, fill=WHITE)

    d.rectangle([0, H - 6 * S, W, H], fill=TEAL)
    img.save(a.out, optimize=True)
    print(f"wrote {a.out} ({W}x{H})")


if __name__ == "__main__":
    main()

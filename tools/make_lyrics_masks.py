#!/usr/bin/env python3
"""Render each lyric line to a transparent alpha-mask PNG (glyphs in the alpha channel),
Helvetica-Neue set, wrapped to the width of the free "column" beside the dish. Masks are
TIGHT in height (just the text block) so Blender can place each line at any vertical position.
Also emit per-word bounding boxes so the `lyrics` treatment can birth each word's filaments at
that word's timestamp.

Run with the project venv (has Pillow):
    .venv/bin/python tools/make_lyrics_masks.py

Output:
    plates/lyrics/cue_XX.png     RGBA masks (black glyphs, transparent ground), tight height
    tools/lyrics_layout.json     [{id, text, haha, png, W, H, words:[{w, box:[x0,y0,x1,y1]}]}]

Coordinates are image pixels, origin top-left (Blender's build_lyrics flips Y).
"""
import argparse
import json
import re
import string
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
FONT_PATH = "/System/Library/Fonts/HelveticaNeue.ttc"
FACE_INDEX = 10          # 0=Regular, 10=Medium (a touch more body so thin strokes trace legibly)

COL_W = 700              # mask width in px = the free column's width (Blender scales this to world)
PAD = 24
FMAX = 132               # max font px; shrinks only if a single word is too wide for the column
FMIN = 40
LEADING = 1.08


def wrap(words, font, maxw, spacew):
    rows, cur, curw = [], [], 0.0
    for w in words:
        ww = font.getlength(w)
        add = ww if not cur else spacew + ww
        if cur and curw + add > maxw:
            rows.append(cur); cur, curw = [w], ww
        else:
            cur.append(w); curw += add
    if cur:
        rows.append(cur)
    return rows


def choose_font(words, maxw):
    for size in range(FMAX, FMIN - 1, -2):
        font = ImageFont.truetype(FONT_PATH, size, index=FACE_INDEX)
        if all(font.getlength(w) <= maxw for w in words):
            return font, size
    return ImageFont.truetype(FONT_PATH, FMIN, index=FACE_INDEX), FMIN


def render_cue(text):
    maxw = COL_W - 2 * PAD
    words = text.split()
    font, _ = choose_font(words, maxw)
    ascent, descent = font.getmetrics()
    line_h = (ascent + descent) * LEADING
    spacew = font.getlength(" ")
    rows = wrap(words, font, maxw, spacew)
    block_h = line_h * len(rows)
    H = int(round(block_h + 2 * PAD))
    img = Image.new("RGBA", (COL_W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    boxes = []
    y = PAD
    for row in rows:
        roww = sum(font.getlength(w) for w in row) + spacew * (len(row) - 1)
        x = (COL_W - roww) / 2.0
        for w in row:
            ww = font.getlength(w)
            draw.text((x, y), w, font=font, fill=(0, 0, 0, 255), anchor="la")
            core = w.rstrip(string.punctuation)          # drop trailing punctuation (e.g. "Haha," -> "Haha")
            corew = font.getlength(core) if core else ww
            boxes.append({"w": w,
                          "box": [round(x), round(y), round(x + ww), round(y + line_h)],
                          "corebox": [round(x), round(y), round(x + corew), round(y + line_h)]})
            x += ww + spacew
        y += line_h
    return img, boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lyrics", default=str(REPO / "tools" / "lyrics.txt"))
    ap.add_argument("--out", default=str(REPO / "plates" / "lyrics"))
    ap.add_argument("--layout", default=str(REPO / "tools" / "lyrics_layout.json"))
    args = ap.parse_args()

    cues = [ln.strip() for ln in Path(args.lyrics).read_text().splitlines() if ln.strip()]
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    layout = []
    for i, text in enumerate(cues):
        img, boxes = render_cue(text)
        png = outdir / f"cue_{i:02d}.png"
        img.save(png)
        layout.append({
            "id": i, "text": text,
            "haha": bool(re.search(r"\bhaha\b", text, re.I)),
            "png": str(png.relative_to(REPO)),
            "W": img.width, "H": img.height,
            "words": boxes,
        })
    Path(args.layout).write_text(json.dumps(layout, indent=1, ensure_ascii=False))
    print(f"wrote {len(cues)} masks to {outdir}; layout -> {args.layout}")
    for c in layout:
        if c["haha"]:
            print(f"  HAHA cue {c['id']:2d} ({c['W']}x{c['H']}) \"{c['text']}\"")


if __name__ == "__main__":
    main()

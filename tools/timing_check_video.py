#!/usr/bin/env python3
"""Render a review video to check word timings by ear: each section's text on screen, the
current word lit up at its aligned time, over the untouched master audio (stream-copied, so
bit-exact). Frames are drawn with Pillow and piped to ffmpeg (the system ffmpeg has no
libass/drawtext). Output goes under renders/ (gitignored).

    .venv/bin/python tools/timing_check_video.py --audio "Robocobra Quartet - Nothing ….wav" \
        --words tools/nothing_align_words.json --sections tools/nothing_sections.json \
        --out renders/nothing_timing_check.mov
"""
import argparse
import bisect
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 960, 540, 25
DIM, LIT, DONE, INFO = (70, 70, 70), (255, 150, 40), (200, 200, 200), (130, 130, 130)


def wrap(draw, words, font, maxw):
    """Greedy line-wrap → list of lines, each a list of word indices."""
    lines, cur, x = [], [], 0
    space = draw.textlength(" ", font=font)
    for i, w in enumerate(words):
        wl = draw.textlength(w, font=font)
        if cur and x + space + wl > maxw:
            lines.append(cur); cur, x = [], 0
        x += (space if cur else 0) + wl
        cur.append(i)
    if cur:
        lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--sections", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    words = json.loads(Path(args.words).read_text())
    sections = json.loads(Path(args.sections).read_text())
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", args.audio], capture_output=True,
                               text=True, check=True).stdout)
    big = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 40)
    small = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 16)
    starts = [w["start"] for w in words]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-i", args.audio, "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-shortest", args.out], stdin=subprocess.PIPE)
    blank = Image.new("RGB", (W, H)).tobytes()
    cache = {}
    for n in range(int(dur * FPS) + 1):
        t = n / FPS
        k = bisect.bisect_right(starts, t) - 1
        if k < 0 or t > words[k]["end"] + 1.0:
            ff.stdin.write(blank); continue
        key = (k, t <= words[k]["end"])
        if key not in cache:
            cache.clear()
            w = words[k]
            sec = [x for x in words if x["section"] == w["section"]]
            j = sec.index(w)
            img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
            lines = wrap(d, [x["word"] for x in sec], big, W - 120)
            y = H / 2 - len(lines) * 26
            for line in lines:
                txt = [sec[i]["word"] for i in line]
                x = (W - d.textlength(" ".join(txt), font=big)) / 2
                for i in line:
                    col = LIT if (i == j and key[1]) else DONE if i <= j else DIM
                    d.text((x, y), sec[i]["word"], font=big, fill=col)
                    x += d.textlength(sec[i]["word"] + " ", font=big)
                y += 52
            p = "manual" if w.get("manual") else f"p={w['prob']:.2f}"
            d.text((24, H - 56), f"[{w['section']}] {sections[w['section']].get('note', '')}",
                   font=small, fill=INFO)
            d.text((24, H - 32), f"{w['word']}  {w['start']:.2f}-{w['end']:.2f}  {p}",
                   font=small, fill=INFO)
            cache[key] = img.tobytes()
        ff.stdin.write(cache[key])
    ff.stdin.close()
    if ff.wait():
        raise SystemExit("ffmpeg failed")
    print("wrote", args.out)


if __name__ == "__main__":
    main()

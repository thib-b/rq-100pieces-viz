#!/usr/bin/env python3
"""Merge the mask layout (per-word boxes) with the forced-alignment word times into cues.json,
the single file the Blender `lyrics` treatment consumes.

    .venv/bin/python tools/build_cues.py            # real times from align_words.json
    .venv/bin/python tools/build_cues.py --placeholder   # even spacing, no alignment needed

Each cue: {id, text, png, W, H, side, ypos, haha, start, end,
           words:[{w, box:[x0,y0,x1,y1], start, end}]}
Times are seconds on the audio timeline. side L/R, ypos 0..1 (fraction of column height, 0.5=centre).
"""
import argparse
import difflib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def norm(s):
    return re.sub(r"[^a-z0-9']", "", s.lower())


def assign_times_real(disp, align_path):
    """disp: flat list of dicts with 'w'. Returns parallel list of (start,end)."""
    A = [w for w in json.load(open(align_path)) if norm(w["word"])]
    a_norm = [norm(w["word"]) for w in A]
    d_norm = [norm(d["w"]) for d in disp]
    times = [None] * len(disp)
    sm = difflib.SequenceMatcher(None, d_norm, a_norm, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (A[j1 + k]["start"], A[j1 + k]["end"])
        elif tag == "replace":
            # spread the aligned span across the display words in this block
            s = A[j1]["start"] if j1 < len(A) else A[-1]["start"]
            e = A[j2 - 1]["end"] if j2 - 1 < len(A) else A[-1]["end"]
            n = i2 - i1
            for k in range(n):
                a = s + (e - s) * k / max(1, n)
                b = s + (e - s) * (k + 1) / max(1, n)
                times[i1 + k] = (round(a, 3), round(b, 3))
    # fill any remaining Nones by interpolating between known neighbours
    last = 0.0
    for i in range(len(times)):
        if times[i] is None:
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), last + 0.3)
            times[i] = (round(last, 3), round((last + nxt) / 2, 3))
        last = times[i][1]
    return times


def assign_times_placeholder(disp, t0=6.0, wps=3.0, gap=0.4, line_ids=None):
    """Even spacing for a no-alignment visual test. wps words/sec; small gap between cues."""
    times = []
    t = t0
    prev_cue = None
    for i, d in enumerate(disp):
        if line_ids and d["cue"] != prev_cue and prev_cue is not None:
            t += gap
        prev_cue = d["cue"]
        times.append((round(t, 3), round(t + 1.0 / wps, 3)))
        t += 1.0 / wps
    return times


MAX_WORD_SECS = 1.0    # clamp each word's on-screen end so over-long tails don't hang
MIN_WORD_SECS = 0.20   # give zero-duration (snapped) words a little presence

# Haha words linger (fade ~10s) into later same-side lines, so give them extreme lanes clear of
# the centred regular blocks: haha1 top, haha2 bottom, haha3 (the one that stays) top.
# (side stays natural-alternating.)
HAHA_YPOS = [0.85, 0.15, 0.85]


def sanitize(words):
    """Clamp on-screen word durations: an end never runs past the next word's onset nor past
    start+MAX_WORD_SECS (fixes whisper's over-extended phrase-final words); floor zero-durations."""
    for i, w in enumerate(words):
        s = w["start"]
        nxt = words[i + 1]["start"] if i + 1 < len(words) else float("inf")
        e = min(w["end"], s + MAX_WORD_SECS, nxt)
        w["end"] = round(max(e, s + MIN_WORD_SECS), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=str(REPO / "tools" / "haha_lyrics_layout.json"))
    ap.add_argument("--align", default=str(REPO / "tools" / "haha_align_words_large.json"))
    ap.add_argument("--fixes", default=str(REPO / "tools" / "haha_time_fixes.json"))
    ap.add_argument("--out", default=str(REPO / "tools" / "haha_cues.json"))
    ap.add_argument("--placeholder", action="store_true")
    args = ap.parse_args()

    layout = json.load(open(args.layout))
    # flatten display words with cue back-reference
    disp = []
    for c in layout:
        for wi, w in enumerate(c["words"]):
            disp.append({"cue": c["id"], "wi": wi, "w": w["w"]})

    if args.placeholder:
        times = assign_times_placeholder(disp, line_ids=True)
    else:
        times = assign_times_real(disp, args.align)

    for d, t in zip(disp, times):
        layout[d["cue"]]["words"][d["wi"]]["start"] = t[0]
        layout[d["cue"]]["words"][d["wi"]]["end"] = t[1]

    # manual per-word corrections (things forced alignment can't place)
    import os
    if os.path.exists(args.fixes):
        for fx in json.load(open(args.fixes)):
            for w in layout[fx["cue"]]["words"]:
                if w["w"] == fx["word"]:
                    if "start" in fx:
                        w["start"] = fx["start"]
                    if "end" in fx:
                        w["end"] = fx["end"]
                    break

    for c in layout:
        sanitize(c["words"])

    n_haha = sum(1 for c in layout if c["haha"])
    haha_order = 0
    cues = []
    for c in layout:
        ws = c["words"]
        cue = {
            "id": c["id"], "text": c["text"], "png": c["png"], "W": c["W"], "H": c["H"],
            "haha": c["haha"],
            "side": "L" if c["id"] % 2 == 0 else "R",   # natural alternation
            "ypos": 0.5,
            "haha_stay": False,
            "start": ws[0]["start"], "end": ws[-1]["end"],
            "words": ws,
        }
        if c["haha"]:
            cue["ypos"] = HAHA_YPOS[min(haha_order, len(HAHA_YPOS) - 1)]
            cue["haha_stay"] = (haha_order == n_haha - 1)   # last haha stays to the song end
            haha_order += 1
        cues.append(cue)

    Path(args.out).write_text(json.dumps(cues, indent=1, ensure_ascii=False))
    matched = sum(1 for d, t in zip(disp, times) if t)
    print(f"wrote {len(cues)} cues, {len(disp)} words ({matched} timed) -> {args.out}")
    for c in cues:
        if c["haha"]:
            print(f"  HAHA cue {c['id']:2d} side={c['side']} ypos={c['ypos']} stay={c['haha_stay']} "
                  f"start={c['start']:.2f} \"{c['text']}\"")
    print("  first cue words:", [(w["w"], w["start"]) for w in cues[0]["words"]])


if __name__ == "__main__":
    main()

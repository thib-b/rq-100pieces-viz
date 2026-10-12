#!/usr/bin/env python3
"""Lyric line masks for Nothing's side-column lyrics (the `lyrics_columns` layer).

Two line sets:
  verse1  every aligned phrase that starts before the scene-1 landing (repeats included)
  outro   the lyric sheet's closing lines only, once each (sung repeats are not shown)

Each line's words are the aligned tokens (tools/nothing_align_words.json), so every display word
carries its own sung time. Masks reuse tools/make_lyrics_masks.render_cue (wrapped to the
column, per-word boxes), in Nothing's lyric face (songs/nothing/fonts.py: Helvetica Neue Bold)
and ALL CAPS.

    .venv/bin/python tools/nothing_lyric_masks.py            # both sets

Output per set:
    plates/nothing_lyrics/<set>_XX.png      RGBA masks (glyphs in alpha)
    tools/nothing_lyrics_<set>.json         [{id, phrases, text, png, W, H,
                                              words:[{w, box, start, end}]}]
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import make_lyrics_masks as mlm  # noqa: E402
from songs.nothing import cues, fonts  # noqa: E402

COL_W = 700          # mask px width = the column width (the style scales it to the column)
# verse1: aligned windows that are one sung line on the lyric sheet (aligned separately):
JOIN = {"Once we aimed": "to rule the world"}
# outro: the sheet's closing lines, as groups of aligned phrase indices (nothing_sections.json)
OUTRO = [[26, 27], [28, 29], [31], [33]]


def display(token):
    """Aligned token → display word: drop the lyric sheet's spaced dash ("- the" → "the")."""
    return token.lstrip("-– ").strip().upper()


def phrase_words(words, pi):
    return [w for w in words if w["section"] == pi and display(w["word"])]


def verse1_lines(phrases, words):
    landing = cues.scene1()["landing"]
    lines = []                                     # [(phrase indices, words)]
    for pi in range(len(phrases)):
        ws = phrase_words(words, pi)
        if not ws or ws[0]["start"] >= landing:
            continue
        prev_text = " ".join(display(w["word"]) for w in lines[-1][1]) if lines else ""
        join = {k.upper(): v.upper() for k, v in JOIN.items()}
        if join.get(prev_text) == " ".join(display(w["word"]) for w in ws):
            lines[-1] = (lines[-1][0] + [pi], lines[-1][1] + ws)
        else:
            lines.append(([pi], ws))
    return lines


def outro_lines(phrases, words):
    return [(group, [w for pi in group for w in phrase_words(words, pi)]) for group in OUTRO]


def write_set(name, lines):
    out = REPO / "plates/nothing_lyrics"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f"{name}_*.png"):
        old.unlink()
    layout = []
    for pis, ws in lines:
        text = " ".join(display(w["word"]) for w in ws)
        img, boxes = mlm.render_cue(text)
        assert len(boxes) == len(ws), (text, len(boxes), len(ws))
        i = len(layout)
        png = out / f"{name}_{i:02d}.png"
        img.save(png)
        layout.append({
            "id": i, "phrases": pis, "text": text, "png": str(png.relative_to(REPO)),
            "W": img.width, "H": img.height,
            "words": [{"w": b["w"], "box": b["box"], "start": w["start"], "end": w["end"]}
                      for b, w in zip(boxes, ws)],
        })
    dst = REPO / f"tools/nothing_lyrics_{name}.json"
    dst.write_text(json.dumps(layout, indent=1, ensure_ascii=False))
    print(f"{name}: {len(layout)} line masks -> {dst}")
    for c in layout:
        print(f"  {c['id']:2d} {c['words'][0]['start']:6.2f}-{c['words'][-1]['end']:6.2f} "
              f"{c['W']}x{c['H']}  {c['text']}")


def main():
    phrases = json.loads((REPO / "tools/nothing_sections.json").read_text())
    words = json.loads((REPO / "tools/nothing_align_words.json").read_text())
    mlm.COL_W = COL_W
    mlm.FACE_INDEX = fonts.LYRIC_FACE
    old = REPO / "plates/nothing_lyrics"
    for f in old.glob("line_*.png"):              # pre-sets naming
        f.unlink()
    (REPO / "tools/nothing_lyrics_layout.json").unlink(missing_ok=True)
    write_set("verse1", verse1_lines(phrases, words))
    write_set("outro", outro_lines(phrases, words))


if __name__ == "__main__":
    main()

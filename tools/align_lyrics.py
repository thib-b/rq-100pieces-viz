#!/usr/bin/env python3
"""Forced-align the known lyrics to the master WAV → per-word timestamps.

Uses stable-ts (whisper-based forced alignment of a KNOWN transcript), which is far more
reliable than transcribing sung vocals from scratch since we already have the exact words.

Run with the align venv:
    .venv-align/bin/python tools/align_lyrics.py \
        --audio "/Users/thib/Downloads/Robocobra Quartet - Haha.wav" \
        --lyrics tools/haha_lyrics.txt --model large-v3 --out tools/haha_align_words_large.json
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--lyrics", default="tools/haha_lyrics.txt")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--out", default="tools/haha_align_words_large.json")
    args = ap.parse_args()

    import stable_whisper
    text = Path(args.lyrics).read_text()
    print(f"loading whisper '{args.model}' …")
    model = stable_whisper.load_model(args.model)
    print("aligning …")
    result = model.align(args.audio, text, language="en")

    words = []
    for seg in result.segments:
        for w in seg.words:
            words.append({"word": w.word.strip(), "start": round(float(w.start), 3),
                          "end": round(float(w.end), 3)})
    Path(args.out).write_text(json.dumps(words, indent=1, ensure_ascii=False))
    print(f"wrote {len(words)} words -> {args.out}")
    if words:
        print("first:", words[:6])
        print("last :", words[-4:])


if __name__ == "__main__":
    main()

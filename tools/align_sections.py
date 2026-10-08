#!/usr/bin/env python3
"""Forced-align lyrics section-by-section inside known time windows → per-word timestamps.

A whole-song `align_lyrics.py` pass can drift when a song repeats lines or has long
instrumental gaps (one bad anchor drags everything after it). Here each section of text is
aligned only against its own window of audio, so errors can't propagate. Best run on an
isolated vocal stem (e.g. demucs `--two-stems=vocals`), which removes most instrument bleed.

Sections file: JSON list of {"start": s, "end": s, "text": "...", "note": "..."(optional)}.
A section may instead carry "words": [[word, start, end], ...] — hand-fixed times that skip
alignment (flagged `manual`), for passages the aligner can't resolve (e.g. fast repeats).
A single-word section that aligns with low confidence falls back to the longest voiced stretch
in its window (flagged `from_voice`) when --snap-db is given.

    .venv-align/bin/python tools/align_sections.py --audio vocals.wav \
        --sections tools/nothing_sections.json --out tools/nothing_align_words.json
"""
import argparse
import json
from pathlib import Path

SR = 16000
HOP = 160  # 10 ms analysis frames


def voiced_frames(audio, below_peak_db, hop=HOP):
    """Boolean 10 ms voice-activity mask: frames within `below_peak_db` dB of the loudest."""
    import numpy as np
    n = len(audio) // hop
    rms = np.sqrt(np.mean(audio[:n * hop].reshape(n, hop) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-9)
    return db > db.max() - below_peak_db


def runs(mask, value):
    """[(i, j)) index runs where mask == value."""
    out, i = [], 0
    while i < len(mask):
        if mask[i] == value:
            j = i
            while j < len(mask) and mask[j] == value:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def snap_to_voice(words, voiced, gap=0.25, min_dur=0.08):
    """Whisper tends to start a word at the end of the previous one, swallowing the pause
    between them. If a word's span contains a silence of >= `gap` s, its start moves to just
    after the last such silence; then leading/trailing silent frames are trimmed. Never shrinks
    a word below `min_dur`. Moved words keep their raw times and are flagged `snapped`."""
    f = SR / HOP  # frames per second
    for w in words:
        if w.get("manual"):
            continue
        a, b = int(w["start"] * f), int(w["end"] * f)
        seg = voiced[a:b]
        for i, j in runs(seg, False):
            if (j - i) / f >= gap and j < len(seg):
                a, seg = a + j, voiced[a + j:b]
        idx = [k for k, v in enumerate(seg) if v]
        if not idx:
            continue
        s, e = (a + idx[0]) / f, (a + idx[-1] + 1) / f
        e = min(max(e, s + min_dur), max(w["end"], s + min_dur))
        if abs(s - w["start"]) > 0.02 or abs(e - w["end"]) > 0.02:
            w["raw_start"], w["raw_end"] = w["start"], w["end"]
            w["start"], w["end"], w["snapped"] = round(s, 3), round(e, 3), True


def widen_short(words, voiced, min_dur=0.1, reach=0.3):
    """A word squeezed below `min_dur` (aligner gave it ~nothing) gets its start pulled back
    into the voiced frames before it — up to `reach` s, never past the previous word's start
    plus `min_dur` (that word's end is trimmed to match). Flagged `widened`."""
    f = SR / HOP
    for k, w in enumerate(words):
        if w.get("manual") or w["end"] - w["start"] >= min_dur:
            continue
        prev = words[k - 1] if k else None
        floor = max(w["end"] - reach, prev["start"] + min_dur if prev else 0.0)
        i = int(w["start"] * f)
        while i - 1 >= floor * f and voiced[max(0, i - 15):i].any():  # bridge <150 ms dips
            i -= 1
        s = max(i / f, floor)
        if w["end"] - s > w["end"] - w["start"]:
            w["start"], w["widened"] = round(s, 3), True
            if prev and prev["end"] > w["start"]:
                prev["end"] = w["start"]


def voiced_region(voiced, lo, hi, bridge=0.3):
    """Longest voiced stretch inside [lo, hi] s, bridging silences shorter than `bridge`."""
    f = SR / HOP
    seg = voiced[int(lo * f):int(hi * f)].copy()
    for i, j in runs(seg, False):
        if (j - i) / f < bridge and i > 0 and j < len(seg):
            seg[i:j] = True
    r = max(runs(seg, True), key=lambda ij: ij[1] - ij[0], default=None)
    return None if r is None else (round(lo + r[0] / f, 3), round(lo + r[1] / f, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--sections", required=True)
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--out", required=True)
    ap.add_argument("--snap-db", type=float, default=None,
                    help="trim each word's leading/trailing silence: frames quieter than "
                         "(peak - SNAP_DB) dB count as silence. Use on a vocal stem only.")
    args = ap.parse_args()

    import stable_whisper
    import whisper

    audio = whisper.load_audio(args.audio)  # 16 kHz mono float32
    sections = json.loads(Path(args.sections).read_text())
    print(f"loading whisper '{args.model}' …")
    model = stable_whisper.load_model(args.model)

    voiced = voiced_frames(audio, args.snap_db) if args.snap_db is not None else None
    words = []
    for i, sec in enumerate(sections):
        lo, hi = sec["start"], sec["end"]
        print(f"[{i:2d}] {lo:7.2f}-{hi:7.2f}  {(sec.get('text') or 'manual')[:60]!r}")
        if "words" in sec:
            words += [{"section": i, "word": w, "start": s, "end": e, "prob": None, "manual": True}
                      for w, s, e in sec["words"]]
            continue
        result = model.align(audio[int(lo * SR):int(hi * SR)], sec["text"], language="en")
        sec_words = [{"section": i, "word": w.word.strip(),
                      "start": round(float(w.start) + lo, 3),
                      "end": round(float(w.end) + lo, 3),
                      "prob": round(float(w.probability), 3)}
                     for seg in result.segments for w in seg.words]
        if voiced is not None:
            snap_to_voice(sec_words, voiced)
            if len(sec_words) == 1 and (sec_words[0]["prob"] < 0.3
                                        or sec_words[0]["end"] - sec_words[0]["start"] < 0.15):
                region = voiced_region(voiced, lo, hi)
                if region:
                    sec_words[0].update(start=region[0], end=region[1], from_voice=True)
        words += sec_words
    if voiced is not None:
        widen_short(words, voiced)
    for w, nxt in zip(words, words[1:]):  # no overlaps: a word ends where the next begins
        if w["end"] > nxt["start"] > w["start"]:
            w["end"] = nxt["start"]
    Path(args.out).write_text(json.dumps(words, indent=1, ensure_ascii=False))
    print(f"wrote {len(words)} words -> {args.out}")


if __name__ == "__main__":
    main()

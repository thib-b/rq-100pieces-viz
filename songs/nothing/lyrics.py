"""Word timings for Nothing (from tools/align_sections.py). Pure (no bpy)."""
from __future__ import annotations

import json
from dataclasses import dataclass

from songs.nothing.state import digest
from songs.nothing.timeline import asset


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    phrase: int          # index into tools/nothing_sections.json (the aligned phrase)


class Lyrics:
    def __init__(self, words):
        self.words = tuple(words)

    @classmethod
    def load(cls, path):
        if not path:
            return cls([])
        raw = json.loads(asset(path).read_text())
        return cls(Word(w["word"], float(w["start"]), float(w["end"]), int(w["section"]))
                   for w in raw)

    def between(self, t0, t1):
        """Words that start in [t0, t1)."""
        return [w for w in self.words if t0 <= w.start < t1]

    def slice_hash(self, t0, t1):
        """Hash of the words a section can see — a timing fix elsewhere doesn't invalidate it."""
        return digest([[w.text, w.start, w.end, w.phrase] for w in self.between(t0, t1)])

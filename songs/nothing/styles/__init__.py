"""Animation styles for Nothing. One module per style, registered by name.

A style module provides:

    plan(ctx) -> plan            pure: every position/colour/birth/death, using ctx.rng(...) only
    exit_state(ctx, plan) -> State   pure: what the section's last frame looks like
    build(ctx, plan) -> None     bpy: create objects + keyframes for the section's frames
    assets(ctx) -> [paths]       optional: files the section reads (hashed into its fingerprint)

Rules that make single-section re-renders possible:
  * no global `random` / `np.random` — only ctx.rng(label);
  * frame-pure: the look at frame f depends only on f (keyframes from the plan), never on
    having rendered earlier frames;
  * everything the next section needs goes into exit_state;
  * read inherited state (ctx.enter) only in plan/exit_state/assets — reads there are tracked
    into the fingerprint; build() must work from the plan alone.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from engine import core
from songs.nothing.seeding import section_rng

STYLES_DIR = Path(__file__).resolve().parent


def get(name):
    if not (STYLES_DIR / f"{name}.py").exists() or name.startswith("_"):
        raise KeyError(f"unknown style {name!r}; have {available()}")
    return importlib.import_module(f"songs.nothing.styles.{name}")


def available():
    return sorted(p.stem for p in STYLES_DIR.glob("*.py") if not p.stem.startswith("_"))


def source_path(name):
    return STYLES_DIR / f"{name}.py"


@dataclass(frozen=True)
class Context:
    """Everything a style may look at. Built by manifest.walk()."""
    song: object          # timeline.Song
    section: object       # timeline.Section
    enter: object         # state.State inherited from the previous section
    lyrics: object        # lyrics.Lyrics

    @property
    def params(self):
        return self.section.params

    @property
    def fps(self):
        return self.song.fps

    @property
    def frame_size(self):
        """World (width, height) the orthographic camera sees."""
        w, h = self.song.aspect
        return core.aspect_frame(w, h, self.song.ortho_scale)

    def param(self, key, state_key=None, default=None):
        """This section's param `key`, else the inherited state value (`state_key`, default
        `key`). Only reads ctx.enter when the param is absent, so an overridden value isn't
        tracked as a dependency on the previous section."""
        if key in self.section.params:
            return self.section.params[key]
        return self.enter.get(state_key or key, default)

    def rng(self, *label):
        """Independent random stream for this section (and optional named sub-stream)."""
        return section_rng(self.song.name, self.section.id, self.section.seed, *label)

    def time(self, frame):
        return (frame - 1) / self.song.fps

    def words(self):
        """Lyric words that start inside this section."""
        return self.lyrics.between(self.time(self.section.first), self.time(self.section.last + 1))

"""Load song.toml → a Song with sections tiled over the global frame grid. Pure (no bpy).

Sections are grouped into scenes (`[scene.<id>]` tables + `scene = "<id>"` on each section).
A section may stack `layers = ["style", ...]` over its base `style` (e.g. lyrics over the plate);
layers share the section's params and inherited State, and don't change the State they hand on.
A scene's `params` are defaults for all of its sections (a section's own params win), so a
shared look — palette, visual language — is set once per scene. A scene's sections must be
contiguous.

Frame numbering is global and 1-based, like Blender's: the frame showing time t is
round(t * fps) + 1. A section starting at `start` seconds owns frames from its start frame up
to the frame before the next section's start; the last section runs to the final frame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

try:                                    # Python 3.11+ (Blender's interpreter)
    import tomllib as _toml
except ModuleNotFoundError:             # Python < 3.11 (the test venv)
    import tomli as _toml

REPO = Path(__file__).resolve().parents[2]
SONG_TOML = Path(__file__).resolve().parent / "song.toml"
ASPECTS = {"landscape": (2048, 1152), "vertical": (1152, 2048), "square": (2048, 2048)}


@dataclass(frozen=True)
class Section:
    index: int
    id: str
    style: str
    start_sec: float
    first: int                    # first global frame (inclusive)
    last: int                     # last global frame (inclusive)
    seed: int = 0
    params: dict = field(default_factory=dict)    # scene params merged under section params
    scene: str = ""
    layers: tuple = ()           # extra styles drawn over the base style (e.g. lyrics), in order

    @property
    def frames(self):
        return range(self.first, self.last + 1)

    def entry(self):
        """The section's own config, as hashed into its fingerprint."""
        return {"id": self.id, "style": self.style, "seed": self.seed, "params": self.params,
                "first": self.first, "last": self.last, "scene": self.scene,
                "layers": list(self.layers)}


@dataclass(frozen=True)
class Song:
    name: str
    fps: int
    aspect: tuple
    duration_sec: float
    audio: str
    words: str
    ortho_scale: float
    initial: dict                 # the State the first section starts from
    sections: tuple
    scenes: tuple = ()            # ((id, title), ...) in song order

    @property
    def total_frames(self):
        return math.ceil(self.duration_sec * self.fps - 1e-9)

    def frame_of(self, t):
        return int(round(t * self.fps)) + 1

    def section(self, sid):
        for s in self.sections:
            if s.id == sid:
                return s
        raise KeyError(f"no section {sid!r}; have {[s.id for s in self.sections]}")

    def section_at_frame(self, f):
        for s in self.sections:
            if s.first <= f <= s.last:
                return s
        raise ValueError(f"frame {f} outside 1..{self.total_frames}")


def asset(path):
    """Resolve an asset path: absolute as-is, else relative to the repo root."""
    p = Path(path)
    return p if p.is_absolute() else REPO / p


def from_dict(data):
    fps = int(data["fps"])
    aspect = data.get("aspect", "landscape")
    aspect = tuple(ASPECTS[aspect] if isinstance(aspect, str) else aspect)
    raw = data["section"]
    if not raw or float(raw[0]["start"]) != 0.0:
        raise ValueError("the first section must start at 0")
    ids = [s["id"] for s in raw]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate section ids in {ids}")
    song = Song(name=data["name"], fps=fps, aspect=aspect,
                duration_sec=float(data["duration_sec"]), audio=data.get("audio", ""),
                words=data.get("words", ""), ortho_scale=float(data.get("ortho_scale", 10.0)),
                initial=dict(data.get("initial", {})), sections=())
    firsts = [song.frame_of(float(s["start"])) for s in raw]
    if any(b <= a for a, b in zip(firsts, firsts[1:])):
        raise ValueError("section starts must be strictly increasing (after frame snapping)")
    if firsts[-1] > song.total_frames:
        raise ValueError("last section starts after the song ends")
    scene_defs = data.get("scene", {})
    for sid, sc in scene_defs.items():
        unknown = set(sc) - {"title", "params"}
        if unknown:
            raise ValueError(f"scene {sid!r}: unknown keys {sorted(unknown)}")
    secs = []
    for i, s in enumerate(raw):
        last = firsts[i + 1] - 1 if i + 1 < len(raw) else song.total_frames
        unknown = set(s) - {"id", "style", "start", "seed", "params", "scene", "layers"}
        if unknown:
            raise ValueError(f"section {s['id']!r}: unknown keys {sorted(unknown)}")
        scene = s.get("scene", "")
        if scene and scene not in scene_defs:
            raise ValueError(f"section {s['id']!r}: unknown scene {scene!r}")
        params = {**scene_defs.get(scene, {}).get("params", {}), **s.get("params", {})}
        secs.append(Section(index=i, id=s["id"], style=s["style"], start_sec=float(s["start"]),
                            first=firsts[i], last=last, seed=int(s.get("seed", 0)),
                            params=params, scene=scene, layers=tuple(s.get("layers", ()))))
    order = [k for i, k in enumerate(s.scene for s in secs) if k and (i == 0 or secs[i - 1].scene != k)]
    if len(order) != len(set(order)):
        raise ValueError(f"a scene's sections must be contiguous; got scene order {order}")
    scenes = tuple((k, scene_defs[k].get("title", k)) for k in order)
    return Song(**{**song.__dict__, "sections": tuple(secs), "scenes": scenes})


def load(path=SONG_TOML):
    with open(path, "rb") as f:
        return from_dict(_toml.load(f))

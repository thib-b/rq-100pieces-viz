"""Recipe: the per-song config that drives a render.

A recipe is a small TOML file (see recipes/*.toml). It names a treatment, the plate/stamp
image, the aspect ratio, the length, and the tuning knobs — everything that used to be a
copy-pasted constant block. Loading merges the file over sensible per-treatment defaults,
so a recipe only needs to state what differs.

Treatments:
  reveal        blooms grow to reconstruct the artwork, then dissolve to reveal the photo
  bloom_overlay blooms grow to reconstruct the artwork on a transparent film, then hold
  stamp         the stamp letterforms draw themselves in on a transparent film
  stamp_blooms  the stamp draws in with blooms growing everywhere around it (on orange)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:                                    # Python 3.11+ (Blender's interpreter)
    import tomllib as _toml
except ModuleNotFoundError:             # Python < 3.11 (the test venv)
    import tomli as _toml


ASPECT_PRESETS = {
    "landscape": (2048, 1152),          # 16:9
    "vertical":  (1152, 2048),          # 9:16
    "square":    (2048, 2048),          # 1:1
}

# Phase boundaries/spans as fractions of the total frame count, taken from the legacy
# scripts. Because they are fractions, a recipe's duration reflows them proportionally.
DEFAULT_TIMELINE = {
    "reveal": {          # haha_reveal.py (193s @ 60fps = 11580 frames)
        "mould_end":    6900 / 11580,   # full coverage (1:55)
        "hold_end":     8100 / 11580,   # held still until (2:15)
        "dissolve_end": 10860 / 11580,  # all blooms gone, photo revealed (3:01)
        "bloom_grow":   300 / 11580,    # frames one bloom takes to grow in
        "bloom_fade":   180 / 11580,    # frames one bloom takes to fade out
    },
    "bloom_overlay": {   # haha_bloom_overlay.py (5s: 3s grow + 2s hold)
        "mould_end":  3 / 5,
        "bloom_grow": 60 / 300,
    },
    "stamp": {           # stamp_overlay.py (5s draw-in)
        "reveal_frames": 240 / 300,
        "stamp_grow":    60 / 300,
        "stamp_bucket":  15 / 300,
    },
    "stamp_blooms": {    # slime_mold_reveal.py (193s)
        "reveal_frames": 11100 / 11580,  # 185s
        "stamp_grow":    300 / 11580,
        "stamp_bucket":  75 / 11580,
        "bloom_grow":    480 / 11580,
    },
}

TREATMENTS = set(DEFAULT_TIMELINE)

# Legacy defaults that differ per treatment (bloom size, background, palette, encode).
TREATMENT_DEFAULTS = {
    "reveal":        dict(background="grey", n_bloom=2400, bloom_diam=(0.24, 0.60),
                          lobe_seg=20, encode="mp4"),
    "bloom_overlay": dict(background="transparent", n_bloom=2400, bloom_diam=(0.24, 0.60),
                          lobe_seg=20, encode="mov"),
    "stamp":         dict(background="transparent", encode="mov"),
    "stamp_blooms":  dict(background="orange", n_bloom=130, bloom_diam=(0.42, 0.96),
                          lobe_seg=22, encode="none",
                          bloom_palette_whites=("#f4f3ee", "#eae6da", "#f2eee6"),
                          bloom_palette_darks=("#1c1b17", "#262521", "#2f3a26",
                                               "#241f1b", "#1f302e", "#33322c"),
                          vein_hex="#f4f3ee"),
}


@dataclass
class Recipe:
    name: str
    treatment: str
    # assets
    art: str = ""                 # bloom family: image that is sampled and later revealed
    stamp_image: str = ""         # stamp family: alpha-mask PNG of the stamp
    # format
    aspect: tuple = (2048, 1152)
    fps: int = 60
    duration_sec: float = 193.0
    ortho_scale: float = 10.0
    plate_frac: float = 0.88
    plate_fit: str = "short"
    background: str = "grey"      # grey | transparent | orange
    orange_hex: str = "#e8743f"
    # blooms
    n_bloom: int = 2400
    bloom_diam: tuple = (0.24, 0.60)
    bloom_appear_exp: float = 0.4
    n_swatch: int = 30
    lobe_seg: int = 20
    bloom_palette_whites: tuple = ()
    bloom_palette_darks: tuple = ()
    # stamp
    stamp_height_frac: float = 0.70
    stamp_ease: float = 0.40
    grid: int = 480
    alpha_thresh: float = 0.35
    fil_cap: int = 3200
    bevel: float = 0.013
    vein_hex: str = "#f4f3ee"
    # reveal image sample grid
    img_grid: int = 700
    # timeline (fractions of total frames); filled from DEFAULT_TIMELINE if omitted
    timeline: dict = field(default_factory=dict)
    # encode / output
    encode: str = "mp4"           # mp4 | mov | none
    output_name: str = ""
    preview_count: int = 30

    @property
    def total_frames(self):
        return int(round(self.duration_sec * self.fps))

    def __post_init__(self):
        if self.treatment not in TREATMENTS:
            raise ValueError(
                f"unknown treatment {self.treatment!r}; choose one of {sorted(TREATMENTS)}")
        self.aspect = tuple(self.aspect)
        self.bloom_diam = tuple(self.bloom_diam)
        self.bloom_palette_whites = tuple(self.bloom_palette_whites)
        self.bloom_palette_darks = tuple(self.bloom_palette_darks)
        # fill in any timeline keys the recipe did not override
        merged = dict(DEFAULT_TIMELINE[self.treatment])
        merged.update(self.timeline or {})
        self.timeline = merged
        if not self.output_name:
            self.output_name = self.name


def _resolve_aspect(value):
    if isinstance(value, str):
        if value not in ASPECT_PRESETS:
            raise ValueError(f"unknown aspect preset {value!r}; "
                             f"choose from {sorted(ASPECT_PRESETS)} or give [width, height]")
        return ASPECT_PRESETS[value]
    if isinstance(value, dict):
        return (int(value["width"]), int(value["height"]))
    return (int(value[0]), int(value[1]))       # [w, h] list


def from_dict(data):
    """Build a Recipe from a plain dict (as parsed from TOML), applying treatment defaults."""
    data = dict(data)
    treatment = data.get("treatment")
    if treatment not in TREATMENTS:
        raise ValueError(
            f"recipe needs a valid treatment; got {treatment!r}, "
            f"choose one of {sorted(TREATMENTS)}")
    merged = dict(TREATMENT_DEFAULTS.get(treatment, {}))
    merged.update(data)                          # explicit recipe values win
    if "aspect" in merged:
        merged["aspect"] = _resolve_aspect(merged["aspect"])
    known = Recipe.__dataclass_fields__
    unknown = set(merged) - set(known)
    if unknown:
        raise ValueError(f"unknown recipe keys: {sorted(unknown)}")
    return Recipe(**merged)


def load(path):
    """Load a recipe from a TOML file."""
    path = Path(path)
    with open(path, "rb") as f:
        data = _toml.load(f)
    data.setdefault("name", path.stem)
    return from_dict(data)

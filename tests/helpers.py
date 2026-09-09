"""Shared test helpers for the 100 Pieces render pipeline.

Pure-python (no bpy): safe to import under the plain venv interpreter. The golden
tests shell out to Blender as a subprocess and compare downsampled thumbnails, because
EEVEE PNG output is not byte-reproducible run-to-run (sub-pixel/metadata jitter) but is
identical once downsampled to a small thumbnail.
"""
import glob
import importlib.util
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
ANIM = REPO / "animations"
ENGINE_ENTRY = REPO / "100pieces.py"
GOLDEN = Path(__file__).resolve().parent / "golden"
BLENDER = os.environ.get("BLENDER_BIN", "/opt/homebrew/bin/blender")

# Comparison config. Run-to-run noise at 32x32 measured ~0.0; a different frame ~90.
THUMB = 32
TOL = 2.0  # mean-abs-diff on a 0-255 scale at 32x32

# The five legacy treatments (name, script, extra CLI args, expected (width, height)).
# The expected dimensions are the aspect-ratio guard: 16:9, 9:16, and 1:1.
TREATMENTS = [
    ("haha_reveal",          "haha_reveal.py",          (),                    (2048, 1152)),
    ("haha_reveal_vertical", "haha_reveal_vertical.py", (),                    (1152, 2048)),
    ("haha_bloom_overlay",   "haha_bloom_overlay.py",   (),                    (2048, 2048)),
    ("slime_mold_reveal",    "slime_mold_reveal.py",    (),                    (2048, 1152)),
    ("stamp_overlay_black",  "stamp_overlay.py",        ("--color", "black"),  (2048, 2048)),
    ("stamp_overlay_white",  "stamp_overlay.py",        ("--color", "white"),  (2048, 2048)),
]

# The recipe-engine treatments (name, recipe file, expected (width, height)). One recipe
# per legacy treatment, driven through the single 100pieces.py engine.
RECIPES = [
    ("haha_landscape",     "recipes/haha_landscape.toml",     (2048, 1152)),
    ("haha_vertical",      "recipes/haha_vertical.toml",      (1152, 2048)),
    ("haha_bloom_overlay", "recipes/haha_bloom_overlay.toml", (2048, 2048)),
    ("stamp_white",        "recipes/stamp_white.toml",        (2048, 2048)),
    ("stamp_black",        "recipes/stamp_black.toml",        (2048, 2048)),
    ("stamp_blooms",       "recipes/stamp_blooms.toml",       (2048, 1152)),
]


def blender_available():
    return Path(BLENDER).exists()


def render_last_frame(script, out_dir, extra_args=()):
    """Render a single final frame via `blender --background ... -- --last`.

    Returns (CompletedProcess, Path-to-png-or-None).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [BLENDER, "--background", "--python", str(ANIM / script), "--",
           "--last", "--output", str(out_dir), *extra_args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    pngs = sorted(glob.glob(str(out_dir / "last_frame*.png")))
    return proc, (Path(pngs[0]) if pngs else None)


def render_recipe_last(recipe_rel, out_dir):
    """Render a recipe's final frame via `100pieces.py -- --recipe ... --last`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [BLENDER, "--background", "--python", str(ENGINE_ENTRY), "--",
           "--recipe", str(REPO / recipe_rel), "--last", "--output", str(out_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    pngs = sorted(glob.glob(str(out_dir / "last_frame*.png")))
    return proc, (Path(pngs[0]) if pngs else None)


def thumb(path, n=THUMB):
    """Downsample an image to an n x n RGB float array (washes out EEVEE jitter)."""
    im = Image.open(path).convert("RGB").resize((n, n))
    return np.asarray(im, dtype=np.float64)


def mean_abs_diff(a, b):
    return float(np.abs(a - b).mean())


def load_module_from(path, name):
    """Import a standalone .py file as a module (used for the bpy-free make_short.py)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

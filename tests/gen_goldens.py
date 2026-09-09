"""Regenerate the committed golden thumbnails for the legacy treatments.

    .venv/bin/python tests/gen_goldens.py

Renders one --last frame per treatment via Blender and saves a 128x128 PNG under
tests/golden/. Only run this deliberately when the treatments' intended look changes;
the golden is the reference the characterization tests compare against.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image
from helpers import (GOLDEN, RECIPES, TREATMENTS, blender_available,
                     render_last_frame, render_recipe_last)


def _save(png, dims, golden_name):
    got = Image.open(png).size
    if got != dims:
        raise SystemExit(f"{golden_name}: rendered {got}, expected {dims}")
    Image.open(png).convert("RGB").resize((128, 128)).save(GOLDEN / f"{golden_name}.png")
    print(f"wrote golden {golden_name}.png  (source {got})")


def main():
    if not blender_available():
        raise SystemExit("Blender binary not found (set BLENDER_BIN).")
    GOLDEN.mkdir(parents=True, exist_ok=True)
    scratch = Path(__file__).resolve().parent / "_scratch" / "gen"
    for name, script, extra, dims in TREATMENTS:
        proc, png = render_last_frame(script, scratch / name, extra)
        if proc.returncode != 0 or png is None:
            raise SystemExit(f"render failed for {name}:\n{proc.stdout[-1500:]}")
        _save(png, dims, name)
    for name, recipe_rel, dims in RECIPES:
        proc, png = render_recipe_last(recipe_rel, scratch / f"recipe_{name}")
        if proc.returncode != 0 or png is None:
            raise SystemExit(f"recipe render failed for {name}:\n{proc.stdout[-1500:]}")
        _save(png, dims, f"recipe_{name}")


if __name__ == "__main__":
    main()

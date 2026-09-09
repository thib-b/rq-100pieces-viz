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
from helpers import GOLDEN, TREATMENTS, blender_available, render_last_frame


def main():
    if not blender_available():
        raise SystemExit("Blender binary not found (set BLENDER_BIN).")
    GOLDEN.mkdir(parents=True, exist_ok=True)
    scratch = Path(__file__).resolve().parent / "_scratch" / "gen"
    for name, script, extra, dims in TREATMENTS:
        out = scratch / name
        proc, png = render_last_frame(script, out, extra)
        if proc.returncode != 0 or png is None:
            raise SystemExit(f"render failed for {name}:\n{proc.stdout[-1500:]}")
        got = Image.open(png).size
        if got != dims:
            raise SystemExit(f"{name}: rendered {got}, expected {dims}")
        Image.open(png).convert("RGB").resize((128, 128)).save(GOLDEN / f"{name}.png")
        print(f"wrote golden {name}.png  (source {got})")


if __name__ == "__main__":
    main()

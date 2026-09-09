"""Golden tests for the recipe engine (100pieces.py).

One recipe per legacy treatment, each rendered through the single engine. Asserts the
engine exits 0, produces the recipe's declared resolution (the aspect-ratio parameter
works), and matches its committed golden thumbnail. The engine keeps its OWN baseline —
its RNG order need not pixel-match the legacy scripts — while the legacy goldens
(test_golden_legacy.py) independently prove the untouched artifacts still render.
"""
import pytest
from PIL import Image

from helpers import (GOLDEN, RECIPES, TOL, blender_available, mean_abs_diff,
                     render_recipe_last, thumb)

requires_blender = pytest.mark.skipif(
    not blender_available(), reason="Blender binary not found (set BLENDER_BIN)")


@requires_blender
@pytest.mark.blender
@pytest.mark.parametrize("name,recipe_rel,dims", RECIPES, ids=[r[0] for r in RECIPES])
def test_recipe_golden(name, recipe_rel, dims, tmp_path):
    proc, png = render_recipe_last(recipe_rel, tmp_path)
    assert proc.returncode == 0, (
        f"engine failed for {name}\nSTDOUT tail:\n{proc.stdout[-1500:]}\n"
        f"STDERR tail:\n{proc.stderr[-1500:]}")
    assert png is not None, f"{name}: no last_frame*.png written to {tmp_path}"

    assert Image.open(png).size == dims, (
        f"{name}: rendered {Image.open(png).size}, expected {dims} "
        f"(aspect-ratio parameter regression)")

    golden = GOLDEN / f"recipe_{name}.png"
    assert golden.exists(), (
        f"missing golden {golden}; run `.venv/bin/python tests/gen_goldens.py`")
    d = mean_abs_diff(thumb(png), thumb(golden))
    assert d < TOL, (
        f"{name}: content drifted from golden (mean-abs-diff {d:.2f} >= {TOL})")

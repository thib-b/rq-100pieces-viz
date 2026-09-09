"""Golden characterization tests for the legacy render treatments.

For each treatment we render one final frame (`--last`, ~1-3s) via Blender and assert:
  1. Blender exits 0.
  2. The output resolution is exactly right  -> guards the aspect-ratio behavior.
  3. The frame matches a committed golden thumbnail within tolerance -> guards the
     visual content, which is driven by the load-bearing RNG call order.

These run on the CURRENT scripts before the refactor and must keep passing after it,
proving the historical artifacts were not disturbed. Regenerate goldens with
`.venv/bin/python tests/gen_goldens.py`.
"""
import pytest
from PIL import Image

from helpers import (GOLDEN, TOL, TREATMENTS, blender_available,
                     mean_abs_diff, render_last_frame, thumb)

requires_blender = pytest.mark.skipif(
    not blender_available(), reason="Blender binary not found (set BLENDER_BIN)")


@requires_blender
@pytest.mark.blender
@pytest.mark.parametrize("name,script,extra,dims", TREATMENTS,
                         ids=[t[0] for t in TREATMENTS])
def test_legacy_treatment_golden(name, script, extra, dims, tmp_path):
    proc, png = render_last_frame(script, tmp_path, extra)
    assert proc.returncode == 0, (
        f"blender failed for {name}\nSTDOUT tail:\n{proc.stdout[-1500:]}\n"
        f"STDERR tail:\n{proc.stderr[-1500:]}")
    assert png is not None, f"{name}: no last_frame*.png written to {tmp_path}"

    assert Image.open(png).size == dims, (
        f"{name}: rendered {Image.open(png).size}, expected {dims} "
        f"(aspect-ratio regression)")

    golden = GOLDEN / f"{name}.png"
    assert golden.exists(), (
        f"missing golden {golden}; run `.venv/bin/python tests/gen_goldens.py`")
    d = mean_abs_diff(thumb(png), thumb(golden))
    assert d < TOL, (
        f"{name}: content drifted from golden (mean-abs-diff {d:.2f} >= {TOL})")

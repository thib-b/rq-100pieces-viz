"""Unit tests for engine.plate — the bpy-free image analysis (dish detection, seeding,
palette quantisation, stamp vein walk) on small synthetic arrays."""
import math

import numpy as np
import pytest

from engine import plate


def _disc_image(grid=200, cx=100, cy=100, r=40, grey=0.6):
    """Grey field with a red disc — a stand-in for the grey background + petri dish."""
    arr = np.full((grid, grid, 3), grey, dtype=np.float64)
    yy, xx = np.mgrid[0:grid, 0:grid]
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= r ** 2
    arr[inside] = np.array([0.85, 0.2, 0.15])
    return arr


def test_resample_grid_shape():
    px = np.random.rand(100, 80, 3)
    out = plate.resample_grid(px, 32)
    assert out.shape == (32, 32, 3)


def test_mask_from_alpha_shape_and_threshold():
    alpha = np.zeros((100, 100), dtype=np.float64)
    alpha[40:60, 40:60] = 1.0
    mask = plate.mask_from_alpha(alpha, 50, 0.35)
    assert mask.shape == (50, 50)
    assert mask.dtype == bool and mask.any()


def test_detect_plate_finds_centre_and_radius():
    arr = _disc_image(grid=200, cx=100, cy=100, r=40)
    grey, cx, cy, r = plate.detect_plate(arr)
    assert grey == pytest.approx([0.6, 0.6, 0.6], abs=1e-6)
    assert cx == pytest.approx(100, abs=3)
    assert cy == pytest.approx(100, abs=3)
    # area-based radius ~ true radius * 1.02
    assert r == pytest.approx(40 * 1.02, rel=0.15)


def test_estimate_agar_returns_finite_rgb():
    arr = _disc_image()
    _, cx, cy, r = plate.detect_plate(arr)
    edge, core_ = plate.estimate_agar(arr, cx, cy, r)
    assert edge.shape == (3,) and core_.shape == (3,)
    assert np.isfinite(edge).all() and np.isfinite(core_).all()


def test_seed_mould_stays_inside_disc():
    arr = _disc_image(grid=120, cx=60, cy=60, r=30)
    _grey, cx, cy, r = plate.detect_plate(arr)
    edge, _core = plate.estimate_agar(arr, cx, cy, r)
    rng = np.random.RandomState(42)
    rows, cols, colors = plate.seed_mould(arr, edge, cx, cy, r, 200, rng)
    assert len(rows) == len(cols) == len(colors) == 200
    d = np.sqrt((cols - cx) ** 2 + (rows - cy) ** 2)
    assert (d <= r).all()          # every seed lands on the disc


def test_quantise_reduces_palette():
    rng = np.random.RandomState(0)
    colors = rng.rand(500, 3)
    reps, assign = plate.quantise(colors, 8)
    assert reps.shape[0] <= 8 and reps.shape[1] == 3
    assert assign.shape == (500,)
    assert assign.min() >= 0 and assign.max() < reps.shape[0]


def test_edge_points_of_filled_block():
    mask = np.zeros((5, 5), dtype=bool)
    mask[1:4, 1:4] = True          # a 3x3 block; only its centre is fully surrounded
    edges = plate.edge_points(mask)
    assert len(edges) == 8         # 9 cells minus the 1 interior cell


def test_simulate_stamp_walks_inside_mask():
    mask = np.zeros((60, 60), dtype=bool)
    mask[10:50, 10:50] = True
    edges = plate.edge_points(mask)
    import random
    fils = plate.simulate_stamp(mask, edges, 20, random.Random(42))
    assert len(fils) > 0
    for pts in fils:
        assert len(pts) >= 2
        for x, y in pts:
            assert 0 <= int(x) < 60 and 0 <= int(y) < 60


def test_taper_radii_monotonic():
    r = plate.taper_radii(5)
    assert r[0] == 1.0 and r[-1] == pytest.approx(0.22)
    assert all(a >= b for a, b in zip(r, r[1:]))

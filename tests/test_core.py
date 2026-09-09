"""Unit tests for engine.core — colour, aspect-ratio math, and the warp/timeline mapping."""
import numpy as np
import pytest

from engine import core


def test_srgb_to_linear_endpoints():
    assert core.srgb_to_linear(0.0) == 0.0
    assert core.srgb_to_linear(1.0) == pytest.approx(1.0)
    assert core.srgb_to_linear(0.5) == pytest.approx(0.21404114, rel=1e-4)


def test_hex_lin_white_and_black():
    assert core.hex_lin("#000000") == (0.0, 0.0, 0.0, 1.0)
    assert core.hex_lin("#ffffff") == pytest.approx((1.0, 1.0, 1.0, 1.0))


def test_smootherstep_floor_and_ceiling():
    assert core.smootherstep(0.0) == pytest.approx(0.04)   # never exactly 0 (clean grow-in)
    assert core.smootherstep(1.0) == pytest.approx(1.0)


def test_aspect_frame_three_ratios():
    assert core.aspect_frame(2048, 1152, 10.0) == pytest.approx((10.0, 5.625))
    assert core.aspect_frame(1152, 2048, 10.0)[1] == pytest.approx(10.0 * 2048 / 1152)
    assert core.aspect_frame(2048, 2048, 10.0) == pytest.approx((10.0, 10.0))


def test_plate_radius_short_fit_matches_all_legacy_cases():
    # landscape: short side is height 5.625 -> matches legacy PLATE_FRAC*frame_h/2
    fw, fh = core.aspect_frame(2048, 1152, 10.0)
    assert core.plate_radius(fw, fh, 0.88, "short") == pytest.approx(0.88 * 5.625 / 2)
    # vertical: short side is width 10 -> matches legacy min(w,h)/2
    fw, fh = core.aspect_frame(1152, 2048, 10.0)
    assert core.plate_radius(fw, fh, 0.88, "short") == pytest.approx(0.88 * 10.0 / 2)
    # square: both 10 -> 4.4
    fw, fh = core.aspect_frame(2048, 2048, 10.0)
    assert core.plate_radius(fw, fh, 0.88, "short") == pytest.approx(0.88 * 10.0 / 2)


def test_total_frames():
    assert core.total_frames(193, 60) == 11580
    assert core.total_frames(30, 60) == 1800


def test_resolve_timeline_reproduces_legacy_absolute_frames():
    fracs = {"mould_end": 6900 / 11580, "hold_end": 8100 / 11580,
             "dissolve_end": 10860 / 11580, "bloom_grow": 300 / 11580}
    got = core.resolve_timeline(11580, fracs)
    assert got == {"mould_end": 6900, "hold_end": 8100,
                   "dissolve_end": 10860, "bloom_grow": 300}


def test_resolve_timeline_warps_proportionally_to_end_length():
    # Same phase fractions, half the length -> every boundary halves (uniform time-warp).
    fracs = {"mould_end": 6900 / 11580, "dissolve_end": 10860 / 11580}
    full = core.resolve_timeline(11580, fracs)
    half = core.resolve_timeline(5790, fracs)
    for k in fracs:
        assert half[k] == pytest.approx(full[k] / 2, abs=1)


def test_resolve_timeline_floors_at_one():
    assert core.resolve_timeline(10, {"x": 0.0})["x"] == 1


def test_pick_even_matches_make_short_contract():
    assert core.pick_even(5, 10) == [0, 1, 2, 3, 4]
    assert core.pick_even(100, 1) == [0]
    picks = core.pick_even(11580, 1800)
    assert len(picks) == 1800 and picks[0] == 0 and picks[-1] == 11579

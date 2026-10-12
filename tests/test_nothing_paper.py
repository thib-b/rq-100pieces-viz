"""The paper: the landing view of the plate, breathing slowly from rest."""
import math

import pytest

from songs.nothing import cues, paper
from songs.nothing.styles import plate_ratchet as pr

FS = (10.0, 5.625)


def test_paper_is_still_until_the_landing_and_leaves_it_at_rest():
    tl = cues.scene1()["landing"]
    assert paper.breath(tl - 5) == (1.0, 0.0, 0.0)
    assert paper.breath(tl) == (1.0, 0.0, 0.0)
    s, dx, dy = paper.breath(tl + 1 / 60)                   # one frame later: barely moved
    assert abs(s - 1) < 1e-4 and abs(dx) < 1e-4 and abs(dy) < 1e-4


def test_breath_is_slow_and_gentle():
    tl = cues.scene1()["landing"]
    b = paper.BREATH
    for k in range(1, 6000):
        t = tl + k / 60
        s, dx, dy = paper.breath(t)
        assert 1.0 <= s <= 1 + b["zoom"] + 1e-12            # only ever zooms in a little
        assert math.hypot(dx, dy) <= 2 * b["drift"]
        s2, dx2, dy2 = paper.breath(t + 1 / 60)
        assert abs(s2 - s) < 3e-4 and math.hypot(dx2 - dx, dy2 - dy) < 2e-3   # per frame


def test_landing_pose_is_the_ratchet_view_seen_from_the_origin():
    """A photo point at the ratchet camera centre lands on the frame centre, scaled by m."""
    P = pr.DEFAULTS
    tl = cues.scene1()["landing"]
    x, y, side, rot = paper.landing_pose(FS)
    m = pr.magnification(tl)
    rw = 0.5 * P["start_dish_frac"] * FS[1]
    cx, cy = pr.camera_center(tl, rw)
    assert (cx * m + x, cy * m + y) == pytest.approx((0.0, 0.0), abs=1e-9)
    assert side == pytest.approx(rw / P["dish_radius_uv"] * m)
    assert rot == pytest.approx(-math.radians(pr.ratchet_angle(tl)))

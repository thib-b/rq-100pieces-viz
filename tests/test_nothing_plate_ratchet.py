"""Pure motion tests for scene 1's plate (ratchet rotation, zoom, fall into the puff)."""
import math

import pytest

from songs.nothing import cues
from songs.nothing.styles import plate_ratchet as pr

P = pr.DEFAULTS
FPS = 60


def test_still_until_first_move_then_lands_each_step_on_a_kick():
    s = cues.scene1()
    assert pr.ratchet_angle(0.0) == 0.0
    assert pr.ratchet_angle(s["ratchet_first_move"]) == 0.0
    for i, t in enumerate(cues.ratchet_landings()):
        # at the landing instant the step is complete: exactly (i+1) steps
        assert pr.ratchet_angle(t) == pytest.approx(P["step_deg"] * (i + 1), abs=1e-3)


def test_each_step_accelerates_then_overshoots_and_settles():
    land = cues.ratchet_landings()
    a, b = land[3], land[4]                      # one full step between two landings
    ts = [a + (b - a) * k / 60 for k in range(61)]
    ang = [pr.ratchet_angle(t) for t in ts]
    settle = P["settle_sixteenths"] * cues.sixteenth()
    # overshoot right after the landing at a: angle exceeds the landed value, then returns
    peak = max(pr.ratchet_angle(a + settle * v) for v in (0.2, 0.3, 0.4))
    assert peak > pr.ratchet_angle(a) + 0.3
    # after settling, the ease-in accelerates: later increments are larger than earlier ones
    after = [t for t in ts if t > a + settle]
    d = [pr.ratchet_angle(y) - pr.ratchet_angle(x) for x, y in zip(after, after[1:])]
    assert d[-1] > 3 * d[1] > 0


def test_rotation_is_clockwise_and_holds_after_last_landing():
    s = cues.scene1()
    total = P["step_deg"] * len(cues.ratchet_landings())
    assert total == pytest.approx(855.0)
    late = s["ratchet_last_land"] + 1.0
    assert pr.ratchet_angle(late) == pytest.approx(total)


def test_zoom_is_imperceptible_then_dish_still_on_screen_at_accel_start():
    s = cues.scene1()
    m_acc = pr.magnification(s["zoom_accel_start"])
    assert m_acc == pytest.approx(P["accel_dish_frac"] / P["start_dish_frac"])
    assert P["start_dish_frac"] * m_acc < 1.0            # dish diameter < frame height at 1:34
    # per-second zoom in the creep phase is tiny (< 0.5% / s)
    assert pr.magnification(60.0) / pr.magnification(59.0) < 1.005


def test_fall_accelerates_and_lands_inside_the_puff():
    s = cues.scene1()
    ta, tl = s["zoom_accel_start"], s["landing"]
    ms = [pr.magnification(ta + (tl - ta) * k / 10) for k in range(11)]
    rates = [math.log(b / a) for a, b in zip(ms, ms[1:])]
    assert all(r2 > r1 for r1, r2 in zip(rates, rates[1:]))     # ever faster
    frame_h_in_radii = 2 / (P["start_dish_frac"] * ms[-1])
    assert frame_h_in_radii == pytest.approx(P["land_view_radii"])


def test_camera_is_continuous_and_ends_centred_on_the_puff():
    s = cues.scene1()
    ta, tl = s["zoom_accel_start"], s["landing"]
    rw = 1.0
    assert pr.camera_center(ta, rw) == (0.0, 0.0)
    # continuity frame to frame through the fall (no jumps)
    prev = pr.camera_center(ta, rw)
    for k in range(1, int((tl - ta) * FPS) + 1):
        cur = pr.camera_center(ta + k / FPS, rw)
        assert math.dist(prev, cur) < 0.05 * rw
        prev = cur
    # at the landing the camera sits exactly on the rotated puff
    th = -math.radians(pr.ratchet_angle(tl))
    dx, dy = P["target"][0], -P["target"][1]
    expect = (dx * math.cos(th) - dy * math.sin(th), dx * math.sin(th) + dy * math.cos(th))
    assert pr.camera_center(tl, rw) == pytest.approx(expect, abs=1e-9)


def test_scene1_plate_hands_on_blank_white_at_the_landing():
    from songs.nothing import manifest, timeline
    runs = {r.section.id: r for r in manifest.walk(timeline.load())}
    assert runs["exposition"].exit["mode"] == "plate"
    ex = runs["first_bridge"].exit
    assert (ex["mode"], ex["background"], ex["image"]) == ("blank", "#ffffff", "")

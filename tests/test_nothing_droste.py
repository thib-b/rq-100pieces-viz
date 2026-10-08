"""Pure tests for the Droste plate zoom."""
import cmath
import math

import pytest

from songs.nothing import cues, manifest, timeline
from songs.nothing.styles import droste_zoom as dz

P = dz.DEFAULTS
TB = cues.raw()["scene3"]["bass_entry"]


def by_level(t):
    return {a: (xy, s, rot) for a, xy, s, rot, _, _ in dz.instances(t, P)}


def test_still_before_the_bass_and_identical_to_the_grown_plate():
    inst = dz.instances(TB - 1.0, P)
    lv0 = [(a, xy, s, rot, g) for a, xy, s, rot, _, g in inst if a == 0]
    assert lv0 == [(0, (0.0, 0.0), 1.0, 0.0, 1.0)]
    assert all(g == 0.0 for a, _, _, _, _, g in inst if a >= 1)    # nested plates not grown yet


def test_each_nested_plate_grows_before_we_reach_it():
    for a in (1, 2, 5):
        gs = [dz.level_grow(a, a - 1 + x / 100, P) for x in range(0, 101)]
        assert gs == sorted(gs) and gs[0] == 0.0
        assert dz.level_grow(a, a - 1 + P["grow_levels"], P) == 1.0   # done when λ reaches a
        steps = [b - a_ for a_, b in zip(gs, gs[1:])]
        assert max(steps) == pytest.approx(min(steps))         # grows at a steady rate
    assert dz.level_grow(0, 0.0, P) == 1.0


def test_organisms_grow_in_order_biggest_colonies_first():
    from songs.nothing import colonies
    t0 = colonies.thresholds()
    d = colonies.data()
    assert min(t0) == pytest.approx(0.2) and max(t0) == pytest.approx(0.78)
    gaps = [b - a for a, b in zip(sorted(t0), sorted(t0)[1:])]
    assert max(gaps) == pytest.approx(min(gaps))               # evenly spaced: a steady rate
    assert max(t0) + P["bloom_soft"] <= 1.0 + 1e-9              # all grown when the plate is
    big = max(d["clusters"], key=lambda c: c["area"])["id"]
    small = min(d["clusters"], key=lambda c: c["area"])["id"]
    first_big = min(t for t, s in zip(t0, d["seeds"]) if s["cluster"] == big)
    first_small = min((t for t, s in zip(t0, d["seeds"]) if s["cluster"] == small), default=1.0)
    assert first_big < first_small


def test_level_is_continuous_and_reaches_steady_rate():
    rate = 1 / (P["bars_per_level"] * cues.bar())
    ts = [TB + i * 0.05 for i in range(2000)]
    lam = [dz.level(t, P) for t in ts]
    assert all(b >= a for a, b in zip(lam, lam[1:]))
    assert max(b - a for a, b in zip(lam, lam[1:])) <= rate * 0.05 + 1e-9
    late = TB + 20
    assert (dz.level(late + 1, P) - dz.level(late, P)) == pytest.approx(rate)


@pytest.mark.parametrize("when", ["bass", "strings"])
def test_crossing_a_whole_level_is_seamless(when):
    # find the moment λ crosses an integer, well after the ramps, and compare both sides
    t0 = TB + 30 if when == "bass" else P["strings_start"] + 30
    lam0 = dz.level(t0, P)
    target = math.ceil(lam0)
    lo, hi = t0, t0 + 20
    for _ in range(60):                              # bisect for λ(t) = integer
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if dz.level(mid, P) < target else (lo, mid)
    a, b = by_level(lo - 1e-7), by_level(hi + 1e-7)
    common = set(a) & set(b)
    assert len(common) >= 3
    for lv in common:
        (xa, ya), sa, ra = a[lv]
        (xb, yb), sb, rb = b[lv]
        # a level's on-screen size/position/rotation must not jump at the wrap
        assert sb == pytest.approx(sa, rel=1e-4)
        assert (xb, yb) == pytest.approx((xa, ya), abs=1e-4 * max(1, sa))
        assert math.remainder(rb - ra, 2 * math.pi) == pytest.approx(0, abs=1e-4)


def test_fixed_point_is_fixed():
    for ph in (0.0, 0.3):
        F = dz.fixed_point(ph, P)
        v = complex(*P["target"])
        assert v + cmath.exp(1j * ph) * F / P["k"] == pytest.approx(F)


def test_matches_sections_and_ends_black():
    song = timeline.load()
    assert P["strings_start"] == pytest.approx(song.section("strings_outro").start_sec)
    assert P["fade_start"] == pytest.approx(song.section("end_resonance").start_sec)
    runs = {r.section.id: r for r in manifest.walk(song)}
    assert runs["end_resonance"].plan["fade"][-1] == pytest.approx(1.0)
    assert runs["outro_bass"].plan["fade"][0] == 0.0


def outermost_visible(t, ancestors):
    """Is the screen fully inside the dish of the outermost KEPT level's child — i.e. would
    the level beyond the kept ancestors be hidden? (Screen in units of the current dish.)"""
    R = 0.5 * P["dish_frac"]                         # dish radius / frame height
    hw, hh = (2048 / 1152) / 2 / R, 0.5 / R
    lam = dz.level(t, P)
    rows = {a: (xy, s) for a, xy, s, *_ in dz.instances(t, P)}
    n = math.floor(lam)
    edge = n - ancestors                             # the outermost kept level must cover the screen
    if edge <= 0 or edge not in rows:
        return True                                  # level 0 sits on black: nothing behind it
    (cx, cy), s = rows[edge]
    reach = 0.9 * s                                  # agar reach, minus its soft rim
    return all(math.hypot(x - cx, y - cy) < reach for x in (-hw, hw) for y in (-hh, hh))


def test_ancestors_kept_cover_everything_behind():
    ts = [TB + i * 0.02 for i in range(int(105 / 0.02))]
    assert all(outermost_visible(t, dz.ANCESTORS) for t in ts)
    assert not all(outermost_visible(t, 1) for t in ts)       # one parent was not enough

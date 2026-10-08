"""Pure tests for the bridge's black slime mould."""
import math

import numpy as np

from songs.nothing import manifest, timeline
from songs.nothing.styles import slime_cover as slime

RUN = {r.section.id: r for r in manifest.walk(timeline.load())}["strings_bridge"]
SEC, PLAN = RUN.section, RUN.plan
P = PLAN["params"]


def test_white_in_black_out():
    assert P["paper"] == "#ffffff" and P["ink"] == "#000000"
    assert RUN.exit["background"] == "#000000" and RUN.exit["mode"] == "blank"


def test_balloons_each_cover_the_whole_frame_by_the_last_frame():
    fw, fh = RUN.ctx.frame_size
    bls = PLAN["balloons"]
    assert len(bls) == P["balloons"]
    for b in bls:
        r = PLAN["rings"][b["ring"]]
        assert SEC.first < b["first"] and b["first"] + len(b["scale"]) - 1 == SEC.last
        assert b["scale"] == sorted(b["scale"]) and b["scale"][0] == 1.0
        solid = slime.LOBE_CORE * slime.SOLID * r["r"] * b["scale"][-1]   # opaque core radius
        assert all(math.hypot(cx - r["x"], cy - r["y"]) < solid
                   for cx in (-fw / 2, fw / 2) for cy in (-fh / 2, fh / 2))
        assert r["birth"] + r["grow"] <= PLAN["t1"] - P["cover_secs"] + 1e-6


def test_moulds_swell_slowly():
    assert min(r["grow"] for r in PLAN["rings"]) >= P["ring_secs"][0] - 1e-9
    assert all(r["lobes"][0] == [0.0, 0.0, slime.LOBE_CORE * r["r"]] for r in PLAN["rings"])


def test_everything_happens_inside_the_section_before_the_cover():
    t_veil = PLAN["t1"] - P["cover_secs"]
    for b in PLAN["branches"]:
        ts = [t for _, _, t in b["pts"]]
        assert PLAN["t0"] <= ts[0] and ts == sorted(ts) and ts[-1] < t_veil
    for r in PLAN["rings"]:
        assert PLAN["t0"] < r["birth"] and r["birth"] + r["grow"] <= t_veil + 1e-6
        assert r["r"] <= P["ring_max_r"] + 1e-9


def test_growth_rises_from_the_bottom():
    pts = [(y, t) for b in PLAN["branches"] for _, y, t in b["pts"]]
    low = [t for y, t in pts if y < -2.0]
    high = [t for y, t in pts if y > 2.0]
    assert sum(low) / len(low) < sum(high) / len(high)


def test_network_plus_moulds_cover_the_frame_before_the_balloons():
    fw, fh = RUN.ctx.frame_size
    w = P["width"][1]
    net = np.array([(x, y) for b in PLAN["branches"] for x, y, _ in b["pts"]])
    rings = PLAN["rings"]
    worst = 0.0
    for gx in np.linspace(-fw / 2 + 0.05, fw / 2 - 0.05, 60):
        for gy in np.linspace(-fh / 2 + 0.05, fh / 2 - 0.05, 34):
            d_net = np.sqrt(((net - (gx, gy)) ** 2).sum(1)).min() - w
            d_ring = min((math.hypot(gx - r["x"], gy - r["y"]) - r["r"] for r in rings), default=9)
            worst = max(worst, min(d_net, d_ring))
    assert worst < P["ring_min_gap"] + P["cell"]        # no gap wider than a ring would fill


def test_deterministic():
    again = {r.section.id: r for r in manifest.walk(timeline.load())}["strings_bridge"].plan
    assert again["branches"] == PLAN["branches"] and again["rings"] == PLAN["rings"]

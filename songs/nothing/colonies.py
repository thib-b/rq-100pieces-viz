"""The plate's growths as blooms (pure) — shared by the outro styles so the plate grown in the
sleepy-piano section and the plate the fractal zoom starts from are the SAME blooms.

Data: plates/nothing_colonies.json (tools/nothing_colonies.py). Every bloom's shape comes from a
stream keyed by its seed index (not by section), so any style rebuilding the plate gets
identical geometry.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

from songs.nothing.seeding import section_rng
from songs.nothing.timeline import asset

DATA = "plates/nothing_colonies.json"


@lru_cache(maxsize=None)
def data():
    return json.loads(asset(DATA).read_text())


def blooms(dish_r, size_k=1.0):
    """[{x, y, lobes[(x,y,r)], swatch, cluster, seed}] in world units for a dish of radius
    dish_r centred on the origin. size_k scales every bloom (overlap / fluffiness)."""
    out = []
    for i, s in enumerate(data()["seeds"]):
        rng = section_rng("nothing", "colonies", 0, i)
        d = 2 * s["r"] * dish_r * size_k
        lobes = [(0.0, 0.0, d * 0.30)]
        for _ in range(int(rng.integers(3, 6))):
            a = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(0.08, 0.24) * d
            lobes.append((math.cos(a) * r0, math.sin(a) * r0, rng.uniform(0.09, 0.18) * d))
        out.append({"x": s["x"] * dish_r, "y": s["y"] * dish_r, "lobes": lobes,
                    "swatch": s["swatch"], "cluster": s["cluster"], "seed": i})
    return out


def z_of(seed, n):
    """Draw height for bloom `seed` — fixed by seed index, so every style stacks the plate alike."""
    return 0.001 + 0.5 * seed / n


def thresholds(lo=0.2, hi=0.78, spread=0.35, jitter=0.08):
    """Per-seed growth threshold in [lo, hi] for a plate growing organism by organism: clusters
    start largest-first, each spreading from its centre outward, plus a little seeded jitter.
    The thresholds are then spaced EVENLY by rank, so a plate whose progress rises at a steady
    rate starts organisms at a steady rate. Index = seed index."""
    d = data()
    order = sorted(d["clusters"], key=lambda c: -c["area"])
    start = {c["id"]: k / len(order) for k, c in enumerate(order)}
    cl = {c["id"]: c for c in d["clusters"]}
    raw = []
    for i, s in enumerate(d["seeds"]):
        c = cl[s["cluster"]]
        reach = math.hypot(s["x"] - c["x"], s["y"] - c["y"]) / max(c["r"], 1e-6)
        j = section_rng("nothing", "colonies-t0", 0, i).uniform(0, jitter)
        raw.append(start[s["cluster"]] * (1 - spread) + spread * min(reach, 1.0) + j)
    rank = sorted(range(len(raw)), key=lambda i: (raw[i], i))
    out = [0.0] * len(raw)
    for k, i in enumerate(rank):
        out[i] = lo + (hi - lo) * k / max(len(raw) - 1, 1)
    return out


# The sleepy-piano regrowth (plate_colonies), shared with the fractal zoom, which keeps growing
# the blooms of the last phrases after the bass comes in.
GROWTH = {"spread_secs": 3.5,   # a colony takes this long to spread from its centre to its edge
          "grow_secs": 4.0,     # each bloom swells in over this long (sleepy)
          "jitter_secs": 0.5}


def cluster_onsets(clusters, onsets):
    """{cluster id: onset time} — clusters largest-first, dealt round-robin over the onsets."""
    order = sorted(clusters, key=lambda c: -c["area"])
    return {c["id"]: onsets[k % len(onsets)] for k, c in enumerate(order)}


def growth(onsets, fps, g=GROWTH):
    """[(birth frame, end frame)] per seed index: when each bloom of the regrown plate starts
    swelling and when it is full size. Nothing is squeezed to fit a section — a bloom set off by
    a late phrase simply finishes growing after the next section has begun."""
    d = data()
    starts = cluster_onsets(d["clusters"], onsets)
    cl = {c["id"]: c for c in d["clusters"]}
    out = []
    for i, s in enumerate(d["seeds"]):
        c = cl[s["cluster"]]
        reach = math.hypot(s["x"] - c["x"], s["y"] - c["y"]) / max(c["r"], 1e-6)
        jit = section_rng("nothing", "colonies-growth", 0, i).uniform(0, g["jitter_secs"])
        t = starts[s["cluster"]] + g["spread_secs"] * min(reach, 1.2) + jit
        b = round(t * fps) + 1
        out.append((b, b + round(g["grow_secs"] * fps)))
    return out


def agar_blooms(n=260, r_range=(0.09, 0.19), t_range=(0.0, 0.32), reach=0.97):
    """Deep-blue ground for a NESTED plate: soft blooms filling the dish (unit radius) that grow
    out from its centre before the organisms do — instead of a hard-edged disc. Returns
    [{x, y, lobes, t0}] in unit-dish coordinates; deterministic (own stream)."""
    rng = section_rng("nothing", "colonies-agar", 0)
    out = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n):                                # sunflower spiral: even fill, no gaps
        rr = reach * math.sqrt((i + 0.5) / n)
        a = i * golden
        x = rr * math.cos(a) + rng.uniform(-0.03, 0.03)
        y = rr * math.sin(a) + rng.uniform(-0.03, 0.03)
        d = 2 * rng.uniform(*r_range)
        lobes = [(0.0, 0.0, d * 0.32)]
        for _ in range(int(rng.integers(3, 6))):
            b = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(0.08, 0.24) * d
            lobes.append((math.cos(b) * r0, math.sin(b) * r0, rng.uniform(0.10, 0.20) * d))
        lo, hi = t_range
        t0 = lo + (hi - lo) * (rr / reach) * 0.85 + rng.uniform(0, 0.15 * (hi - lo))
        out.append({"x": x, "y": y, "lobes": lobes, "t0": min(t0, hi)})
    return out

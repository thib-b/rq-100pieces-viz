"""slime_cover — the bridge (2:20.636 → 2:58.1): black slime mould takes over a white frame.

Black filaments grow up from the bottom edge like a slime mould (Physarum) foraging: each tip
wanders with a smooth heading, leans upward, branches more and more as the tension builds, and
steers away from ground already explored, so the growth spreads into a network. The tips are paced
by an accelerating front, so the takeover speeds up through the bridge. Behind them the network
thickens, and lobed concentric black moulds slowly swell out of the gaps it leaves, filling them.
In the last seconds a few of those moulds balloon, accelerating, until each alone covers the whole
frame, so the release (2:58.1) lands on exactly #000000 — the only fact the outro inherits.

The growth is simulated once in pure numpy (plan) from the section's own seed and cached on disk;
the Blender side only reveals what the simulation recorded (bevel-factor keys per branch).
"""
from __future__ import annotations

import json
import math

import numpy as np

from songs.nothing.state import digest
from songs.nothing.timeline import REPO

DEFAULTS = {
    "paper": "#ffffff",
    "ink": "#000000",
    "roots": 36,                # filaments starting along the bottom edge
    "step": 0.035,              # tip advance per simulation step (world units)
    "dt": 1 / 30,               # simulation step (s)
    "speed": 1.2,               # tip speed (world units / s) — the front usually limits it
    "lead": [0.05, 1.1],        # each filament may run ahead of the front by its own amount
    "speed_jitter": 0.45,       # ± fraction of speed, per filament
    "front_wave": 0.45,         # the front is ragged across the width: smooth wave amplitude
    "root_delay": 3.0,          # roots start over this many seconds, not all at once
    "wander_deg": 16.0,          # heading noise per step
    "up_bias": 0.018,            # pull of the heading towards straight up
    "avoid_deg": 30.0,          # turn away from explored ground per step (max)
    "branch_p": [0.012, 0.07],  # branching probability per step, rising over the section
    "branch_deg": [35, 80],
    "max_tips": 1200,
    "cell": 0.05,               # exploration grid
    "crowd": 2,                 # a tip dies entering a cell visited this many times by others
    "cover_frac": 0.82,         # the front reaches the top at this fraction of the section
    "ease_power": 1.7,          # >1: the front accelerates
    "width": [0.005, 0.10],    # filament half-width: newborn → full as the front tops out
    "ring_min_gap": 0.05,       # gaps wider than this get a concentric mould
    "ring_max_r": 0.34,         # bigger gaps get several small moulds, not one big disc
    "ring_delay": 2.0,          # a mould starts this long after the network passed its spot
    "ring_secs": [3.5, 8.0],    # mould growth time, small → large (slow swell)
    "cover_secs": 3.0,          # the last seconds: a few moulds balloon over the whole frame
    "balloons": 5,
    "balloon_lag": 1.2,         # balloons start staggered over this long, all full at the end
    "balloon_power": 3.0,       # >1: they start slowly and race to the edges
}

CACHE = REPO / "renders" / "nothing" / "cache"
LOBE_CORE = 0.7      # a mould's central lobe, as a fraction of its radius
SOLID = 0.88         # the mould material is fully opaque out to this fraction of a lobe


def _p(ctx):
    return {**DEFAULTS, **ctx.params.get("slime", {})}


def front_y(t, t0, cover_t, y_lo, y_hi, power):
    u = min(max((t - t0) / (cover_t - t0), 0.0), 1.0)
    return y_lo + (y_hi - y_lo) * u ** power


def simulate(p, rng, fw, fh, t0, t1):
    """Grow the network. Returns (branches, rings): branches = [{pts:[(x,y,t)], parent}],
    rings = [{x, y, r, birth, grow}] (times in seconds)."""
    cell = p["cell"]
    gw, gh = int(fw / cell) + 1, int(fh / cell) + 1
    visits = np.zeros((gh, gw), np.int32)
    owner = -np.ones((gh, gw), np.int32)
    x_lo, y_lo, y_hi = -fw / 2, -fh / 2 - 0.05, fh / 2 + 0.05
    cover_t = t0 + (t1 - t0) * p["cover_frac"]

    def cellof(x, y):
        return (min(max(int((y - y_lo) / cell), 0), gh - 1), min(max(int((x - x_lo) / cell), 0), gw - 1))

    branches, tips = [], []

    def new_branch(x, y, th, t, parent, start=None):
        branches.append({"pts": [(x, y, t)], "parent": parent})
        tips.append({"b": len(branches) - 1, "x": x, "y": y, "th": th, "alive": True,
                     "start": t if start is None else start,
                     "lead": rng.uniform(*p["lead"]),
                     "speed": 1.0 + rng.uniform(-1, 1) * p["speed_jitter"]})

    # a ragged front: a smooth random wave across the width, so no invisible straight line
    waves = [(rng.uniform(0.4, 2.2), rng.uniform(0, 2 * math.pi), rng.uniform(0.5, 1.0))
             for _ in range(4)]
    norm = sum(a for _, _, a in waves)

    def wave(x):
        return p["front_wave"] * sum(a * math.sin(f * x + ph) for f, ph, a in waves) / norm

    for i in range(p["roots"]):
        x = x_lo + (i + rng.uniform(0.15, 0.85)) * fw / p["roots"]
        t_start = t0 + rng.uniform(0, p["root_delay"])
        new_branch(x, y_lo, math.pi / 2 + rng.normal(0, 0.25), t_start, -1, start=t_start)

    wander, avoid = math.radians(p["wander_deg"]), math.radians(p["avoid_deg"])
    t = t0
    while t < cover_t + 1.0 and any(tp["alive"] for tp in tips):
        t += p["dt"]
        fy = front_y(t, t0, cover_t, y_lo, y_hi, p["ease_power"])
        frac = min(max((t - t0) / (cover_t - t0), 0.0), 1.0)
        bp = p["branch_p"][0] + (p["branch_p"][1] - p["branch_p"][0]) * frac
        for tp in list(tips):
            if not tp["alive"] or t < tp["start"]:
                continue
            budget = p["speed"] * tp["speed"] * p["dt"]
            moved = 0.0
            while moved < budget and tp["alive"]:
                if tp["y"] > fy + wave(tp["x"]) + tp["lead"]:
                    break                                   # wait for (its part of) the front
                # steer: wander, lean up, turn away from explored ground ahead
                th = tp["th"] + rng.normal(0, wander)
                th += p["up_bias"] * math.sin(math.pi / 2 - th)
                look = 3 * cell
                sides = []
                for d in (-0.6, 0.6):
                    lx, ly = tp["x"] + look * math.cos(th + d), tp["y"] + look * math.sin(th + d)
                    r, c = cellof(lx, ly)
                    sides.append(visits[r, c] * (owner[r, c] != tp["b"]))
                if sides[0] != sides[1]:
                    th += avoid if sides[0] > sides[1] else -avoid
                nx, ny = tp["x"] + p["step"] * math.cos(th), tp["y"] + p["step"] * math.sin(th)
                if not (x_lo - 0.1 <= nx <= -x_lo + 0.1) or ny > y_hi:
                    tp["alive"] = False
                    break
                r, c = cellof(nx, ny)
                if owner[r, c] not in (-1, tp["b"]) and visits[r, c] >= p["crowd"]:
                    tp["alive"] = False                     # merged into the network
                    branches[tp["b"]]["pts"].append((nx, ny, t))
                    break
                visits[r, c] += 1
                owner[r, c] = tp["b"] if owner[r, c] == -1 else owner[r, c]
                tp["x"], tp["y"], tp["th"] = nx, ny, th
                branches[tp["b"]]["pts"].append((nx, ny, t))
                moved += p["step"]
                if len(tips) < p["max_tips"] and rng.random() < bp:
                    side = 1 if rng.random() < 0.5 else -1
                    new_branch(nx, ny, th + side * math.radians(rng.uniform(*p["branch_deg"])), t,
                               tp["b"])
    branches = [b for b in branches if len(b["pts"]) >= 3]
    return branches, _rings(p, rng, branches, fw, fh, t0, t1)


def _rings(p, rng, branches, fw, fh, t0, t1):
    """Greedy concentric moulds in the gaps left by the network (by the final cover)."""
    cell = p["cell"]
    gw, gh = int(fw / cell) + 1, int(fh / cell) + 1
    xs = -fw / 2 + (np.arange(gw) + 0.5) * cell
    ys = -fh / 2 + (np.arange(gh) + 0.5) * cell
    pts = np.array([(x, y) for b in branches for (x, y, _) in b["pts"]])
    # distance from every cell centre to the network (minus the final filament width)
    dist = np.full((gh, gw), np.inf)
    for chunk in np.array_split(pts, max(1, len(pts) // 4000)):
        dx = xs[None, :, None] - chunk[None, None, :, 0]
        dy = ys[:, None, None] - chunk[None, None, :, 1]
        dist = np.minimum(dist, np.sqrt(dx * dx + dy * dy).min(axis=2))
    gap = dist - 0.85 * p["width"][1]          # the tapered tip width
    cover_t0 = t1 - p["cover_secs"]
    cover_t = t0 + (t1 - t0) * p["cover_frac"]
    rings = []
    while True:
        r_i = np.unravel_index(np.argmax(gap), gap.shape)
        g = gap[r_i]
        if g < p["ring_min_gap"]:
            break
        cx, cy = xs[r_i[1]], ys[r_i[0]]
        rad = min(g * 1.6 + cell, p["ring_max_r"])   # overlap the filaments around it
        u = (cy + fh / 2) / fh
        lo, hi = p["ring_secs"]
        grow = lo + (hi - lo) * min(rad / p["ring_max_r"], 1.0)
        passed = t0 + (cover_t - t0) * min(max(u, 0.0), 1.0) ** (1 / p["ease_power"])
        birth = min(passed + p["ring_delay"] + rng.uniform(0.0, 1.5), cover_t0 - grow)
        lobes = [(0.0, 0.0, LOBE_CORE * rad)]       # lobed outline, extent ≈ rad
        for _ in range(int(rng.integers(4, 7))):
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(0.22, 0.38) * rad
            lobes.append((d * math.cos(a), d * math.sin(a), rng.uniform(0.5, 0.64) * rad))
        rings.append({"x": float(cx), "y": float(cy), "r": float(rad), "birth": float(birth),
                      "grow": float(grow), "lobes": [[float(v) for v in lb] for lb in lobes]})
        dd = np.sqrt((xs[None, :] - cx) ** 2 + (ys[:, None] - cy) ** 2)
        gap = np.where(dd < rad, -1.0, np.minimum(gap, dd - rad))
    return rings


def plan(ctx):
    p = _p(ctx)
    sec, fps = ctx.section, ctx.fps
    fw, fh = ctx.frame_size
    t0, t1 = ctx.time(sec.first), ctx.time(sec.last + 1)
    key = digest({"p": p, "seed": sec.seed, "id": sec.id, "song": ctx.song.name,
                  "frame": [fw, fh], "t": [t0, t1], "v": 5})
    path = CACHE / f"slime_{key[:20]}.json"
    if path.exists():
        branches, rings = json.loads(path.read_text())
    else:
        text = json.dumps(simulate(p, ctx.rng("slime"), fw, fh, t0, t1))
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        branches, rings = json.loads(text)       # same shape fresh or cached (lists, not tuples)
    return {"params": p, "branches": branches, "rings": rings, "t0": t0, "t1": t1,
            "balloons": balloons(p, ctx.rng("balloons"), rings, fw, fh, sec.last, fps)}


def balloons(p, rng, rings, fw, fh, last, fps):
    """The ending: a few big moulds, spread over the frame, swell until EACH ALONE covers every
    corner with its solid core by the last frame. [{ring, first, scale: [per frame first..last]}]"""
    picks = []
    for i in sorted(range(len(rings)), key=lambda i: -rings[i]["r"]):
        r = rings[i]
        if all(math.hypot(r["x"] - rings[j]["x"], r["y"] - rings[j]["y"]) > 1.4 for j in picks):
            picks.append(i)
        if len(picks) == p["balloons"]:
            break
    end = last
    out = []
    for k, i in enumerate(picks):
        r = rings[i]
        far = max(math.hypot(cx - r["x"], cy - r["y"]) for cx in (-fw / 2, fw / 2)
                  for cy in (-fh / 2, fh / 2))
        full = 1.03 * far / (LOBE_CORE * SOLID * r["r"])        # the core alone reaches the corners
        lag = p["balloon_lag"] * (k / max(len(picks) - 1, 1)) + rng.uniform(0, 0.15)
        first = end - round((p["cover_secs"] - lag) * fps)
        n = end - first
        scale = [1.0 + (full - 1.0) * (f / n) ** p["balloon_power"] for f in range(n + 1)]
        out.append({"ring": i, "first": first, "scale": scale})
    return out


def exit_state(ctx, plan):
    return ctx.enter.with_(background="#000000", image="", mode="blank")


def build(ctx, plan):
    import bpy
    from engine import core
    from engine import render as eng
    from songs.nothing import build as B
    p, fps = plan["params"], ctx.fps
    last = ctx.section.last
    B.set_background(p["paper"])
    ink = eng.make_emission_material("slime_ink", core.hex_lin(p["ink"]))
    w0, w1 = p["width"]
    frame = lambda t: round(t * fps) + 1                               # noqa: E731
    # filaments reach full thickness as the front tops out
    thick_f = frame(plan["t0"] + (plan["t1"] - plan["t0"]) * p["cover_frac"])

    for bi, br in enumerate(plan["branches"]):
        pts = br["pts"]
        cu = bpy.data.curves.new(f"slime_{bi}", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 1.0
        cu.bevel_resolution = 1
        cu.use_fill_caps = True
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        sp.points.foreach_set("co", [c for (x, y, _) in pts for c in (x, y, 0.0, 1.0)])
        n = len(pts)
        sp.points.foreach_set("radius", [1.0 - 0.15 * i / (n - 1) for i in range(n)])  # slight taper
        cu.materials.append(ink)
        obj = bpy.data.objects.new(f"slime_{bi}", cu)
        obj.location = (0.0, 0.0, 0.01 + 0.0001 * bi)
        bpy.context.collection.objects.link(obj)
        # reveal along the branch at the simulated pace (key every ~10 points, by length)
        seg = [math.dist(pts[i][:2], pts[i + 1][:2]) for i in range(n - 1)]
        total = sum(seg) or 1.0
        acc, keys = 0.0, [(frame(pts[0][2]), 0.0)]
        for i in range(1, n):
            acc += seg[i - 1]
            if i % 10 == 0 or i == n - 1:
                keys.append((frame(pts[i][2]), acc / total))
        for f, v in keys:
            cu.bevel_factor_end = v
            cu.keyframe_insert("bevel_factor_end", frame=max(f, keys[0][0]))
        # thicken: newborn hairline → full width as the front tops out
        cu.bevel_depth = w0
        cu.keyframe_insert("bevel_depth", frame=keys[0][0])
        cu.bevel_depth = w1
        cu.keyframe_insert("bevel_depth", frame=max(thick_f, keys[0][0] + 1))
        B.show_between(obj, keys[0][0], last)

    disc_mat = _ring_material(B, p["ink"])
    swell = {b["ring"]: b for b in plan["balloons"]}
    for ri, rg in enumerate(plan["rings"]):
        me = eng.colony_mesh(f"ring_{ri}", [tuple(lb) for lb in rg["lobes"]], 32)
        me.materials.append(disc_mat)
        obj = bpy.data.objects.new(f"ring_{ri}", me)
        obj.location = (rg["x"], rg["y"], 0.001 + 0.000001 * ri)
        bpy.context.collection.objects.link(obj)
        b0, b1 = frame(rg["birth"]), frame(rg["birth"] + rg["grow"])
        obj["band"] = 1.0
        obj.keyframe_insert('["band"]', frame=b0)
        obj.scale = (0.03, 0.03, 1.0)                  # a speck that slowly swells out
        obj.keyframe_insert("scale", frame=b0)
        obj.scale = (1.0, 1.0, 1.0)
        obj.keyframe_insert("scale", frame=b1)
        bl = swell.get(ri)
        if bl:                       # ballooning: per-frame scale, and the growth bands melt away
            obj.location.z = 0.5 + 0.001 * ri          # over the filaments
            n = len(bl["scale"]) - 1
            for k, sc in enumerate(bl["scale"]):
                obj.scale = (sc, sc, 1.0)
                obj.keyframe_insert("scale", frame=bl["first"] + k)
                obj["band"] = 1.0 - k / n
                obj.keyframe_insert('["band"]', frame=bl["first"] + k)
        B.show_between(obj, b0, last)


def _ring_material(B, ink):
    """A concentric mould: solid ink with a thin soft rim and faint growth rings."""
    import bpy
    from engine import core
    mat = bpy.data.materials.new("slime_ring")
    mat.use_nodes = True
    B._blended(mat)
    nt = mat.node_tree
    nt.nodes.clear()
    uv = nt.nodes.new("ShaderNodeTexCoord")
    length = nt.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    nt.links.new(uv.outputs["UV"], length.inputs[0])            # colony_mesh: rim UV radius 1
    rim = nt.nodes.new("ShaderNodeMapRange")
    rim.interpolation_type = "SMOOTHSTEP"
    rim.inputs["From Min"].default_value = SOLID
    rim.inputs["From Max"].default_value = 1.0
    rim.inputs["To Min"].default_value = 1.0
    rim.inputs["To Max"].default_value = 0.0
    nt.links.new(length.outputs["Value"], rim.inputs["Value"])
    bands = nt.nodes.new("ShaderNodeMath")                      # faint concentric rings
    bands.operation = "SINE"
    scale = nt.nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = 38.0
    nt.links.new(length.outputs["Value"], scale.inputs[0])
    nt.links.new(scale.outputs["Value"], bands.inputs[0])
    mixc = nt.nodes.new("ShaderNodeMix")
    mixc.data_type = "RGBA"
    mixc.inputs["A"].default_value = core.hex_lin(ink)
    mixc.inputs["B"].default_value = core.hex_lin("#161616")
    band01 = nt.nodes.new("ShaderNodeMapRange")
    band01.inputs["From Min"].default_value = -1.0
    band01.inputs["From Max"].default_value = 1.0
    band01.inputs["To Min"].default_value = 0.0
    band01.inputs["To Max"].default_value = 0.5
    nt.links.new(bands.outputs["Value"], band01.inputs["Value"])
    gate = nt.nodes.new("ShaderNodeAttribute")                  # per-mould band strength
    gate.attribute_type = "OBJECT"
    gate.attribute_name = "band"
    gated = nt.nodes.new("ShaderNodeMath")
    gated.operation = "MULTIPLY"
    nt.links.new(band01.outputs["Result"], gated.inputs[0])
    nt.links.new(gate.outputs["Fac"], gated.inputs[1])
    nt.links.new(gated.outputs["Value"], mixc.inputs["Factor"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mixc.outputs["Result"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(rim.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat

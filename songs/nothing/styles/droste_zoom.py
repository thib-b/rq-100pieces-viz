"""droste_zoom — the plate as its own fractal (outro: bass → strings → end resonance).

At the bass entry a miniature plate grows inside its largest white puff — first its dish,
then its organisms one by one (largest colonies first, each spreading from its centre) — and the
camera starts falling towards it — forever: inside the miniature's puff sits another, and so on.
For the strings each nested plate is also turned by φ relative to its parent (zoom then traces
a logarithmic spiral, so rotation and zoom become ambiguous) and the whole screen rolls
clockwise. Through the end resonance the zoom carries on while everything fades to black.

Implementation: the grown plate (colonies.py, the same blooms the sleepy-piano section grew) is
built ONCE as a unit-radius collection — blooms plus a ground of deep-blue blooms — and shown through a handful
of collection instances. Their transforms come from the continuous zoom level λ(t): with
n = floor(λ), u = frac(λ), instance j shows absolute level n+j (j = -1 … `levels`), so only a
few levels exist at any time and nothing ever gets numerically tiny. The view is centred on the
nesting's fixed point F (where every level converges), which is what makes λ → λ+1 seamless.

All motion is a pure function of global time (cues.toml), so the three sections that use this
style join without seams.
"""
from __future__ import annotations

import cmath
import math

from songs.nothing import colonies, cues

# the plate's growth order and ground are read from colonies.py at BUILD time (not in the plan)
DEPENDS = ["songs/nothing/colonies.py", "songs/nothing/styles/plate_colonies.py"]

DEFAULTS = {
    "k": 3.6,                   # each nested plate is k× smaller …
    "target": [-0.349, 0.075],  # … sitting at the largest white puff (dish radii, y up)
    "bars_per_level": 2.0,      # zoom speed once going: one level per this many bars
    "ease_bars": 3.0,           # the zoom eases in over this long after the bass entry
    "grow_levels": 1.0,         # a nested plate grows over this much zoom (λ), at a steady rate
    "bloom_soft": 0.22,         # each organism swells over this much of its plate's growth
    "levels": 3,                # nested levels kept beyond the current one
    "agar": "#01132c",          # nested plates sit on the plate's own agar
    "background": "#000000",
    "dish_frac": 0.92,          # must match plate_colonies (the hand-over is the same plate)
    "size_k": 1.6,              # must match plate_colonies
    "lobe_seg": 20,
    "core_alpha": 0.92,
    "mid_alpha": 0.80,
    # strings: log-spiral nesting + clockwise roll
    "strings_start": 252.06,
    "phi_deg": 24.0,            # turn of each nested plate relative to its parent (at full)
    "phi_ramp_bars": 4.0,
    "roll_deg_per_s": 7.0,      # clockwise screen roll (at full)
    "roll_ramp_bars": 2.0,
    # end resonance
    "fade_start": 302.85,
    "fade_secs": 5.0,
}


# Ancestor plates kept behind the current one. The view is centred on the fixed point, off the
# plate's centre, so late in a level the screen edge sees past the current plate's dish onto its
# parent's — and, beyond that parent's agar, its grandparent's blooms. Two generations cover it.
ANCESTORS = 2


def _p(ctx):
    return {**DEFAULTS, **ctx.params.get("droste", {})}


def _bar():
    return cues.bar()


def _ramp(t, t0, dur):
    """Smoothstep 0 → 1 over [t0, t0+dur]."""
    x = min(max((t - t0) / dur, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def level(t, p=DEFAULTS):
    """Continuous zoom level λ(t) ≥ 0: 0 until the bass, then eases into one level per
    `bars_per_level` bars (λ is C¹: the ease is a quadratic onto the steady rate)."""
    tb = cues.raw()["scene3"]["bass_entry"]
    rate = 1.0 / (p["bars_per_level"] * _bar())
    te = p["ease_bars"] * _bar()
    tau = t - tb
    if tau <= 0:
        return 0.0
    if tau < te:
        return rate * tau * tau / (2 * te)
    return rate * (tau - te / 2)


def level_grow(a, lam, p=DEFAULTS):
    """How far absolute level a's plate has grown (0 → 1) at zoom level λ. The original plate
    (a = 0) grew in the sleepy-piano section; each nested plate grows organism by organism at a
    steady rate while λ runs over [a-1, a-1+grow_levels] — the whole time it takes the zoom to
    reach it — so new blooms keep appearing at an even pace (thresholds are evenly spaced)."""
    if a <= 0:
        return 1.0
    x = (lam - (a - 1)) / p["grow_levels"]
    return min(max(x, 0.0), 1.0)


def phi(t, p=DEFAULTS):
    return math.radians(p["phi_deg"]) * _ramp(t, p["strings_start"], p["phi_ramp_bars"] * _bar())


def roll(t, p=DEFAULTS):
    """Clockwise screen roll (radians, positive = clockwise), easing in at the strings."""
    t0, te = p["strings_start"], p["roll_ramp_bars"] * _bar()
    w = math.radians(p["roll_deg_per_s"])
    tau = t - t0
    if tau <= 0:
        return 0.0
    if tau < te:
        return w * tau * tau / (2 * te)
    return w * (tau - te / 2)


def fade(t, p=DEFAULTS):
    """Black veil opacity through the end resonance."""
    return _ramp(t, p["fade_start"], p["fade_secs"])


def fixed_point(ph, p=DEFAULTS):
    """F with S(F) = F for S(z) = v + e^{iφ} z / k: the point every level converges to."""
    v = complex(*p["target"])
    return v / (1 - cmath.exp(1j * ph) / p["k"])


def instances(t, p=DEFAULTS):
    """Pure: [(absolute level, (x, y) local-to-view, scale, rotation, agar_on, grow)] at time t.

    Coordinates are in units of the CURRENT level's dish radius, in the view (camera) frame:
    the caller multiplies by the world dish radius."""
    lam = level(t, p)
    n, u = int(math.floor(lam)), lam - math.floor(lam)
    k, ph = p["k"], phi(t, p)
    v = complex(*p["target"])
    F = fixed_point(ph, p)
    home = _ramp(lam, 0.0, 1.0)                     # centre on F over the first level
    c = F * home if n == 0 else F
    view = (k ** u) * cmath.exp(-1j * (u * ph + roll(t, p)))   # local → view (zoom, spin)
    out = []
    for j in range(-ANCESTORS, p["levels"] + 1):
        a = n + j
        if a < 0:
            continue
        # level n+j in the local frame of level n (radius 1, centre 0, rotation 0)
        centre, s, rot = 0j, 1.0, 0.0
        for i in range(j):
            centre += s * cmath.exp(1j * rot) * v
            s /= k
            rot += ph
        for i in range(-j):
            # an ancestor: S^{-1}(z) = k e^{-iφ} (z - v), applied once per generation
            centre = k * cmath.exp(-1j * ph) * (centre - v)
            s *= k
            rot -= ph
        z = view * (centre - c)
        out.append((a, (z.real, z.imag), s * abs(view), rot - (u * ph + roll(t, p)), a >= 1,
                    level_grow(a, lam, p)))
    return out


def plan(ctx):
    p = _p(ctx)
    sec = ctx.section
    _, fh = ctx.frame_size
    R = 0.5 * p["dish_frac"] * fh
    frames = list(sec.frames)
    per_frame = [instances(ctx.time(f), p) for f in frames]
    slots = p["levels"] + 1 + ANCESTORS            # j = -ANCESTORS … levels
    # the original plate (level 0) is the sleepy-piano plate itself, still finishing the blooms
    # its last phrases set off: [(seed, birth frame, full-size frame)] for those not yet full
    zero = []
    if any(r[0] == 0 for row in per_frame for r in row):
        sched = colonies.growth(cues.raw()["scene3"]["piano_onsets"], ctx.fps)
        zero = [(i, b, e) for i, (b, e) in enumerate(sched) if e > sec.first]
    return {"params": p, "R": R, "frames": frames, "inst": per_frame, "slots": slots,
            "fade": [fade(ctx.time(f), p) for f in frames], "zero": zero,
            "swatches": colonies.data()["swatches"]}


def exit_state(ctx, plan):
    return ctx.enter.with_(background="#000000", image="", mode="droste",
                           level=round(level(ctx.time(ctx.section.last), plan["params"]), 6))


def assets(ctx):
    return [colonies.asset(colonies.DATA)]


def build(ctx, plan):
    import bpy
    from engine import core
    from engine import render as eng
    from songs.nothing import build as B
    p, R = plan["params"], plan["R"]
    B.set_background(p["background"])

    # the unit plate: blooms + agar disc, in a collection that only appears through instances
    unit = bpy.data.collections.new("plate_unit")
    mats = [_growing_fluff(B, eng, f"dz_{i}", core.hex_lin(h), p, soft=p["bloom_soft"])
            for i, h in enumerate(plan["swatches"])]
    bl = colonies.blooms(1.0, p["size_k"])
    t0s = colonies.thresholds()
    n = len(bl)
    for b in bl:                 # one object per bloom: EEVEE sorts blended blobs per object
        me = eng.colony_mesh(f"dz_{b['seed']}", b["lobes"], p["lobe_seg"])
        me.materials.append(mats[b["swatch"]])
        obj = bpy.data.objects.new(f"dz_{b['seed']}", me)
        obj.location = (b["x"], b["y"], colonies.z_of(b["seed"], n))
        obj["t0"] = t0s[b["seed"]]                   # when this organism starts growing
        unit.objects.link(obj)
    # a nested plate's dark ground: many small deep-blue blooms growing out from its centre
    # (only shown on nested levels — the instancer's "agar" property), no hard-edged disc
    agar_mat = _growing_fluff(B, eng, "dz_agar", core.hex_lin(p["agar"]), p, agar_gate=True,
                              core_alpha=1.0, mid_alpha=0.95)
    for i, a in enumerate(colonies.agar_blooms()):
        me = eng.colony_mesh(f"dz_agar_{i}", a["lobes"], p["lobe_seg"])
        me.materials.append(agar_mat)
        obj = bpy.data.objects.new(f"dz_agar_{i}", me)
        obj.location = (a["x"], a["y"], 0.0002 + 0.0003 * i / 1000)     # beneath every organism
        obj["t0"] = a["t0"]
        unit.objects.link(obj)

    # level 0 is real objects, not an instance: the sleepy-piano plate with its own (scale-keyed)
    # growth, parented to an empty that moves like a slot
    zero = None
    if plan["zero"] or any(r[0] == 0 for row in plan["inst"] for r in row):
        from songs.nothing.styles.plate_colonies import grow_keys
        zero = bpy.data.objects.new("level_zero", None)
        bpy.context.collection.objects.link(zero)
        plain = [eng.make_fluff_material(f"dz0_{i}", core.hex_lin(h), dissolve=False,
                                         core_alpha=p["core_alpha"], mid_alpha=p["mid_alpha"])
                 for i, h in enumerate(plan["swatches"])]
        growing = {i: (b0, b1) for i, b0, b1 in plan["zero"]}
        first = ctx.section.first
        for b in bl:
            me = eng.colony_mesh(f"dz0_{b['seed']}", b["lobes"], p["lobe_seg"])
            me.materials.append(plain[b["swatch"]])
            obj = bpy.data.objects.new(f"dz0_{b['seed']}", me)
            obj.location = (b["x"], b["y"], colonies.z_of(b["seed"], n))
            obj.parent = zero
            bpy.context.collection.objects.link(obj)
            if b["seed"] in growing:
                b0, b1 = growing[b["seed"]]
                grow_keys(obj, b0, b1)
                if b0 > first:
                    B.show_between(obj, b0, ctx.section.last)

    insts = []
    for j in range(plan["slots"]):
        e = bpy.data.objects.new(f"level_slot_{j}", None)
        e.instance_type = "COLLECTION"
        e.instance_collection = unit
        e["agar"] = 0.0
        e["grow"] = 1.0
        bpy.context.collection.objects.link(e)
        insts.append(e)

    for f, row in zip(plan["frames"], plan["inst"]):
        rows = sorted(row, key=lambda r: r[0])           # outermost level first
        if zero is not None:
            z0 = [(j, r) for j, r in enumerate(rows) if r[0] == 0]
            if z0:
                j, (_, (x, y), s, rot, _, _) = z0[0]
                zero.location = (x * R, y * R, 0.6 * j)
                zero.scale = (s * R, s * R, 1.0)
                zero.rotation_euler = (0.0, 0.0, rot)
            else:
                zero.scale = (0.0, 0.0, 1.0)             # level 0 gone: collapse it
            for path in ("location", "scale", "rotation_euler"):
                zero.keyframe_insert(path, frame=f)
        for j, e in enumerate(insts):
            if j < len(rows) and not (zero is not None and rows[j][0] == 0):
                a, (x, y), s, rot, agar_on, gr = rows[j]
                e.location = (x * R, y * R, 0.6 * j)     # deeper levels drawn on top
                e.scale = (s * R, s * R, 1.0)            # depth unscaled: levels stay in layers
                e.rotation_euler = (0.0, 0.0, rot)
                e["agar"] = 1.0 if agar_on else 0.0
                e["grow"] = gr
                e.hide_render = False
            else:
                e.hide_render = True
            e.keyframe_insert("location", frame=f)
            e.keyframe_insert("scale", frame=f)
            e.keyframe_insert("rotation_euler", index=2, frame=f)
            e.keyframe_insert('["agar"]', frame=f)
            e.keyframe_insert('["grow"]', frame=f)
            e.keyframe_insert("hide_render", frame=f)
    B.make_constant(*insts, *([zero] if zero is not None else []))   # per-frame: no blending

    veil = B.camera_veil("fade_veil", "#000000")
    for f, a in zip(plan["frames"], plan["fade"]):
        veil.alpha_input.default_value = a
        veil.alpha_input.keyframe_insert("default_value", frame=f)


def _growing_fluff(B, eng, name, colour, p, soft=0.12, edge=0.25, agar_gate=False,
                   core_alpha=None, mid_alpha=None):
    """The Haha fluff blob, plus growth: an organism with threshold t0 (object property) starts
    when its plate's `grow` (instancer property) passes t0, and opens out from its centre."""
    mat = eng.make_fluff_material(name, colour, dissolve=False,
                                  core_alpha=p["core_alpha"] if core_alpha is None else core_alpha,
                                  mid_alpha=p["mid_alpha"] if mid_alpha is None else mid_alpha)
    nt = mat.node_tree
    mix = next(n for n in nt.nodes if n.type == "MIX_SHADER")
    ramp = next(n for n in nt.nodes if n.type == "VALTORGB")
    t0 = nt.nodes.new("ShaderNodeAttribute")
    t0.attribute_type = "OBJECT"
    t0.attribute_name = "t0"
    gr = nt.nodes.new("ShaderNodeAttribute")
    gr.attribute_type = "INSTANCER"
    gr.attribute_name = "grow"
    prog = nt.nodes.new("ShaderNodeMath")                   # (grow - t0) / soft, clamped
    prog.operation = "SUBTRACT"
    nt.links.new(gr.outputs["Fac"], prog.inputs[0])
    nt.links.new(t0.outputs["Fac"], prog.inputs[1])
    prog2 = nt.nodes.new("ShaderNodeMath")
    prog2.operation = "DIVIDE"
    prog2.use_clamp = True
    prog2.inputs[1].default_value = soft
    nt.links.new(prog.outputs["Value"], prog2.inputs[0])
    uv = nt.nodes.new("ShaderNodeTexCoord")
    rad = nt.nodes.new("ShaderNodeVectorMath")              # 0 at a lobe's centre, 1 at its rim
    rad.operation = "LENGTH"
    nt.links.new(uv.outputs["UV"], rad.inputs[0])
    front = nt.nodes.new("ShaderNodeMath")                  # (progress·(1+edge) - r) / edge
    front.operation = "MULTIPLY_ADD"
    front.inputs[1].default_value = 1.0 + edge
    nt.links.new(prog2.outputs["Value"], front.inputs[0])
    neg = nt.nodes.new("ShaderNodeMath")
    neg.operation = "MULTIPLY"
    neg.inputs[1].default_value = -1.0
    nt.links.new(rad.outputs["Value"], neg.inputs[0])
    nt.links.new(neg.outputs["Value"], front.inputs[2])
    mask = nt.nodes.new("ShaderNodeMath")
    mask.operation = "DIVIDE"
    mask.use_clamp = True
    mask.inputs[1].default_value = edge
    nt.links.new(front.outputs["Value"], mask.inputs[0])
    alpha = nt.nodes.new("ShaderNodeMath")
    alpha.operation = "MULTIPLY"
    nt.links.new(ramp.outputs["Color"], alpha.inputs[0])
    nt.links.new(mask.outputs["Value"], alpha.inputs[1])
    if agar_gate:                       # the original plate (level 0) sits on black: no ground
        gate = nt.nodes.new("ShaderNodeAttribute")
        gate.attribute_type = "INSTANCER"
        gate.attribute_name = "agar"
        gated = nt.nodes.new("ShaderNodeMath")
        gated.operation = "MULTIPLY"
        nt.links.new(alpha.outputs["Value"], gated.inputs[0])
        nt.links.new(gate.outputs["Fac"], gated.inputs[1])
        alpha = gated
    nt.links.new(alpha.outputs["Value"], mix.inputs["Fac"])
    return mat

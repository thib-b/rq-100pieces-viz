"""The paper: scene 1's fall lands inside the plate's largest white puff, and that exact view of
the photo stays on as the "white" ground of everything after it (verse 2, NOTHING, the claps,
the bridge) — the plate's own grain instead of a digital #ffffff. The black of NOTHING's
negative flips is the same paper inverted (in display space, so it reads as a true negative).

The paper breathes very slowly: a gentle zoom-in-and-back plus a slight drift, a pure function
of global time since the landing that starts at rest, so it joins the fall seamlessly and every
section that shows it lines up.
"""
from __future__ import annotations

import math

from songs.nothing import cues
from songs.nothing.styles import plate_ratchet as pr

BREATH = {
    "zoom": 0.04,          # peak extra magnification of a breath
    "bars": 4,             # one breath per this many bars (≈12.5 s)
    "drift": 0.12,         # peak drift, world units (frame width 10)
}
Z = -1.0                   # behind everything drawn on it


def landing_pose(frame_size, p=pr.DEFAULTS):
    """The photo plane's transform (camera at the origin, ortho = frame width) that shows exactly
    what plate_ratchet's camera sees at the landing: (x, y, side, rotation_z)."""
    fw, fh = frame_size
    tl = cues.scene1()["landing"]
    rw = 0.5 * p["start_dish_frac"] * fh
    side = rw / p["dish_radius_uv"]
    m = pr.magnification(tl, p)
    cx, cy = pr.camera_center(tl, rw, p)
    return -cx * m, -cy * m, side * m, -math.radians(pr.ratchet_angle(tl, p))


def breath(t, b=BREATH):
    """(scale, dx, dy) of the paper at global time t: identity until the landing, then slow
    breaths that leave the landing at rest (1 − cos ramps: zero value and speed at t = landing)."""
    u = t - cues.scene1()["landing"]
    if u <= 0:
        return 1.0, 0.0, 0.0
    T = b["bars"] * cues.bar()
    ramp = lambda period: (1 - math.cos(2 * math.pi * u / period)) / 2      # noqa: E731
    return (1 + b["zoom"] * ramp(T),
            b["drift"] * (ramp(1.618 * T) - 0.5 * ramp(0.71 * T)),
            b["drift"] * (0.8 * ramp(2.27 * T) - 0.4 * ramp(0.53 * T)))


def build(ctx, invertible=False):
    """Add the breathing paper behind this section's frames. Returns the inversion factor socket
    (a Value node: 0 paper, 1 negative — keyframe it) when `invertible`, else None."""
    import bpy
    from songs.nothing import build as B
    from songs.nothing.timeline import asset
    x, y, side, rot = landing_pose(ctx.frame_size)
    rig = bpy.data.objects.new("paper_rig", None)          # breathes about the frame centre
    bpy.context.collection.objects.link(rig)
    plane = B.image_plane("paper", asset(pr.DEFAULTS["image"]), side, center=(x, y), z=Z)
    plane.rotation_euler[2] = rot
    plane.parent = rig
    for f in ctx.section.frames:
        s, dx, dy = breath(ctx.time(f))
        rig.scale = (s, s, 1.0)
        rig.location = (dx, dy, 0.0)
        rig.keyframe_insert("scale", frame=f)
        rig.keyframe_insert("location", frame=f)
    if not invertible:
        return None
    return _add_negative(plane.data.materials[0], asset(pr.DEFAULTS["image"]))


def _add_negative(mat, path):
    """Mix the paper's emission with its display-space negative: the raw (non-colour) pixels are
    inverted, then decoded with the exact sRGB curve, so the Standard view shows 255 − value."""
    import bpy
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = next(n for n in nt.nodes if n.type == "EMISSION")
    raw_img = bpy.data.images.load(str(path), check_existing=False)
    raw_img.colorspace_settings.name = "Non-Color"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = raw_img
    tex.interpolation = "Cubic"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(tex.outputs["Color"], sep.inputs["Color"])

    def math_node(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    for i in range(3):
        y = math_node("SUBTRACT", 1.0, sep.outputs[i])                       # the negative
        lo = math_node("DIVIDE", y, 12.92)
        hi = math_node("POWER", math_node("DIVIDE", math_node("ADD", y, 0.055), 1.055), 2.4)
        c = math_node("LESS_THAN", y, 0.04045)
        lin = math_node("ADD", hi, math_node("MULTIPLY", c, math_node("SUBTRACT", lo, hi)))
        nt.links.new(lin, comb.inputs[i])
    neg = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(comb.outputs["Color"], neg.inputs["Color"])
    fac = nt.nodes.new("ShaderNodeValue")
    fac.outputs[0].default_value = 0.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac.outputs[0], mix.inputs["Fac"])
    nt.links.new(em.outputs["Emission"], mix.inputs[1])
    nt.links.new(neg.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return fac.outputs[0]

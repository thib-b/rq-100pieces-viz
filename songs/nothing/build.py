"""Blender scene construction for ONE section (bpy). Styles call these helpers from build().

Each section is built in a freshly cleared scene containing only its own objects, so build
time and memory scale with the section, not the song.
"""
from __future__ import annotations

from types import SimpleNamespace

import bpy

from engine import core
from engine import render as eng


def reset_scene(song, out_pattern, res_pct=100):
    """Empty scene + ortho camera + EEVEE/PNG render settings for the song's format."""
    eng.clear_scene()
    # everything a previous section in the same Blender session could leave behind — worlds and
    # actions especially: keyframes on a reused node name would keep animating the new scene
    for coll in (bpy.data.node_groups, bpy.data.textures, bpy.data.worlds, bpy.data.actions,
                 bpy.data.fonts):
        for item in list(coll):
            coll.remove(item)
    fmt = SimpleNamespace(aspect=song.aspect, fps=song.fps, ortho_scale=song.ortho_scale,
                          background="opaque")
    eng.setup_camera(fmt)
    eng.setup_render(fmt, ".", res_pct)
    bpy.context.scene.render.filepath = str(out_pattern)
    set_background("#000000")


def set_background(hexstr):
    """Flat world colour (Standard view transform → the hex shows exactly)."""
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = core.hex_lin(hexstr)
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def _blended(mat):
    """Smooth (non-dithered) alpha blending, across Blender versions."""
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND"),
                      ("show_transparent_back", False)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass


def _load_image(path):
    key = str(path)
    for img in bpy.data.images:
        if img.filepath == key:
            return img
    return bpy.data.images.load(key)


def image_plane(name, path, height, center=(0.0, 0.0), z=0.0, radial_alpha=None):
    """An unlit plane showing an image at its true colours, `height` world units tall.

    radial_alpha=(r0, r1): opaque within radius r0 of the image centre (as a fraction of the
    image's side), fading to transparent at r1 — for circular cut-outs and soft edges."""
    img = _load_image(path)
    w_px, h_px = img.size
    width = height * w_px / h_px
    bpy.ops.mesh.primitive_plane_add(size=1, location=(center[0], center[1], z))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (width, height, 1)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    if radial_alpha is None:
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    else:
        _blended(mat)
        uv = nt.nodes.new("ShaderNodeTexCoord")
        dist = nt.nodes.new("ShaderNodeVectorMath")
        dist.operation = "DISTANCE"
        dist.inputs[1].default_value = (0.5, 0.5, 0.0)
        nt.links.new(uv.outputs["UV"], dist.inputs[0])
        rng = nt.nodes.new("ShaderNodeMapRange")
        rng.inputs["From Min"].default_value = radial_alpha[0]
        rng.inputs["From Max"].default_value = radial_alpha[1]
        rng.inputs["To Min"].default_value = 1.0
        rng.inputs["To Max"].default_value = 0.0
        rng.interpolation_type = "SMOOTHSTEP"
        nt.links.new(dist.outputs["Value"], rng.inputs["Value"])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(rng.outputs["Result"], mix.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
        nt.links.new(em.outputs["Emission"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    obj.data.materials.append(mat)
    return obj


def camera():
    return bpy.context.scene.camera


def camera_veil(name, hexstr, alpha=0.0):
    """A flat colour sheet just in front of the camera (follows it), opacity on `.alpha_input`
    (a Value node — keyframe its default_value). For fades to/from a solid colour."""
    cam = camera()
    bpy.ops.mesh.primitive_plane_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    obj.parent = cam
    obj.location = (0.0, 0.0, -1.0)              # 1 unit in front of the ortho camera
    obj.scale = (1000.0, 1000.0, 1.0)            # covers any ortho_scale
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    _blended(mat)
    nt = mat.node_tree
    nt.nodes.clear()
    val = nt.nodes.new("ShaderNodeValue")
    val.outputs[0].default_value = alpha
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = core.hex_lin(hexstr)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(val.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    obj.data.materials.append(mat)
    return _Veil(obj, val.outputs[0])


class _Veil:
    def __init__(self, obj, alpha_socket):
        self.obj = obj
        self.alpha_input = alpha_socket


def build_section(run, out_pattern, res_pct=100):
    """Clear the scene and build just this section, framed to its global frame range."""
    from songs.nothing import styles
    reset_scene(run.ctx.song, out_pattern, res_pct)
    styles.get(run.section.style).build(run.ctx, run.plan)
    for name, plan in run.layer_plans:
        styles.get(name).build(run.ctx, plan)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = run.section.first, run.section.last


# ---------------- text ----------------
FONT_PATH = "/System/Library/Fonts/HelveticaNeue.ttc"


def font():
    for f in bpy.data.fonts:
        if f.filepath == FONT_PATH:
            return f
    return bpy.data.fonts.load(FONT_PATH)


def emission_material(name, hexstr):
    """Flat unlit colour; its colour socket is returned too (for keyframed colour flips)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = core.hex_lin(hexstr)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat, em.inputs["Color"]


CAP_CENTER = 0.36     # baseline offset (× size) that visually centres capitals on y


def text_object(name, body, size, mat, x=0.0, y=0.0, z=0.1, align_x="CENTER"):
    """A flat Helvetica Neue text object (unlit), on a fixed baseline so the cap height is
    centred on `y` whatever the text (prefixes of a line never jump). With align_x='LEFT',
    `x` is the left edge."""
    cu = bpy.data.curves.new(name, type="FONT")
    cu.body = body
    cu.font = font()
    cu.size = size
    cu.align_x = align_x
    cu.align_y = "BOTTOM_BASELINE"
    cu.materials.append(mat)
    obj = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(obj)
    obj.location = (x, y - CAP_CENTER * size, z)
    return obj


def text_width(obj):
    bpy.context.view_layer.update()
    return obj.dimensions[0]


def world_color_input():
    """The world Background colour socket (after set_background)."""
    nt = bpy.context.scene.world.node_tree
    return next(n for n in nt.nodes if n.type == "BACKGROUND").inputs["Color"]


def fcurves(id_data):
    """All F-curves animating a datablock (Blender 4.4+ layered actions, or legacy)."""
    ad = getattr(id_data, "animation_data", None)
    if not ad or not ad.action:
        return []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return list(cb.fcurves) if cb else []
    except (ImportError, AttributeError):
        return list(ad.action.fcurves)


def make_constant(*id_datas):
    """Set every keyframe on these datablocks to CONSTANT interpolation (hard cuts)."""
    for d in id_datas:
        for fc in fcurves(d):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


class constant_keys:
    """Context manager: keyframes inserted inside are CONSTANT (snaps, not blends). Sets the
    preference (honoured by UI inserts) — scripts must also call make_constant() on the
    datablocks afterwards, which is what actually sticks."""

    def __enter__(self):
        self.edit = bpy.context.preferences.edit
        self.prev = self.edit.keyframe_new_interpolation_type
        self.edit.keyframe_new_interpolation_type = "CONSTANT"

    def __exit__(self, *exc):
        self.edit.keyframe_new_interpolation_type = self.prev


def show_between(obj, first, last):
    """obj renders only on frames first..last (inclusive), via constant hide_render keys."""
    with constant_keys():
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=first - 1)
        obj.hide_render = False
        obj.keyframe_insert("hide_render", frame=first)
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=last + 1)
    for fc in fcurves(obj):                  # only the visibility snaps: other keys keep easing
        if fc.data_path == "hide_render":
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"

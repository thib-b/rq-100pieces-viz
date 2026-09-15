#!/usr/bin/env python3
"""Blender entry point: render a recipe.

Run under Blender (not plain Python):

    blender --background --python 100pieces.py -- --recipe recipes/haha_landscape.toml [--last]
    blender --background --python 100pieces.py -- --recipe recipes/haha_vertical.toml --preview [--fullres]
    blender --background --python 100pieces.py -- --recipe recipes/haha_landscape.toml --output DIR

Modes: --last (final frame only), --preview [--fullres] (spread of frames), or full render
(all frames, then auto-encode per the recipe). This module ports the proven builders from the
legacy animations/ scripts, parameterised by the recipe; the pure math/image logic lives in
engine.core and engine.plate.
"""
import json
import math
import os
import random
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np

# Make the `engine` package importable when Blender runs this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from engine import core, plate, recipe as recipe_mod  # noqa: E402


def _asset(path):
    """Resolve a recipe asset path: absolute as-is, else relative to the repo root."""
    p = Path(path)
    return str(p if p.is_absolute() else REPO_ROOT / p)


# ---------------- argv ----------------
def args_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get_opt(args, flag, default=None):
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return default


# ---------------- scene bootstrap ----------------
def clear_scene():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.curves,
                 bpy.data.materials, bpy.data.cameras, bpy.data.images):
        for item in list(coll):
            coll.remove(item)


def load_rgb(path, grid):
    img = bpy.data.images.load(path)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    px = buf.reshape(h, w, 4)[:, :, :3]
    arr = plate.resample_grid(px, grid)
    bpy.data.images.remove(img)
    return arr


def load_mask(path, grid, thresh):
    img = bpy.data.images.load(path)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    alpha = buf.reshape(h, w, 4)[:, :, 3]
    mask = plate.mask_from_alpha(alpha, grid, thresh)
    bpy.data.images.remove(img)
    ys, xs = np.where(mask)
    return mask, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def setup_world(rcp, grey):
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    if rcp.background == "transparent":
        return                                  # film_transparent handles it
    bg = nt.nodes.new("ShaderNodeBackground")
    if rcp.background == "orange":
        bg.inputs["Color"].default_value = core.hex_lin(rcp.orange_hex)
    else:                                       # grey (detected from the plate image)
        bg.inputs["Color"].default_value = core.lin4(grey)
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def setup_camera(rcp):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "HORIZONTAL"          # ortho_scale maps to WIDTH for every aspect
    cam_data.ortho_scale = rcp.ortho_scale
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (0, 0, 10)
    bpy.context.scene.camera = cam


def setup_render(rcp, out_dir, res_pct):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = rcp.aspect
    scene.render.resolution_percentage = res_pct
    scene.render.fps = rcp.fps
    scene.render.film_transparent = (rcp.background == "transparent")
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = os.path.join(out_dir, "frame_#####")
    try:
        scene.view_settings.view_transform = "Standard"
    except TypeError:
        pass


# ---------------- revealed plate photo (bloom-reveal treatment) ----------------
def build_reveal_photo(art_path, icx, icy, ir, r_world, frame_w, frame_h, grid, hold_end, dissolve_end):
    img = bpy.data.images.load(art_path)
    mat = bpy.data.materials.new("reveal")
    mat.use_nodes = True
    for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED"),
                      ("show_transparent_back", False)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    tex.interpolation = "Cubic"; tex.extension = "EXTEND"
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    texco = nt.nodes.new("ShaderNodeTexCoord")
    length = nt.nodes.new("ShaderNodeVectorMath"); length.operation = "LENGTH"
    nt.links.new(texco.outputs["Object"], length.inputs[0])
    ndist = nt.nodes.new("ShaderNodeMath"); ndist.operation = "DIVIDE"
    nt.links.new(length.outputs["Value"], ndist.inputs[0]); ndist.inputs[1].default_value = r_world
    crop = nt.nodes.new("ShaderNodeMapRange")
    crop.inputs["From Min"].default_value = 0.98
    crop.inputs["From Max"].default_value = 1.0
    crop.inputs["To Min"].default_value = 1.0
    crop.inputs["To Max"].default_value = 0.0
    crop.clamp = True
    nt.links.new(ndist.outputs["Value"], crop.inputs["Value"])
    reveal = nt.nodes.new("ShaderNodeValue"); reveal.label = "reveal"
    fac = nt.nodes.new("ShaderNodeMath"); fac.operation = "MULTIPLY"
    nt.links.new(crop.outputs["Result"], fac.inputs[0])
    nt.links.new(reveal.outputs["Value"], fac.inputs[1])
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(trans.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    reveal.outputs["Value"].default_value = 0.0
    reveal.outputs["Value"].keyframe_insert("default_value", frame=hold_end)
    reveal.outputs["Value"].default_value = 1.0
    reveal.outputs["Value"].keyframe_insert("default_value", frame=dissolve_end)

    me = bpy.data.meshes.new("revealplane")
    verts = [(-frame_w / 2, -frame_h / 2, 0), (frame_w / 2, -frame_h / 2, 0),
             (frame_w / 2, frame_h / 2, 0), (-frame_w / 2, frame_h / 2, 0)]
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")

    def uvof(wx, wy):
        return ((icx + (wx / r_world) * ir) / (grid - 1), (icy + (wy / r_world) * ir) / (grid - 1))
    corner_uv = {0: uvof(-frame_w / 2, -frame_h / 2), 1: uvof(frame_w / 2, -frame_h / 2),
                 2: uvof(frame_w / 2, frame_h / 2), 3: uvof(-frame_w / 2, frame_h / 2)}
    for i, loop in enumerate(me.loops):
        uvl.data[i].uv = corner_uv[loop.vertex_index]
    me.materials.append(mat)
    obj = bpy.data.objects.new("revealplane", me)
    bpy.context.collection.objects.link(obj)


# ---------------- bloom geometry + materials ----------------
def colony_mesh(name, lobes, lobe_seg):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for (lx, ly, r) in lobes:
        c = bm.verts.new((lx, ly, 0.0))
        rim = []
        for i in range(lobe_seg):
            a = 2 * math.pi * i / lobe_seg
            ca, sa = math.cos(a), math.sin(a)
            rim.append((bm.verts.new((lx + ca * r, ly + sa * r, 0.0)), ca, sa))
        for i in range(lobe_seg):
            v1, c1, s1 = rim[i]
            v2, c2, s2 = rim[(i + 1) % lobe_seg]
            f = bm.faces.new((c, v1, v2))
            for loop in f.loops:
                if loop.vert is c:
                    loop[uvl].uv = (0.0, 0.0)
                elif loop.vert is v1:
                    loop[uvl].uv = (c1, s1)
                else:
                    loop[uvl].uv = (c2, s2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def make_fluff_material(name, color, dissolve, core_alpha=0.92, mid_alpha=0.82):
    """Radial-gradient soft blob. If `dissolve`, opacity is multiplied by the object's own
    alpha (Object Info) so each bloom can fade independently through one shared material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED"),
                      ("show_transparent_back", False)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    nt = mat.node_tree
    nt.nodes.clear()
    texco = nt.nodes.new("ShaderNodeTexCoord")
    grad = nt.nodes.new("ShaderNodeTexGradient"); grad.gradient_type = "SPHERICAL"
    nt.links.new(texco.outputs["UV"], grad.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0, 0, 0, 1)
    el[1].position = 1.0; el[1].color = (core_alpha, core_alpha, core_alpha, 1)
    mid = ramp.color_ramp.elements.new(0.36); mid.color = (mid_alpha, mid_alpha, mid_alpha, 1)
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    emis = nt.nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = color
    emis.inputs["Strength"].default_value = 1.0
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    if dissolve:
        objinfo = nt.nodes.new("ShaderNodeObjectInfo")
        opacity = nt.nodes.new("ShaderNodeMath"); opacity.operation = "MULTIPLY"
        nt.links.new(ramp.outputs["Color"], opacity.inputs[0])
        nt.links.new(objinfo.outputs["Alpha"], opacity.inputs[1])
        nt.links.new(opacity.outputs["Value"], mix.inputs["Fac"])
    else:
        nt.links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    nt.links.new(trans.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emis.outputs["Emission"], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def make_emission_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def build_blooms_image(rcp, seeds_world, assign, births, deaths, fluff_mats, mould_end,
                       bloom_grow, bloom_fade):
    """Image-matched blooms (reveal / bloom_overlay). deaths=None => no dissolve (overlay)."""
    lo, hi = rcp.bloom_diam
    for i, (wx, wy) in enumerate(seeds_world):
        birth = births[i]
        diam = _rng.uniform(lo, hi)
        lobes = [(0.0, 0.0, diam * 0.34)]
        for _ in range(_rng.randint(3, 5)):
            a = _rng.uniform(0, 2 * math.pi)
            d = _rng.uniform(0.08, 0.24) * diam
            r = _rng.uniform(0.09, 0.18) * diam
            lobes.append((math.cos(a) * d, math.sin(a) * d, r))
        me = colony_mesh(f"bloom_{i}", lobes, rcp.lobe_seg)
        me.materials.append(fluff_mats[int(assign[i])])
        obj = bpy.data.objects.new(f"bloom_{i}", me)
        obj.location = (wx, wy, 0.01 + 0.05 * (birth / mould_end))
        bpy.context.collection.objects.link(obj)
        obj.scale = (0.001, 0.001, 0.001)
        obj.keyframe_insert("scale", frame=max(1, int(birth)))
        obj.scale = (1.0, 1.0, 1.0)
        obj.keyframe_insert("scale", frame=max(2, int(birth) + bloom_grow))
        if deaths is not None:
            death = deaths[i]
            obj.color = (1.0, 1.0, 1.0, 1.0)
            obj.keyframe_insert("color", frame=int(death))
            obj.color = (1.0, 1.0, 1.0, 0.0)
            obj.keyframe_insert("color", frame=int(death) + bloom_fade)


def build_blooms_scatter(rcp, stamp_half, frame_w, frame_h, fluff_mats, total, bloom_grow):
    """Palette blooms scattered everywhere EXCEPT the central stamp square (stamp_blooms)."""
    hx, hy = stamp_half
    lo, hi = rcp.bloom_diam
    palette = list(rcp.bloom_palette_whites) + list(rcp.bloom_palette_darks)
    i = 0
    for _ in range(rcp.n_bloom):
        diam = _rng.uniform(lo, hi)
        reach = diam * 0.5
        mx, my = hx * 1.05 + reach, hy * 1.05 + reach
        cx = cy = None
        for _try in range(40):
            xp = _rng.uniform(-frame_w / 2, frame_w / 2)
            yp = _rng.uniform(-frame_h / 2, frame_h / 2)
            if abs(xp) > mx or abs(yp) > my:
                cx, cy = xp, yp
                break
        if cx is None:
            continue
        lobes = [(0.0, 0.0, diam * 0.30)]
        for _i in range(_rng.randint(4, 7)):
            a = _rng.uniform(0, 2 * math.pi)
            d = _rng.uniform(0.10, 0.28) * diam
            r = _rng.uniform(0.09, 0.19) * diam
            lobes.append((math.cos(a) * d, math.sin(a) * d, r))
        col = (_rng.choice(rcp.bloom_palette_whites) if _rng.random() < 0.5
               else _rng.choice(rcp.bloom_palette_darks))
        birth = _rng.uniform(1, total - bloom_grow)
        me = colony_mesh(f"colony_{i}", lobes, rcp.lobe_seg)
        me.materials.append(fluff_mats[col])
        obj = bpy.data.objects.new(f"colony_{i}", me)
        obj.location = (cx, cy, 0.002 * (birth / total))
        bpy.context.collection.objects.link(obj)
        s0 = core.smootherstep(0.0)
        obj.scale = (s0, s0, s0)
        obj.keyframe_insert("scale", frame=max(1, int(birth)))
        obj.scale = (1.0, 1.0, 1.0)
        obj.keyframe_insert("scale", frame=max(2, int(birth) + bloom_grow))
        i += 1


# ---------------- stamp geometry ----------------
def make_wave_object(name, fils, start_frame, grow_frames, mat, bevel):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 1
    cu.use_fill_caps = True
    for pts, radii in fils:
        n = len(pts)
        sp = cu.splines.new("POLY")
        sp.points.add(n - 1)
        coords = []
        for (x, y) in pts:
            coords += [x, y, 0.0, 1.0]
        sp.points.foreach_set("co", coords)
        sp.points.foreach_set("radius", radii)
    cu.materials.append(mat)
    obj = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(obj)
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert("bevel_factor_end", frame=max(1, int(start_frame)))
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert("bevel_factor_end", frame=max(2, int(start_frame) + grow_frames))


def build_stamp(rcp, fils_grid, to_world, mat, reveal_frames, stamp_grow, stamp_bucket):
    buckets = {}
    for grid_pts in fils_grid:
        birth = reveal_frames * (_rng.random() ** rcp.stamp_ease)
        buckets.setdefault(int(birth / stamp_bucket), []).append(grid_pts)
    for wv, bucket in buckets.items():
        fils = [([to_world(c, r) for (c, r) in gp], plate.taper_radii(len(gp))) for gp in bucket]
        make_wave_object(f"stamp_{wv}", fils, 1 + wv * stamp_bucket, stamp_grow, mat, rcp.bevel)


def world_mapping(rcp, bbox, frame_w, frame_h):
    minc, minr, maxc, maxr = bbox
    cx, cy = (minc + maxc) / 2.0, (minr + maxr) / 2.0
    scale = (rcp.stamp_height_frac * frame_h) / max(1, (maxr - minr))

    def to_world(col, row):
        return ((col - cx) * scale, (row - cy) * scale)

    stamp_half = ((maxc - minc) * scale / 2.0, (maxr - minr) * scale / 2.0)
    return to_world, stamp_half


# ---------------- lyrics ----------------
def load_mask_aspect(path, long_grid, thresh):
    """Downsample a mask PNG's alpha to a boolean grid preserving aspect (long side=long_grid).
    Returns (mask[gh,gw] bool, (gw, gh), (fullW, fullH)). Row 0 = image bottom (Blender order)."""
    img = bpy.data.images.load(path)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    alpha = buf.reshape(h, w, 4)[:, :, 3]
    bpy.data.images.remove(img)
    if h >= w:
        gh = long_grid; gw = max(1, round(long_grid * w / h))
    else:
        gw = long_grid; gh = max(1, round(long_grid * h / w))
    rows = np.linspace(0, h - 1, gh).astype(int)
    cols = np.linspace(0, w - 1, gw).astype(int)
    return alpha[np.ix_(rows, cols)] > thresh, (gw, gh), (w, h)


def make_word_object(name, world_fils, bevel, mat):
    """A word's filaments as one beveled POLY curve, centred on its own origin (so scaling the
    object grows it in place). Returns (obj, curve)."""
    pts_all = [p for pts, _ in world_fils for p in pts]
    cx = sum(p[0] for p in pts_all) / len(pts_all)
    cy = sum(p[1] for p in pts_all) / len(pts_all)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 1
    cu.use_fill_caps = True
    for pts, radii in world_fils:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        coords = []
        for (x, y) in pts:
            coords += [x - cx, y - cy, 0.0, 1.0]
        sp.points.foreach_set("co", coords)
        sp.points.foreach_set("radius", radii)
    cu.materials.append(mat)
    obj = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(obj)
    obj.location = (cx, cy, 0.0)
    return obj, cu


def _emission_color_input(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "EMISSION").inputs["Color"]


def _draw_in(cu, birth, trace_f):
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert("bevel_factor_end", frame=birth)
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert("bevel_factor_end", frame=birth + trace_f)


def _retract(cu, birth, trace_f, start, retract_f):
    """Un-trace (recede) the strokes back to nothing, held until `start`, over `retract_f`."""
    start = max(start, birth + trace_f + 1)
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert("bevel_factor_end", frame=start)
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert("bevel_factor_end", frame=start + retract_f)


def build_lyrics(rcp, frame_w, frame_h, total):
    """Trace each lyric line word-by-word in the free columns beside the dish, retract it when
    the line ends; 'Haha' words stay and drift black->orange, growing subtly to the song end."""
    fps = rcp.fps
    cues = json.load(open(_asset(rcp.cues)))
    r = core.plate_radius(frame_w, frame_h, rcp.plate_frac, rcp.plate_fit)
    m = rcp.col_margin
    cols = {"L": (-frame_w / 2 + m, -r - m), "R": (r + m, frame_w / 2 - m)}
    y_lo, y_hi = -frame_h / 2 + m, frame_h / 2 - m

    ink = make_emission_material("lyric_ink", core.hex_lin(rcp.vein_hex))
    black = core.hex_lin("#000000")
    orange = core.hex_lin(rcp.haha_orange_hex)
    trace_f = max(1, round(rcp.trace_secs * fps))
    retract_f = max(1, round(rcp.retract_secs * fps))
    hold_f = max(0, round(rcp.word_hold_secs * fps))
    haha_fade_f = max(1, round(rcp.haha_fade_secs * fps))
    haha_disappear_f = max(1, round(rcp.haha_disappear_secs * fps))

    n_words = 0
    for cue in cues:
        mask, (gw, gh), (fw_px, fh_px) = load_mask_aspect(
            _asset(cue["png"]), rcp.lyrics_grid, rcp.alpha_thresh)
        edges = plate.edge_points(mask)
        if not edges:
            continue
        n_fil = min(rcp.lyrics_fil_cap, max(300, len(edges) * 3))
        fils_grid = plate.simulate_stamp(mask, edges, n_fil, _rng)

        x0c, x1c = cols[cue["side"]]
        scale = min((x1c - x0c) / gw, (y_hi - y_lo) / gh)
        world_h = gh * scale
        cx_world = (x0c + x1c) / 2.0
        yc_lo, yc_hi = y_lo + world_h / 2.0, y_hi - world_h / 2.0
        cy_world = yc_lo + (yc_hi - yc_lo) * cue.get("ypos", 0.5)

        def to_world(col, row):
            return (cx_world + (col - gw / 2.0) * scale,
                    cy_world + (row - gh / 2.0) * scale)

        def px_to_grid_box(box):
            x0, y0, x1, y1 = box
            c0 = x0 / max(1, fw_px - 1) * (gw - 1)
            c1 = x1 / max(1, fw_px - 1) * (gw - 1)
            ra = (fh_px - 1 - y0) / max(1, fh_px - 1) * (gh - 1)   # top pixel -> higher grid row
            rb = (fh_px - 1 - y1) / max(1, fh_px - 1) * (gh - 1)
            return (min(c0, c1), max(c0, c1), min(ra, rb), max(ra, rb))

        wboxes = [px_to_grid_box(w["box"]) for w in cue["words"]]
        groups = [[] for _ in wboxes]
        for gp in fils_grid:
            sc, sr = gp[0]
            idx = None
            for i, (c0, c1, r0, r1) in enumerate(wboxes):
                if c0 <= sc <= c1 and r0 <= sr <= r1:
                    idx = i
                    break
            if idx is None:
                idx = min(range(len(wboxes)),
                          key=lambda i: ((wboxes[i][0] + wboxes[i][1]) / 2 - sc) ** 2
                                        + ((wboxes[i][2] + wboxes[i][3]) / 2 - sr) ** 2)
            groups[idx].append(gp)

        def build_obj(name, fils, mat):
            world_fils = [([to_world(c, r) for (c, r) in gp], plate.taper_radii(len(gp)))
                          for gp in fils]
            return make_word_object(name, world_fils, rcp.lyrics_bevel, mat)

        for i, w in enumerate(cue["words"]):
            grp = groups[i]
            if not grp:
                continue
            birth = max(1, round(w["start"] * fps))
            leave = round(w["end"] * fps) + hold_f          # per-word disappearance trigger
            letters = "".join(ch for ch in w["w"].lower() if ch.isalpha())

            if rcp.haha_word in letters:
                # split the letters ("Haha") from trailing punctuation (the comma): the letters
                # persist, drift to orange and keep growing outward; the comma un-traces like any word.
                cb = px_to_grid_box(w.get("corebox", w["box"]))
                core_fils = [gp for gp in grp if cb[0] <= gp[0][0] <= cb[1]]
                rest_fils = [gp for gp in grp if not (cb[0] <= gp[0][0] <= cb[1])]
                if core_fils:
                    # turn black -> orange, then slowly un-trace away over ~haha_disappear_secs
                    mat = make_emission_material(f"haha_{cue['id']}", black)
                    obj, cu = build_obj(f"haha_{cue['id']}", core_fils, mat); n_words += 1
                    _draw_in(cu, birth, trace_f)
                    ci = _emission_color_input(mat)
                    ci.default_value = black
                    ci.keyframe_insert("default_value", frame=leave)
                    ci.default_value = orange
                    ci.keyframe_insert("default_value", frame=leave + haha_fade_f)
                    if not cue.get("haha_stay"):
                        _retract(cu, birth, trace_f, leave, haha_disappear_f)
                    # else: the final Haha stays drawn (bevel held at 1) to the song's end
                if rest_fils:
                    obj, cu = build_obj(f"lyr_{cue['id']}_{i}p", rest_fils, ink); n_words += 1
                    _draw_in(cu, birth, trace_f)
                    _retract(cu, birth, trace_f, leave, retract_f)
            else:
                obj, cu = build_obj(f"lyr_{cue['id']}_{i}", grp, ink); n_words += 1
                _draw_in(cu, birth, trace_f)
                _retract(cu, birth, trace_f, leave, retract_f)
    print(f"treatment=lyrics cues={len(cues)} words={n_words}")


# ---------------- encode ----------------
def encode(rcp, out_dir):
    if rcp.encode == "none":
        print("encode: none (frames only) ->", out_dir)
        return
    import shutil
    import subprocess
    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not (shutil.which("ffmpeg") or os.path.exists(ffmpeg)):
        print("ffmpeg not found — skipping encode; frames are in", out_dir)
        return
    frames = os.path.join(out_dir, "frame_%05d.png")
    if rcp.encode == "mp4":
        target = os.path.join(out_dir, f"{rcp.output_name}.mp4")
        codec = ["-c:v", "libx264", "-crf", "12", "-preset", "veryslow", "-pix_fmt", "yuv420p"]
    elif rcp.encode == "mov":
        target = os.path.join(out_dir, f"{rcp.output_name}.mov")
        codec = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    else:
        raise ValueError(f"unknown encode {rcp.encode!r}")
    cmd = [ffmpeg, "-y", "-framerate", str(rcp.fps), "-start_number", "1", "-i", frames,
           *codec, "-movflags", "+faststart", target]
    print("encoding:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        print("wrote", target)
    except (subprocess.CalledProcessError, OSError) as e:
        print("encode failed:", e, "— frames remain in", out_dir)


# ---------------- build ----------------
_rng = random.Random(42)   # random.Random for shapes/births/deaths; reseeded in build()


def build_scene(rcp):
    """Construct the whole scene for the recipe. Returns nothing; leaves a ready scene."""
    global _rng
    np.random.seed(42)
    _rng = random.Random(42)
    clear_scene()

    frame_w, frame_h = core.aspect_frame(rcp.aspect[0], rcp.aspect[1], rcp.ortho_scale)
    total = rcp.total_frames
    tl = core.resolve_timeline(total, rcp.timeline)

    if rcp.treatment in ("reveal", "bloom_overlay"):
        r_world = core.plate_radius(frame_w, frame_h, rcp.plate_frac, rcp.plate_fit)
        art_path = _asset(rcp.art)
        arr = load_rgb(art_path, rcp.img_grid)
        grey, icx, icy, ir = plate.detect_plate(arr)
        agar_edge, _agar_core = plate.estimate_agar(arr, icx, icy, ir)
        setup_world(rcp, grey)
        setup_camera(rcp)
        if rcp.treatment == "reveal":
            build_reveal_photo(art_path, icx, icy, ir, r_world, frame_w, frame_h,
                               rcp.img_grid, tl["hold_end"], tl["dissolve_end"])
        rows, cols, colors = plate.seed_mould(arr, agar_edge, icx, icy, ir, rcp.n_bloom, np.random)
        reps, assign = plate.quantise(colors, rcp.n_swatch)
        fluff_mats = [make_fluff_material(f"fluff_{i}", core.lin4(reps[i]), dissolve=True)
                      for i in range(len(reps))]
        seeds_world = [(((c - icx) / ir) * r_world, ((r - icy) / ir) * r_world)
                       for r, c in zip(rows, cols)]
        last_birth = tl["mould_end"] - tl["bloom_grow"]
        births = [1 + last_birth * (_rng.random() ** rcp.bloom_appear_exp)
                  for _ in range(len(seeds_world))]
        if rcp.treatment == "reveal":
            death_span = (tl["dissolve_end"] - tl["bloom_fade"]) - tl["hold_end"]
            deaths = [tl["hold_end"] + death_span * (_rng.random() ** rcp.bloom_appear_exp)
                      for _ in range(len(seeds_world))]
        else:
            deaths = None
        build_blooms_image(rcp, seeds_world, assign, births, deaths, fluff_mats,
                           tl["mould_end"], tl["bloom_grow"], tl.get("bloom_fade", 0))
        print(f"treatment={rcp.treatment} blooms={len(seeds_world)} swatches={len(reps)}")

    elif rcp.treatment in ("stamp", "stamp_blooms"):
        setup_world(rcp, grey=np.array([0.9, 0.9, 0.9]))
        setup_camera(rcp)
        mask, bbox = load_mask(_asset(rcp.stamp_image), rcp.grid, rcp.alpha_thresh)
        to_world, stamp_half = world_mapping(rcp, bbox, frame_w, frame_h)
        edges = plate.edge_points(mask)
        n_fil = min(rcp.fil_cap, max(400, len(edges) * 3))
        stamp_fils = plate.simulate_stamp(mask, edges, n_fil, _rng)
        vein_mat = make_emission_material("Vein", core.hex_lin(rcp.vein_hex))
        if rcp.treatment == "stamp_blooms":
            palette = list(rcp.bloom_palette_whites) + list(rcp.bloom_palette_darks)
            fluff_mats = {h: make_fluff_material(f"fluff_{h}", core.hex_lin(h), dissolve=False,
                                                 core_alpha=0.85, mid_alpha=0.75) for h in palette}
            build_stamp(rcp, stamp_fils, to_world, vein_mat,
                        tl["reveal_frames"], tl["stamp_grow"], tl["stamp_bucket"])
            build_blooms_scatter(rcp, stamp_half, frame_w, frame_h, fluff_mats,
                                 total, tl["bloom_grow"])
        else:
            build_stamp(rcp, stamp_fils, to_world, vein_mat,
                        tl["reveal_frames"], tl["stamp_grow"], tl["stamp_bucket"])
        print(f"treatment={rcp.treatment} edges={len(edges)} fils={len(stamp_fils)}")

    elif rcp.treatment == "lyrics":
        setup_world(rcp, grey=np.array([0.9, 0.9, 0.9]))   # transparent -> returns early
        setup_camera(rcp)
        build_lyrics(rcp, frame_w, frame_h, total)

    else:
        raise ValueError(f"unhandled treatment {rcp.treatment!r}")

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total


def main():
    args = args_after_ddash()
    recipe_path = get_opt(args, "--recipe")
    if not recipe_path:
        raise SystemExit("need --recipe <path.toml>")
    rcp = recipe_mod.load(recipe_path)
    print(f"recipe={rcp.name} treatment={rcp.treatment} aspect={rcp.aspect} "
          f"duration={rcp.duration_sec}s total_frames={rcp.total_frames}")

    build_scene(rcp)

    out_dir = get_opt(args, "--output", f"/tmp/100pieces_{rcp.name}")
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene

    respct = int(get_opt(args, "--respct", 100))

    if "--frame" in args:                       # single arbitrary frame at --respct
        setup_render(rcp, out_dir, respct)
        f = max(1, int(get_opt(args, "--frame")))
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out_dir, f"frame_{f:05d}")
        bpy.ops.render.render(write_still=True)
    elif "--range" in args:                     # frames A..B (inclusive) at --respct, step --step
        setup_render(rcp, out_dir, respct)
        i = args.index("--range")
        a, b = int(args[i + 1]), int(args[i + 2])
        step = int(get_opt(args, "--step", 1))
        for f in range(max(1, a), b + 1, step):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out_dir, f"frame_{f:05d}")
            bpy.ops.render.render(write_still=True)
    elif "--last" in args:
        setup_render(rcp, out_dir, 100)
        scene.frame_set(rcp.total_frames)
        scene.render.filepath = os.path.join(out_dir, "last_frame")
        bpy.ops.render.render(write_still=True)
    elif "--preview" in args:
        setup_render(rcp, out_dir, 100 if "--fullres" in args else 40)
        frames = (int(round(v)) for v in
                  np.linspace(1, rcp.total_frames - 120, rcp.preview_count))
        for f in frames:
            scene.frame_set(max(1, f))
            scene.render.filepath = os.path.join(out_dir, f"preview_{f:05d}")
            bpy.ops.render.render(write_still=True)
    else:
        setup_render(rcp, out_dir, 100)
        bpy.ops.render.render(animation=True)
        encode(rcp, out_dir)
    print("Done!")


if __name__ == "__main__":
    main()

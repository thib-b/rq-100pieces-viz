"""lyrics_columns — lyrics growing in the side columns, fixed on screen (layer).

Used for verse 1 (beside the dish, black ink) and for the outro's closing lines (beside the
fractal zoom, light "smoke": translucent, rising and swelling as it dissolves). The line set and
look come from the section's `params.lyrics` table (see DEFAULTS).

The Haha filament language (lines traced word-by-word as Helvetica-Neue-shaped filaments), made
slower and more organic: each word traces in over `trace_secs` from its sung start, lingers
`hold_secs` after it's sung, then dissolves — its filaments split into `groups` that un-trace at
staggered (seeded) moments while the word's opacity fades.

The text is fixed on SCREEN (upright, not zooming): everything hangs off a "HUD" empty parented
to the camera whose scale follows the camera's ortho_scale via a driver. Coordinates here are
screen units: the frame is [-fw/2, fw/2] x [-fh/2, fh/2] at magnification 1.

Lines and word times come from tools/nothing_lyrics_<set>.json (tools/nothing_lyric_masks.py).
"""
from __future__ import annotations

import json

from songs.nothing import cues
from songs.nothing.timeline import asset

DEFAULTS = {
    "set": "verse1",             # tools/nothing_lyrics_<set>.json
    "ink": "#000000",
    "opacity": 1.0,              # peak opacity (smoke < 1)
    "fade_in": False,            # also fade opacity in while tracing (smoke)
    "untrace": True,             # filaments recede as the word goes (False: just fade in place)
    "drift": 0.0,                # screen units each dissolving filament group rises
    "swell": 1.0,                # … and scales to, as it dissolves (smoke spreads)
    "trace_secs": 1.6,
    "hold_secs": 2.5,
    "retract_secs": 3.0,
    "groups": 3,                 # filament groups per word, dissolving at staggered moments
    "stagger_secs": 0.9,         # spread of those moments
    "dish_frac": 0.92,           # dish diameter / frame height when the columns are tightest
    "margin": 0.28,              # screen units between dish edge / frame edge and the text
    "gap": 0.15,                 # min vertical gap between two visible lines on the same side
    "bevel": 0.008,
    "grid": 900,                 # long-side sampling of each mask
    "fil_cap": 2200,
    "clear_by": "landing-0.15",  # every line fully gone by then (s, "landing-<s>", or "" = no limit)
}


def layout_path(p):
    return f"tools/nothing_lyrics_{p['set']}.json"


def clear_by(p):
    v = p["clear_by"]
    if v in ("", None):
        return None
    if isinstance(v, str) and v.startswith("landing"):
        return cues.scene1()["landing"] + float(v[len("landing"):] or 0)   # "landing-0.15"
    return float(v)


def _p(ctx):
    return {**DEFAULTS, **ctx.params.get("lyrics", {})}


def columns(fw, fh, p):
    """Screen-space (x0, x1) of the left/right columns and the usable (y0, y1)."""
    r = 0.5 * p["dish_frac"] * fh
    m = p["margin"]
    return ({"L": (-fw / 2 + m, -r - m), "R": (r + m, fw / 2 - m)}, (-fh / 2 + m, fh / 2 - m))


def finish_by(w, last_frame):
    """Re-time a word so it has fully dissolved by `last_frame` (keeps its birth; compresses
    trace/retract/stagger proportionally if there isn't room for them)."""
    tr, rf, st = w["trace"], w["retract"], w["stagger"]
    avail = last_frame - w["birth"] - 1
    need = tr + 1 + rf + st
    if need > avail:
        k = max(avail, 0) / need
        tr, rf, st = max(1, int(tr * k)), max(1, int(rf * k)), int(st * k)
    leave = max(min(w["leave"], last_frame - rf - st), w["birth"] + tr + 1)
    w.update(trace=tr, retract=rf, stagger=st, leave=leave)


def _gone(words):
    return max(w["leave"] + w["retract"] + w["stagger"] for w in words)


def schedule(layout, fw, fh, p, fps, clear_at=None):
    """Pure: place every line (side, vertical position, scale) and time every word (frames).

    Words trace in when sung and dissolve `hold_secs` after. A line goes in the centre of its
    column if free, else beside the lines still visible there; if there's no room at all, the
    older lines on that side are hurried to finish dissolving before the new line starts. With
    `clear_at` (seconds), every word has fully dissolved by then."""
    cols, (y0, y1) = columns(fw, fh, p)
    col_w = cols["R"][1] - cols["R"][0]
    hold_f = round(p["hold_secs"] * fps)
    base = {"trace": round(p["trace_secs"] * fps), "retract": round(p["retract_secs"] * fps),
            "stagger": round(p["stagger_secs"] * fps)}
    last_frame = None if clear_at is None else round(clear_at * fps) + 1
    lines = []
    for c in layout:
        side = "L" if c["id"] % 2 == 0 else "R"
        scale = col_w / c["W"]                 # screen units per mask px
        h = c["H"] * scale
        words = [{"w": w["w"], "box": w["box"], "birth": round(w["start"] * fps) + 1,
                  "leave": round(w["end"] * fps) + 1 + hold_f, **base} for w in c["words"]]
        if last_frame is not None:
            for w in words:
                finish_by(w, last_frame)
        first = min(w["birth"] for w in words)
        same = [ln for ln in lines if ln["side"] == side]
        busy = [(ln["cy"] - ln["h"] / 2, ln["cy"] + ln["h"] / 2, ln["gone"]) for ln in same]
        cy = place(h, first, busy, y0, y1, p["gap"])
        if cy is None:                          # no room: older lines make way
            for ln in same:
                if ln["gone"] >= first:
                    for w in ln["words"]:
                        finish_by(w, first - 1)
                    ln["gone"] = _gone(ln["words"])
            cy = (y0 + y1) / 2
        x0, x1 = cols[side]
        lines.append({"id": c["id"], "png": c["png"], "text": c["text"], "W": c["W"],
                      "H": c["H"], "h": h, "side": side, "cx": (x0 + x1) / 2, "cy": cy,
                      "scale": scale, "first": first, "gone": _gone(words), "words": words})
    return {"lines": lines}


def place(h, first, busy, y0, y1, gap):
    """Vertical centre for a line of height h: the centre of the column if free, else the
    free spot (just above or below a still-visible line) nearest the centre; None if none."""
    active = [(lo, hi) for lo, hi, until in busy if until >= first]
    mid = (y0 + y1) / 2
    lo_ok, hi_ok = y0 + h / 2, y1 - h / 2
    if hi_ok < lo_ok:                           # taller than the column: centre it
        return mid
    cands = [mid] + [c for lo, hi in active for c in (hi + gap + h / 2, lo - gap - h / 2)]
    free = [c for c in cands if lo_ok - 1e-9 <= c <= hi_ok + 1e-9
            and all(c + h / 2 + gap <= lo or c - h / 2 - gap >= hi for lo, hi in active)]
    if not free:                                # tight: push to the column edge, smaller gap
        clamped = [min(max(c, lo_ok), hi_ok) for c in cands]
        free = [c for c in clamped
                if all(c + h / 2 <= lo or c - h / 2 >= hi for lo, hi in active)]
    return min(free, key=lambda c: abs(c - mid)) if free else None


def plan(ctx):
    p = _p(ctx)
    fw, fh = ctx.frame_size
    layout = json.loads(asset(layout_path(p)).read_text())
    sch = schedule(layout, fw, fh, p, ctx.fps, clear_by(p))
    sec = ctx.section
    # only the lines visible somewhere inside this section
    sch["lines"] = [ln for ln in sch["lines"] if ln["first"] <= sec.last and ln["gone"] >= sec.first]
    sch["params"] = p
    return sch


def exit_state(ctx, plan):            # a layer: hands on the base style's State unchanged
    return ctx.enter


def assets(ctx):
    path = layout_path(_p(ctx))
    layout = json.loads(asset(path).read_text())
    return [asset(path)] + [asset(c["png"]) for c in layout]


def build(ctx, plan):
    import bpy
    from engine import core, plate
    from engine import render as eng
    from songs.nothing import build as B
    from songs.nothing.seeding import py_random

    p = plan["params"]
    fw, _ = ctx.frame_size
    cam = B.camera()
    hud = bpy.data.objects.new("lyrics_hud", None)
    bpy.context.collection.objects.link(hud)
    hud.parent = cam
    hud.location = (0.0, 0.0, -1.5)                 # under the camera veil, over the plate
    for i in range(2):                              # x/y scale follow the zoom
        fc = hud.driver_add("scale", i)
        fc.driver.type = "SCRIPTED"
        var = fc.driver.variables.new()
        var.name = "o"
        var.targets[0].id_type = "CAMERA"
        var.targets[0].id = cam.data
        var.targets[0].data_path = "ortho_scale"
        fc.driver.expression = f"o / {fw}"
    ink = core.hex_lin(p["ink"])

    for ln in plan["lines"]:
        mask, (gw, gh), (fw_px, fh_px) = eng.load_mask_aspect(str(asset(ln["png"])), p["grid"],
                                                              0.35)
        edges = plate.edge_points(mask)
        if not edges:
            continue
        rng = ctx.rng("lyric", ln["id"])
        n_fil = min(p["fil_cap"], max(300, len(edges) * 3))
        fils = plate.simulate_stamp(mask, edges, n_fil, py_random(rng))
        g_scale = ln["scale"] * fw_px / gw          # screen units per grid cell

        def to_hud(col, row):
            return (ln["cx"] + (col - gw / 2) * g_scale, ln["cy"] + (row - gh / 2) * g_scale)

        def grid_box(box):
            x0, y0, x1, y1 = box
            c0, c1 = x0 / (fw_px - 1) * (gw - 1), x1 / (fw_px - 1) * (gw - 1)
            ra, rb = (fh_px - 1 - y0) / (fh_px - 1) * (gh - 1), (fh_px - 1 - y1) / (fh_px - 1) * (gh - 1)
            return min(c0, c1), max(c0, c1), min(ra, rb), max(ra, rb)

        boxes = [grid_box(w["box"]) for w in ln["words"]]
        per_word = [[] for _ in boxes]
        for f in fils:
            sc, sr = f[0]
            hit = next((i for i, (c0, c1, r0, r1) in enumerate(boxes)
                        if c0 <= sc <= c1 and r0 <= sr <= r1), None)
            if hit is None:
                hit = min(range(len(boxes)), key=lambda i: ((boxes[i][0] + boxes[i][1]) / 2 - sc) ** 2
                          + ((boxes[i][2] + boxes[i][3]) / 2 - sr) ** 2)
            per_word[hit].append(f)

        for wi, (w, wf) in enumerate(zip(ln["words"], per_word)):
            if not wf:
                continue
            fade_in = (w["birth"], w["birth"] + w["trace"]) if p["fade_in"] else None
            mat = _fading_ink(f"lyr{ln['id']}_{wi}", ink, p["opacity"], fade_in, w["leave"],
                              w["leave"] + w["retract"] + w["stagger"])
            groups = [[] for _ in range(p["groups"])]
            for f in wf:
                groups[int(rng.integers(0, p["groups"]))].append(f)
            offsets = sorted(int(x) for x in rng.integers(0, w["stagger"] + 1, p["groups"]))
            for gi, (grp, off) in enumerate(zip(groups, offsets)):
                if not grp:
                    continue
                world_fils = [([to_hud(c, r) for (c, r) in g], plate.taper_radii(len(g))) for g in grp]
                obj, cu = eng.make_word_object(f"lyr{ln['id']}_{wi}_{gi}", world_fils, p["bevel"], mat)
                loc = tuple(obj.location)
                obj.parent = hud
                obj.location = loc                  # HUD-local == screen units
                eng._draw_in(cu, w["birth"], w["trace"])
                if p["untrace"]:
                    eng._retract(cu, w["birth"], w["trace"], w["leave"] + off, w["retract"])
                if p["drift"] or p["swell"] != 1.0:          # smoke: rise and spread away
                    a = max(w["leave"] + off, w["birth"] + w["trace"] + 1)
                    b = a + w["retract"]
                    obj.keyframe_insert("location", index=1, frame=a)
                    obj.keyframe_insert("scale", frame=a)
                    obj.location[1] = loc[1] + p["drift"]
                    obj.scale = (p["swell"],) * 3
                    obj.keyframe_insert("location", index=1, frame=b)
                    obj.keyframe_insert("scale", frame=b)


def _fading_ink(name, ink, opacity, fade_in, fade_start, fade_end):
    """Emission ink at `opacity`, optionally fading in over the `fade_in` (a, b) frames, then
    easing to 0 between fade_start and fade_end (blended)."""
    import bpy
    from songs.nothing import build as B
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    B._blended(mat)
    nt = mat.node_tree
    nt.nodes.clear()
    val = nt.nodes.new("ShaderNodeValue")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = ink
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(val.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    s = val.outputs[0]
    if fade_in:
        s.default_value = 0.0
        s.keyframe_insert("default_value", frame=fade_in[0])
        s.default_value = opacity
        s.keyframe_insert("default_value", frame=min(fade_in[1], fade_start))
    s.default_value = opacity
    s.keyframe_insert("default_value", frame=fade_start)
    s.default_value = 0.0
    s.keyframe_insert("default_value", frame=max(fade_end, fade_start + 1))
    return mat

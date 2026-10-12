"""nothing_flips — NOTHING typed in capitals, then negative flips (scene 1, 2:07.7 → 2:20.636).

  2:07.73        NOTHING typed, centred, pure black on the paper (Helvetica Neue Bold, as all
                 the lyrics; the paper is the plate's own white, songs/nothing/paper.py)
  2:08.51 → …    one negative flip per sung "Nothing" (11, on the measured "&" hits)
  2:17.13        the music stops: the picture holds (until the flips resume)
  2:17.55 → …    one flip per hand clap (27, measured — sparse, then accelerating into 32nds),
                 all done before the bass and kick come in at 2:20.636: the background keeps
                 alternating paper / its negative, the text pure black / pure white, fading a
                 step more transparent on every flip; the last flip lands on the paper with the
                 text gone, and the bridge carries on on that paper.

Used by both the nothing2 and claps sections: the look is a pure function of global time
(cues.toml), so the two join seamlessly. Colours change with constant keys (hard flips).
"""
from __future__ import annotations

from songs.nothing import cues

DEPENDS = ["songs/nothing/fonts.py", "songs/nothing/paper.py", "songs/nothing/styles/plate_ratchet.py"]

DEFAULTS = {
    "word": "NOTHING",
    "ink": "#000000",
    "paper": "#ffffff",
    "size": 1.5,                # world units at magnification 1 (frame width 10)
    "type_secs": 0.55,          # NOTHING is typed over this long
}


def _p(ctx):
    return {**DEFAULTS, **ctx.params.get("nothing", {})}


def colours_at(t, p=DEFAULTS):
    """(background, text, text opacity) at global time t. The background is the paper (`paper`)
    or its negative (`ink`); the text is always the pure opposite colour, and over the claps it
    loses k = claps/len(claps) of its opacity."""
    flips = sum(1 for f in cues.nothing_flips() if f <= t)
    claps = sum(1 for f in cues.clap_flips() if f <= t)
    k = claps / len(cues.clap_flips())
    inverted = (flips + claps) % 2 == 1
    bg, text = (p["ink"], p["paper"]) if inverted else (p["paper"], p["ink"])
    return bg, text, round(1.0 - k, 6)


def type_frames(fps, p=DEFAULTS):
    """[(frame, prefix_len)] typing the word, first letter on the typed cue."""
    t0, n = cues.nothing_typed(), len(p["word"])
    out = {}
    for k in range(n):
        out[round((t0 + p["type_secs"] * k / n) * fps) + 1] = k + 1
    return sorted(out.items())


def plan(ctx):
    p = _p(ctx)
    sec = ctx.section
    events = sorted({sec.first} | {round(t * ctx.fps) + 1 for t in
                                   cues.nothing_flips() + cues.clap_flips()
                                   if sec.first <= round(t * ctx.fps) + 1 <= sec.last})
    half = 0.5 / ctx.fps                     # an event belongs to the frame it rounds onto
    keys = [(f, *colours_at(ctx.time(f) + half, p)) for f in events]
    typing = [(f, n) for f, n in type_frames(ctx.fps, p)]
    spans = []                                          # visible prefixes in this section
    for k, (f, n) in enumerate(typing):
        last = typing[k + 1][0] - 1 if k + 1 < len(typing) else sec.last
        a, b = max(f, sec.first), min(last, sec.last)
        if a <= b:
            spans.append({"text": p["word"][:n], "first": a, "last": b})
    return {"params": p, "keys": keys, "spans": spans,
            "end": colours_at(ctx.time(sec.last) + half, p)}


def exit_state(ctx, plan):
    bg, fg, alpha = plan["end"]
    if alpha == 0:
        return ctx.enter.with_(background=bg, image="", mode="blank")
    return ctx.enter.with_(background=bg, image="", mode="nothing", text_colour=fg)


def build(ctx, plan):
    import bpy
    from engine import core
    from songs.nothing import build as B
    from songs.nothing import fonts, paper
    p = plan["params"]
    B.set_background(p["paper"])
    negative = paper.build(ctx, invertible=True)
    mat, text_col, text_alpha = _ink_material(B, "nothing_ink", plan["keys"][0][2])
    with B.constant_keys():
        for f, bg, fg, alpha in plan["keys"]:
            negative.default_value = 1.0 if bg == p["ink"] else 0.0
            negative.keyframe_insert("default_value", frame=f)
            text_col.default_value = core.hex_lin(fg)
            text_col.keyframe_insert("default_value", frame=f)
            text_alpha.default_value = alpha
            text_alpha.keyframe_insert("default_value", frame=f)
    paper_mat = bpy.data.objects["paper"].data.materials[0]
    B.make_constant(paper_mat.node_tree, mat.node_tree)
    face = bpy.data.fonts.load(str(fonts.face_path()))

    def text(*a, **kw):
        obj = B.text_object(*a, **kw)
        obj.data.font = face
        return obj

    full = text("nothing_probe", p["word"], p["size"], mat)
    w = B.text_width(full)
    bpy.data.objects.remove(full)
    for si, sp in enumerate(plan["spans"]):
        obj = text(f"nothing_{si}", sp["text"], p["size"], mat, x=-w / 2, align_x="LEFT")
        B.show_between(obj, sp["first"], sp["last"])


def _ink_material(B, name, hexstr, alpha=1.0):
    """Flat unlit colour that can fade out: returns (material, colour socket, opacity socket — a
    Value node's output; keyframe their default_value)."""
    import bpy
    from engine import core
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    B._blended(mat)
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = core.hex_lin(hexstr)
    val = nt.nodes.new("ShaderNodeValue")
    val.outputs[0].default_value = alpha
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(val.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat, em.inputs["Color"], val.outputs[0]

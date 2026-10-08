"""nothing_flips — NOTHING typed in capitals, then negative flips (scene 1, 2:07.7 → 2:20.636).

  2:07.73        NOTHING typed, centred, black on white (Helvetica Neue Medium, as all the lyrics)
  2:08.51 → …    one negative flip per sung "Nothing" (11, on the measured "&" hits)
  2:17.13        the music stops: the picture holds (until the flips resume)
  2:17.55 → …    one flip per hand clap (27, measured — sparse, then accelerating into 32nds),
                 all done before the bass and kick come in at 2:20.636: the background keeps
                 alternating pure black / pure white, while the TEXT fades a step closer to its
                 background on every flip; the last flip lands on white with the text gone, and
                 the bridge carries on in that white.

Used by both the nothing2 and claps sections: the look is a pure function of global time
(cues.toml), so the two join seamlessly. Colours change with constant keys (hard flips).
"""
from __future__ import annotations

from songs.nothing import cues

DEPENDS = ["songs/nothing/fonts.py"]

DEFAULTS = {
    "word": "NOTHING",
    "ink": "#000000",
    "paper": "#ffffff",
    "size": 1.5,                # world units at magnification 1 (frame width 10)
    "type_secs": 0.55,          # NOTHING is typed over this long
}


def _p(ctx):
    return {**DEFAULTS, **ctx.params.get("nothing", {})}


def _hex(rgb):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def colours_at(t, p=DEFAULTS):
    """(background, text) hex at global time t. Backgrounds are always pure ink/paper; over the
    claps the text moves k = claps/12 of the way from full contrast to its background."""
    flips = sum(1 for f in cues.nothing_flips() if f <= t)
    claps = sum(1 for f in cues.clap_flips() if f <= t)
    k = claps / len(cues.clap_flips())
    inverted = (flips + claps) % 2 == 1
    bg, contrast = (p["ink"], p["paper"]) if inverted else (p["paper"], p["ink"])
    text = _hex([c + (b - c) * k for c, b in zip(_rgb(contrast), _rgb(bg))])
    return bg, text


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
    bg, fg = plan["end"]
    if bg == fg:
        return ctx.enter.with_(background=bg, image="", mode="blank")
    return ctx.enter.with_(background=bg, image="", mode="nothing", text_colour=fg)


def build(ctx, plan):
    from songs.nothing import build as B
    p = plan["params"]
    B.set_background(plan["keys"][0][1])
    mat, text_col = B.emission_material("nothing_ink", plan["keys"][0][2])
    world_col = B.world_color_input()
    from engine import core
    with B.constant_keys():
        for f, bg, fg in plan["keys"]:
            world_col.default_value = core.hex_lin(bg)
            world_col.keyframe_insert("default_value", frame=f)
            text_col.default_value = core.hex_lin(fg)
            text_col.keyframe_insert("default_value", frame=f)
    import bpy
    B.make_constant(bpy.context.scene.world.node_tree, mat.node_tree)
    from songs.nothing import fonts
    medium = bpy.data.fonts.load(str(fonts.face_path()))

    def text(*a, **kw):
        obj = B.text_object(*a, **kw)
        obj.data.font = medium
        return obj

    full = text("nothing_probe", p["word"], p["size"], mat)
    w = B.text_width(full)
    bpy.data.objects.remove(full)
    for si, sp in enumerate(plan["spans"]):
        obj = text(f"nothing_{si}", sp["text"], p["size"], mat, x=-w / 2, align_x="LEFT")
        B.show_between(obj, sp["first"], sp["last"])

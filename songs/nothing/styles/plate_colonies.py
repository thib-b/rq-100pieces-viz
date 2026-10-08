"""plate_colonies — the outro opens on black, and the plate's own growths regrow there, at their
real places, sizes and colours, set off by the sleepy piano's phrases (2:58.1 → 3:22.97).

Each piano phrase (cues.toml [scene3].piano_onsets) starts the next colonies: clusters are taken
largest-first, dealt round-robin over the phrases, so every phrase brings one big growth plus
smaller ones. Inside a colony the blooms spread outward from its centre, each swelling in slowly.
The timing lives in colonies.growth(): the last phrases' blooms keep growing after the bass
entry, where the fractal zoom picks up the identical plate and finishes growing them.
"""
from __future__ import annotations

from songs.nothing import colonies, cues

DEPENDS = ["songs/nothing/colonies.py"]

DEFAULTS = {
    "background": "#000000",
    "dish_frac": 0.92,          # dish diameter / frame height (matches the end of scene 1's creep)
    "size_k": 1.6,              # bloom size multiplier (overlap → fluffy, continuous colonies)
    "lobe_seg": 20,
    "core_alpha": 0.92,
    "mid_alpha": 0.80,
}


def _p(ctx):
    return {**DEFAULTS, **ctx.params.get("colonies", {})}


def dish_radius(frame_h, p):
    return 0.5 * p["dish_frac"] * frame_h


cluster_onsets = colonies.cluster_onsets


def plan(ctx):
    p = _p(ctx)
    sec = ctx.section
    _, fh = ctx.frame_size
    R = dish_radius(fh, p)
    data = colonies.data()
    sched = colonies.growth(cues.raw()["scene3"]["piano_onsets"], ctx.fps)
    out = []
    for b in colonies.blooms(R, p["size_k"]):
        birth, full = sched[b["seed"]]
        if birth > sec.last:                      # set off by a late phrase: born in the zoom
            continue
        out.append({**b, "birth": birth, "full": full})
    out.sort(key=lambda b: b["birth"])
    return {"params": p, "dish_r": R, "blooms": out, "n_seeds": len(sched),
            "swatches": data["swatches"]}


def exit_state(ctx, plan):
    return ctx.enter.with_(background=plan["params"]["background"], image="", mode="plate_growing",
                           dish_r=round(plan["dish_r"], 6))


def assets(ctx):
    return [colonies.asset(colonies.DATA)]


def build(ctx, plan):
    import bpy
    from engine import core
    from engine import render as eng
    from songs.nothing import build as B
    p = plan["params"]
    B.set_background(p["background"])
    mats = [eng.make_fluff_material(f"col_{i}", core.hex_lin(h), dissolve=False,
                                    core_alpha=p["core_alpha"], mid_alpha=p["mid_alpha"])
            for i, h in enumerate(plan["swatches"])]
    n = plan["n_seeds"]                            # z by seed over the WHOLE plate, as the zoom
    for b in plan["blooms"]:
        me = eng.colony_mesh(f"col_{b['seed']}", b["lobes"], p["lobe_seg"])
        me.materials.append(mats[b["swatch"]])
        obj = bpy.data.objects.new(f"col_{b['seed']}", me)
        obj.location = (b["x"], b["y"], colonies.z_of(b["seed"], n))   # same stack as the zoom
        bpy.context.collection.objects.link(obj)
        grow_keys(obj, b["birth"], b["full"])
        B.show_between(obj, max(b["birth"], ctx.section.first), ctx.section.last)


def grow_keys(obj, birth, full):
    """Scale 0 → 1 from birth to full (frames; either may lie outside the section) — shared with
    the zoom's level-0 plate so a bloom still growing at the hand-over continues identically."""
    obj.scale = (0.0, 0.0, 0.0)
    obj.keyframe_insert("scale", frame=birth)
    obj.scale = (1.0, 1.0, 1.0)
    obj.keyframe_insert("scale", frame=full)

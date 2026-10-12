"""plate_ratchet — scene 1's plate: ratchet rotation on the kicks + slow zoom, then the fall
into the largest white puff, landing at the downbeat after the band stop on the view that stays
on as the paper of everything after it (songs/nothing/paper.py).

Everything is a pure function of *global* time (cues.toml), so the exposition and first_bridge
sections (which both use this style) join seamlessly and any frame renders on its own.

Geometry (world units, y up): the dish centre is the origin. The photo is shown at a size where
the dish diameter is `start_dish_frac` of the frame height at magnification 1. The camera's
magnification m(t) sets ortho_scale = frame_w / m; its centre c(t) tracks the puff.
"""
from __future__ import annotations

import math

import numpy as np

from songs.nothing import cues
from songs.nothing.timeline import asset

DEFAULTS = {
    "image": "plates/nothing.jpg",
    "ground": "#f3f3f4",              # world colour behind the photo (photo edges feather into it)
    "dish_radius_uv": 0.2923,         # dish (agar) radius as a fraction of the photo's side
    "disc_cut_uv": [0.300, 0.330],    # rotating cut-out: opaque inside, feathered to this radius
    "ground_feather_uv": [0.40, 0.50],  # static photo fades into `ground` between these radii
    "start_dish_frac": 0.70,          # dish diameter / frame height at t=0
    "accel_dish_frac": 0.92,          # … at the start of the accelerating zoom (dish still on screen)
    "target": [-0.349, -0.075],        # zoom target: largest white puff, dish radii, image axes (y down)
    "land_view_radii": 0.10,         # frame height at the landing, in dish radii (inside the puff)
    "step_deg": 15.0,                 # clockwise per ratchet step
    "ease_power": 2.5,                # acceleration through each 2-beat step
    "overshoot_deg": 1.0,             # the mechanical catch after each landing …
    "settle_sixteenths": 1.0,         # … settled within this many 16ths
    "zoom_accel_power": 4.0,          # how sharply the final fall accelerates
}


def _p(ctx):
    return {**DEFAULTS, **ctx.params}


# ---------------- pure motion functions (global time t, seconds) ----------------
def ratchet_angle(t, p=DEFAULTS):
    """Clockwise rotation in degrees at time t: 0 before the first move, then one `step_deg`
    step per 2 beats, each accelerating (ease-in) and landing on a kick, with a damped
    overshoot after each landing. Holds after the last landing."""
    s = cues.scene1()
    step = 2 * cues.beat()
    t0, t_last = s["ratchet_first_move"], s["ratchet_last_land"]
    n_steps = round((t_last - t0) / step)
    if t <= t0:
        return 0.0
    k = min(int((t - t0) // step), n_steps)            # completed steps
    u = 0.0 if k >= n_steps else ((t - t0) - k * step) / step
    angle = p["step_deg"] * (k + u ** p["ease_power"])
    # overshoot bump after the most recent landing (landing k at t0 + k*step, k >= 1)
    if k >= 1:
        since = (t - t0) - k * step
        settle = p["settle_sixteenths"] * cues.sixteenth()
        if 0 <= since < settle:
            v = since / settle
            angle += p["overshoot_deg"] * math.sin(math.pi * v) * (1 - v)
    return angle


def magnification(t, p=DEFAULTS):
    """Zoom factor m(t) ≥ 1: constant log-rate creep until the accel start (dish still fully on
    screen), then an accelerating fall that reaches the puff interior at the landing."""
    s = cues.scene1()
    ta, tl = s["zoom_accel_start"], s["landing"]
    m1 = p["accel_dish_frac"] / p["start_dish_frac"]
    # frame height in dish radii at m: (1 / start_dish_frac) * 2 / m  →  solve for land_view_radii
    m_end = 2.0 / (p["start_dish_frac"] * p["land_view_radii"])
    r = math.log(m1) / ta
    if t <= ta:
        return math.exp(r * max(t, 0.0))
    T = tl - ta
    tau = min(t - ta, T)
    K = math.log(m_end) - math.log(m1) - r * T
    return math.exp(math.log(m1) + r * tau + K * (tau / T) ** p["zoom_accel_power"])


def _smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def camera_center(t, rw, p=DEFAULTS):
    """Camera centre (world) at time t. Before the fall: the dish centre. During the fall it
    homes in on the (rotating) puff so the puff ends exactly centred at the landing."""
    s = cues.scene1()
    ta, tl = s["zoom_accel_start"], s["landing"]
    if t <= ta:
        return (0.0, 0.0)
    th = -math.radians(ratchet_angle(t, p))                     # clockwise = negative
    dx, dy = p["target"][0] * rw, -p["target"][1] * rw          # image y-down → world y-up
    px = dx * math.cos(th) - dy * math.sin(th)
    py = dx * math.sin(th) + dy * math.cos(th)
    m1 = p["accel_dish_frac"] / p["start_dish_frac"]
    w = (m1 / magnification(t, p)) * (1 - _smoothstep((t - ta) / (tl - ta)))
    return (px * (1 - w), py * (1 - w))


# ---------------- style contract ----------------
def plan(ctx):
    p = _p(ctx)
    fw, fh = ctx.frame_size
    rw = 0.5 * p["start_dish_frac"] * fh                 # dish radius in world units
    side = rw / p["dish_radius_uv"]                      # photo side length in world units
    frames = list(ctx.section.frames)
    ts = [ctx.time(f) for f in frames]
    mags = [magnification(t, p) for t in ts]
    centers = [camera_center(t, rw, p) for t in ts]
    return {
        "params": p, "side": side, "rw": rw, "frames": frames,
        "angle_deg": [ratchet_angle(t, p) for t in ts],
        "ortho": [fw / m for m in mags],
        "cam_xy": centers,
    }


def exit_state(ctx, plan):
    landed = ctx.section.last + 1 >= ctx.song.frame_of(cues.scene1()["landing"])
    if landed:
        return ctx.enter.with_(background="#ffffff", image="", mode="blank")
    return ctx.enter.with_(background=plan["params"]["ground"], mode="plate",
                           image=plan["params"]["image"],
                           plate_angle_deg=round(plan["angle_deg"][-1], 4))


def assets(ctx):
    return [asset(_p(ctx)["image"])]


def build(ctx, plan):
    from songs.nothing import build as B
    p = plan["params"]
    B.set_background(p["ground"])
    img = asset(p["image"])
    B.image_plane("photo_ground", img, plan["side"], z=0.0,
                  radial_alpha=tuple(p["ground_feather_uv"]))
    dish = B.image_plane("photo_dish", img, plan["side"], z=0.01,
                         radial_alpha=tuple(p["disc_cut_uv"]))
    cam = B.camera()
    for f, a, o, (cx, cy) in zip(plan["frames"], plan["angle_deg"], plan["ortho"],
                                 plan["cam_xy"]):
        dish.rotation_euler[2] = -math.radians(a)
        dish.keyframe_insert("rotation_euler", index=2, frame=f)
        cam.data.ortho_scale = o
        cam.data.keyframe_insert("ortho_scale", frame=f)
        cam.location[0], cam.location[1] = cx, cy
        cam.keyframe_insert("location", index=0, frame=f)
        cam.keyframe_insert("location", index=1, frame=f)

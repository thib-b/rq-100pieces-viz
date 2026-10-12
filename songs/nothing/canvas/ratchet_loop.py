"""Canvas 3 — the opening ratchet plate, as a perfect loop.

The film turns the plate clockwise one step every 2 beats (accelerating, landing on the kick,
with a small mechanical catch). The plate has no symmetry, so a loop must turn it exactly 360°:
STEPS steps of 360°/STEPS, at the film's beat-locked pace (2 beats a step, 77 bpm). The catch
scales with the step so it feels the same; the landing on frame 1 carries the catch of the loop's
last step, so the last frame flows into the first.

Like the film, only the dish turns (cut out with a feathered edge), over the photo's own static
ground. Pure PIL/numpy.

    .venv/bin/python -m songs.nothing.canvas.ratchet_loop
"""
from __future__ import annotations

import math
import subprocess

import numpy as np
from PIL import Image

from songs.nothing import cues
from songs.nothing.styles import plate_ratchet as pr
from songs.nothing.timeline import REPO

SIZE = (1080, 1920)
FPS = 30
STEPS = 5                     # 5 × 72° in 5 × 2 beats ≈ 7.79 s
DISH = 0.43                   # agar radius / frame width
SS = 2                        # supersampling
OUT = REPO / "renders" / "nothing_canvas" / "ratchet_loop"


def period():
    return STEPS * 2 * cues.beat()


def frames():
    return round(period() * FPS)        # the loop is retimed by < 0.2% to whole frames


def angle(t, p=pr.DEFAULTS):
    """Clockwise degrees at loop time t ∈ [0, period): the film's eased step + damped catch."""
    step_t = 2 * cues.beat()
    deg = 360.0 / STEPS
    k, rem = divmod(t, step_t)
    u = rem / step_t
    a = deg * (k + u ** p["ease_power"])
    settle = p["settle_sixteenths"] * cues.sixteenth()
    if rem < settle:                    # just landed (t = 0 is the previous loop's last landing)
        v = rem / settle
        a += p["overshoot_deg"] * deg / p["step_deg"] * math.sin(math.pi * v) * (1 - v)
    return a


def _smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def render(p=pr.DEFAULTS):
    out = OUT / "frames"
    out.mkdir(parents=True, exist_ok=True)
    W, H = SIZE[0] * SS, SIZE[1] * SS
    photo = Image.open(REPO / p["image"]).convert("RGB")
    side = photo.size[0]
    k = DISH * W / (p["dish_radius_uv"] * side)          # photo px → work px
    n_px = round(side * k)
    photo = photo.resize((n_px, n_px), Image.LANCZOS)
    ground = np.array([int(pr.DEFAULTS["ground"][i:i + 2], 16) for i in (1, 3, 5)], float)
    canvas = np.empty((H, W, 3))
    canvas[:] = ground
    x0, y0 = (W - n_px) // 2, (H - n_px) // 2

    def place(img):                     # photo (n_px²) centred on the work canvas
        c = canvas.copy()
        a = np.asarray(img, float)
        sx0, sy0 = max(0, -x0), max(0, -y0)
        dx0, dy0 = max(0, x0), max(0, y0)
        w, h = min(n_px - sx0, W - dx0), min(n_px - sy0, H - dy0)
        c[dy0:dy0 + h, dx0:dx0 + w] = a[sy0:sy0 + h, sx0:sx0 + w]
        return c

    yy, xx = np.mgrid[:H, :W]
    r_uv = np.hypot(xx - (x0 + n_px / 2), yy - (y0 + n_px / 2)) / n_px
    g0, g1 = p["ground_feather_uv"]
    d0, d1 = p["disc_cut_uv"]
    a_ground = (1 - _smooth((r_uv - g0) / (g1 - g0)))[..., None]
    a_dish = (1 - _smooth((r_uv - d0) / (d1 - d0)))[..., None]
    static = canvas * (1 - a_ground) + place(photo) * a_ground
    n = frames()
    for f in range(n):
        t = f * period() / n
        turned = place(photo.rotate(-angle(t, p), resample=Image.BICUBIC,
                                    fillcolor=tuple(int(g) for g in ground)))
        img = static * (1 - a_dish) + turned * a_dish
        Image.fromarray((img + 0.5).astype(np.uint8)).resize(SIZE, Image.LANCZOS) \
            .save(out / f"frame_{f + 1:05d}.png")
    print(f"{n} frames = {n / FPS:.3f} s ({STEPS} × {360 / STEPS:g}°, one step per 2 beats); "
          f"angle at the wrap: {angle(period() - 1e-9, p) % 360:.4f}° → {angle(0.0, p):.4f}°")
    mp4 = OUT / "nothing_canvas_ratchet_loop.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS),
                    "-i", str(out / "frame_%05d.png"), "-c:v", "libx264", "-preset", "slow",
                    "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                    str(mp4)], check=True)
    print(f"wrote {mp4}")


if __name__ == "__main__":
    render()

"""Canvas 2 — a stack of plates: holes bloom through the top one like moulds, grow and take
over the whole plate, revealing the plate beneath — which then blooms open in turn. The last
plate opens onto the first again, so the loop is seamless by construction.

Pure numpy/PIL (no Blender). Every plate photo is registered on its own dish (detected circle):
same centre, same radius, colour-matched to one shared ground, so each plate sits exactly where
the one above it was — one looks like it grows inside the other.

    .venv/bin/python -m songs.nothing.canvas.plate_stack
"""
from __future__ import annotations

import subprocess

import numpy as np
from PIL import Image

from songs.nothing.seeding import section_rng
from songs.nothing.timeline import REPO

SPORES = "/Users/thib/dev/the100-visual-assets/spores-pics/100 pieces_1080 x 1080{}.jpg"
PLATES = [SPORES.format(n) for n in (100, 57, 90, 98)]   # green, blue, pink, sepia: seeded
                                                      # random picks of distinctly dyed plates
SIZE = (1080, 1920)            # 9:16
FPS = 30
PHASE_FRAMES = 58              # per plate: 4 plates → 232 frames = 7.73 s (Spotify: 3–8 s)
HOLD = 0.06                    # of each phase, the plate shown whole before it starts to open
DISH = 0.42                    # dish radius / frame width
GROUND = (234.0, 235.0, 237.0)  # the shared cream ground (the photos' own, averaged)
BLOOM = {
    "seeds": 13,               # holes per plate
    "spawn": 0.6,              # holes are born over this much of the opening (accelerating)
    "reach": 0.6,              # a hole's radius when its plate is fully open (dish radii)
    "flood_from": 0.75,        # from here every hole also swells together, …
    "cover_by": 0.98,          # … so nothing is left of the plate by here
    "lobes": 0.07,             # each hole's outline: harmonics 3–7 of this amplitude (lobed)
    "ragged": 0.035,           # fine edge roughness (dish radii)
    "soft": 0.03,              # edge blur (dish radii)
    "fringe": 0.3,             # a pale, fuzzy mould fringe along the growing edge (opacity)
}
OUT = REPO / "renders" / "nothing_canvas" / "plate_stack"


def find_dish(img, n=600):
    """(cx, cy, r) of the dish in an image's pixels: a circle fitted to the outermost
    non-ground pixel along 720 rays (outliers — moulds over the rim — rejected)."""
    w = img.size[0]
    a = np.asarray(img.convert("RGB").resize((n, n), Image.LANCZOS), float)
    border = np.concatenate([a[:20].reshape(-1, 3), a[-20:].reshape(-1, 3),
                             a[:, :20].reshape(-1, 3), a[:, -20:].reshape(-1, 3)])
    ground = np.median(border, 0)
    m = np.linalg.norm(a - ground, axis=2) > 30
    yy, xx = np.mgrid[:n, :n]
    cx, cy = xx[m].mean(), yy[m].mean()
    rs = np.arange(5, n * 0.49)
    for _ in range(4):
        pts = []
        for th in np.linspace(0, 2 * np.pi, 720, endpoint=False):
            x = (cx + rs * np.cos(th)).astype(int)
            y = (cy + rs * np.sin(th)).astype(int)
            ok = (x >= 0) & (x < n) & (y >= 0) & (y < n)
            hit = np.nonzero(m[y[ok], x[ok]])[0]
            if len(hit):
                pts.append((x[ok][hit[-1]], y[ok][hit[-1]]))
        p = np.array(pts, float)
        r = np.hypot(p[:, 0] - cx, p[:, 1] - cy)
        p = p[np.abs(r - np.median(r)) < 0.04 * np.median(r)]
        A = np.c_[2 * p[:, 0], 2 * p[:, 1], np.ones(len(p))]
        cx, cy, c = np.linalg.lstsq(A, (p ** 2).sum(1), rcond=None)[0]
        rad = np.sqrt(c + cx * cx + cy * cy)
    s = w / n
    return cx * s, cy * s, rad * s, ground


def layer(path):
    """The plate registered on the frame: dish centred, radius DISH × width, ground → GROUND."""
    img = Image.open(path).convert("RGB")
    cx, cy, r, ground = find_dish(img)
    W, H = SIZE
    k = DISH * W / r                                   # photo px → frame px
    # affine: frame (u, v) → photo (x, y)
    data = (1 / k, 0, cx - (W / 2) / k, 0, 1 / k, cy - (H / 2) / k)
    a = np.asarray(img.transform(SIZE, Image.AFFINE, data, resample=Image.BICUBIC,
                                 fillcolor=tuple(int(g) for g in ground)), float)
    a = a * (np.array(GROUND) / ground)                # colour-match the ground
    # beyond the dish, fade the photo into the flat shared ground (vignette, photo edges)
    yy, xx = np.mgrid[:H, :W]
    d = np.hypot(xx - W / 2, yy - H / 2) / (DISH * W)
    f = np.clip((d - 1.12) / 0.2, 0, 1)
    f = f * f * (3 - 2 * f)
    return np.clip(a * (1 - f[..., None]) + np.array(GROUND) * f[..., None], 0, 255)


def _noise(rng, shape, cells):
    """Smooth value noise in [-1, 1] (a random grid, bicubic-upsampled)."""
    h, w = shape
    g = rng.random((max(2, round(cells * h / w)), cells)).astype(np.float32)
    im = Image.fromarray(g).resize((w, h), Image.BICUBIC)
    return np.asarray(im) * 2 - 1


def blooms(i):
    """Plate i's holes: seeded centres (dish radii, inside the dish) and birth times (0 → 1 of
    the opening), plus its ragged-edge field."""
    rng = section_rng("nothing", "canvas-plate-stack", i)
    n = BLOOM["seeds"]
    births = BLOOM["spawn"] * np.sort(rng.random(n)) ** 0.7
    births[0] = 0.0
    rr = 0.85 * np.sqrt(rng.random(n))
    th = rng.random(n) * 2 * np.pi
    lobes = [(rng.normal(0, BLOOM["lobes"], 5), rng.random(5) * 2 * np.pi) for _ in range(n)]
    W, H = SIZE
    edge = 0.6 * _noise(rng, (H, W), 18) + 0.4 * _noise(rng, (H, W), 60)
    return np.c_[rr * np.cos(th), rr * np.sin(th)], births, lobes, edge


def holes(tau, centres, births, lobes, edge):
    """(hole opacity — 1 = see-through —, edge fringe) of the TOP plate at opening progress
    tau ∈ [0, 1]."""
    W, H = SIZE
    R = DISH * W
    yy, xx = np.mgrid[:H, :W]
    x, y = (xx - W / 2) / R, (yy - H / 2) / R
    d = np.full((H, W), np.inf, np.float32)
    for i, ((cx, cy), b) in enumerate(zip(centres, births)):
        if tau <= b:
            continue
        g = (tau - b) / (1 - b)
        amp, ph = lobes[i]
        ang = np.arctan2(y - cy, x - cx)
        shape = 1 + sum(a * np.cos(k * ang + p) for k, a, p in zip(range(3, 8), amp, ph))
        d = np.minimum(d, np.hypot(x - cx, y - cy) - BLOOM["reach"] * g ** 1.4 * shape)
    fl = np.clip((tau - BLOOM["flood_from"]) / (BLOOM["cover_by"] - BLOOM["flood_from"]), 0, 1)
    d = d - 3.0 * fl ** 3                                  # the frame corners are < 2.2 radii out
    d = d + BLOOM["ragged"] * edge
    s = BLOOM["soft"]
    h = np.clip((s - d) / (2 * s), 0, 1)
    on_dish = np.clip((1.02 - np.hypot(x, y)) / 0.04, 0, 1)      # no fringe on the bare ground
    fringe = BLOOM["fringe"] * on_dish * np.exp(-((d - 1.5 * s) / (2 * s)) ** 2)
    return h * h * (3 - 2 * h), fringe


def frames():
    return len(PLATES) * PHASE_FRAMES


def render():
    out = OUT / "frames"
    out.mkdir(parents=True, exist_ok=True)
    layers = [layer(p) for p in PLATES]
    fields = [blooms(i) for i in range(len(PLATES))]
    per = PHASE_FRAMES
    n = frames()
    worst = 0.0
    for f in range(n):
        i, k = divmod(f, per)
        tau = min(max((k / per - HOLD) / (1 - HOLD), 0.0), 1.0)
        top, under = layers[i], layers[(i + 1) % len(layers)]
        h, fringe = holes(tau, *fields[i])
        if k == per - 1:                         # last frame of a phase: the plate must be gone
            worst = max(worst, float(1 - h.min()))
        img = top * (1 - h[..., None]) + under * h[..., None]
        img = img + (248.0 - img) * (fringe * (1 - h))[..., None]     # only on the plate side
        Image.fromarray((img + 0.5).astype(np.uint8)).save(out / f"frame_{f + 1:05d}.png")
    print(f"{n} frames = {n / FPS:.2f} s; plate left on a phase's last frame: {worst:.4f}")
    mp4 = OUT / "nothing_canvas_plate_stack.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS),
                    "-i", str(out / "frame_%05d.png"), "-c:v", "libx264", "-preset", "slow",
                    "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                    str(mp4)], check=True)
    print(f"wrote {mp4}")


if __name__ == "__main__":
    render()

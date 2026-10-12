"""Canvas 4 — the Nothing plate as the DVD screensaver logo, bouncing off the screen edges.

A perfect loop needs both bounces periodic within it: the plate makes X_TRIPS horizontal round
trips for every Y_TRIPS vertical ones, so after one loop it is back exactly where it started,
moving the same way. With 2 : 1 the path is close to the classic diagonal. The two bounces are
phased apart so the plate never hits (or nearly hits) a corner: whenever it meets the top or
bottom it is mid-width, and its side hits fall at uneven heights, so the path looks less regular.

The plate is plates/nothing_plate_cutout.png (the dish cut out of the photo, transparent
around it). Pure PIL/numpy.

    .venv/bin/python -m songs.nothing.canvas.dvd_loop
"""
from __future__ import annotations

import subprocess

import numpy as np
from PIL import Image

from songs.nothing.timeline import REPO

SIZE = (1080, 1920)
FPS = 30
FRAMES = 234                  # 7.8 s
PLATE = REPO / "plates" / "nothing_plate_cutout.png"
DIAMETER = 400                # px
X_TRIPS, Y_TRIPS = 2, 1       # round trips per loop, each way
START_X, START_Y = 0.07, 0.225  # each bounce's phase at frame 1: 0.155 apart, clear of corners
BACKGROUND = (0xf3, 0xf3, 0xf4)  # the opening's ground: the plate photo's own light grey
OUT = REPO / "renders" / "nothing_canvas" / "dvd_loop"


def _tri(u):
    """0 → 1 → 0 over each unit of u: one round trip between the two walls."""
    u = u % 1.0
    return 2 * u if u < 0.5 else 2 - 2 * u


def position(s):
    """Top-left corner (px) of the plate at loop phase s ∈ [0, 1)."""
    W, H = SIZE
    return ((W - DIAMETER) * _tri(X_TRIPS * (s + START_X)),
            (H - DIAMETER) * _tri(Y_TRIPS * (s + START_Y)))


def nearest_corner():
    """Closest the plate ever gets to a corner (px from the corner position)."""
    W, H = SIZE
    best = float("inf")
    for f in range(FRAMES * 8):
        x, y = position(f / (FRAMES * 8))
        best = min(best, np.hypot(min(x, W - DIAMETER - x), min(y, H - DIAMETER - y)))
    return best


def render():
    out = OUT / "frames"
    out.mkdir(parents=True, exist_ok=True)
    plate = Image.open(PLATE).convert("RGBA").resize((DIAMETER, DIAMETER), Image.LANCZOS)
    pad = 2
    tile = Image.new("RGBA", (DIAMETER + 2 * pad, DIAMETER + 2 * pad), (0, 0, 0, 0))
    tile.alpha_composite(plate, (pad, pad))
    # premultiplied, so sub-pixel resampling doesn't drag dark fringes in from the transparency
    t = np.asarray(tile, float) / 255
    tile_pm = np.dstack([t[..., :3] * t[..., 3:], t[..., 3:]])
    bands = [Image.fromarray(tile_pm[..., i].astype(np.float32)) for i in range(4)]
    for f in range(FRAMES):
        x, y = position(f / FRAMES)
        ix, iy = int(np.floor(x)), int(np.floor(y))
        fx, fy = x - ix, y - iy
        shifted = np.dstack([np.asarray(b.transform(b.size, Image.AFFINE,
                                                    (1, 0, -fx, 0, 1, -fy),
                                                    resample=Image.BICUBIC)) for b in bands])
        shifted = np.clip(shifted, 0, 1)
        frame = np.empty((SIZE[1], SIZE[0], 3))
        frame[:] = np.array(BACKGROUND, float) / 255
        x0, y0 = ix - pad, iy - pad
        h, w = shifted.shape[:2]
        sx0, sy0 = max(0, -x0), max(0, -y0)
        ex, ey = min(w, SIZE[0] - x0), min(h, SIZE[1] - y0)
        reg = frame[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex]
        src = shifted[sy0:ey, sx0:ex]
        reg[:] = src[..., :3] + reg * (1 - src[..., 3:])
        Image.fromarray((frame * 255 + 0.5).astype(np.uint8)).save(out / f"frame_{f + 1:05d}.png")
    print(f"{FRAMES} frames = {FRAMES / FPS:.2f} s; nearest a corner ever gets: {nearest_corner():.0f} px")
    mp4 = OUT / "nothing_canvas_dvd_loop.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS),
                    "-i", str(out / "frame_%05d.png"), "-c:v", "libx264", "-preset", "slow",
                    "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                    str(mp4)], check=True)
    print(f"wrote {mp4}")


if __name__ == "__main__":
    render()

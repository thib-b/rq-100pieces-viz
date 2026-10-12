"""Canvas 1 — the outro's spinning Droste fractal, as a perfect loop.

The fractal is self-similar: one nesting level later (zoomed k×, turned by φ) the picture is
exactly what it was, nested plates' growth included (each grows over the one level it takes to
reach it). So exactly one level, at the film's pace (2 bars ≈ 6.23 s), loops with no seam.

The film's extra screen roll (7°/s) would break that unless it made whole turns, so it is dropped
and folded into the spiral instead: φ = 68° per level ≈ the film's 24° spiral + 43.6° of roll
per level, so the screen spins at the film's rate and the spin loops for free.

    .venv/bin/python -m songs.nothing.canvas.fractal_loop check   # pure checks (no Blender)
    blender -b --python canvas.py -- fractal_loop                  # render + encode
"""
from __future__ import annotations

import math
from types import SimpleNamespace

from songs.nothing import cues
from songs.nothing.styles import droste_zoom as dz
from songs.nothing.timeline import REPO

SIZE = (1080, 1920)            # 9:16, Spotify's 1080 px tall maximum … in portrait
FPS = 30
ORTHO = 10.0                   # world frame width
LOOP = {
    "bars_per_level": 2.0,     # the film's zoom pace: one level per 2 bars
    "phi_deg": 68.0,           # spiral turn per level (the film's spiral + roll, see above)
    "start_level": 4,          # deep enough that every kept slot is a nested plate (no level 0)
}
OUT = REPO / "renders" / "nothing_canvas" / "fractal_loop"


def params():
    """droste_zoom params for the loop: steady spiral (no ramps), no roll, no fade."""
    return {**dz.DEFAULTS, "phi_deg": LOOP["phi_deg"], "bars_per_level": LOOP["bars_per_level"],
            "roll_deg_per_s": 0.0, "strings_start": 0.0, "fade_start": 1e9}


def frames():
    """Frames in one loop: one level, rounded to whole frames."""
    return round(LOOP["bars_per_level"] * cues.bar() * FPS)


def time_of_level(lam, p):
    """The global time droste_zoom.level() maps to λ (its steady, linear part)."""
    tb = cues.raw()["scene3"]["bass_entry"]
    te = p["ease_bars"] * cues.bar()
    return tb + te / 2 + lam * p["bars_per_level"] * cues.bar()


def frame_size():
    w, h = SIZE
    return ORTHO, ORTHO * h / w


def dish_radius(p):
    """World dish radius: the film's dish/short-side ratio, so the portrait shows as much plate
    across its width as the film does across its height."""
    return 0.5 * p["dish_frac"] * min(frame_size())


def plan(extra=0):
    """Per-frame instance rows for frames 1 … N(+extra): λ = start + (f−1)/N exactly."""
    p, n = params(), frames()
    fr = list(range(1, n + 1 + extra))
    inst = [dz.instances(time_of_level(LOOP["start_level"] + (f - 1) / n, p), p) for f in fr]
    from songs.nothing import colonies
    return {"params": p, "R": dish_radius(p), "frames": fr, "inst": inst,
            "slots": p["levels"] + 1 + dz.ANCESTORS, "fade": [0.0] * len(fr), "zero": [],
            "swatches": colonies.data()["swatches"]}


def covered(row, p, R):
    """Is the whole screen inside the outermost kept ancestor's dish (nothing black behind)?"""
    fw, fh = frame_size()
    hw, hh = fw / 2 / R, fh / 2 / R
    (cx, cy), s = min(((xy, s) for a, xy, s, *_ in row), key=lambda r: -r[1])
    return all(math.hypot(x - cx, y - cy) < 0.9 * s for x in (-hw, hw) for y in (-hh, hh))


def check():
    pl = plan(extra=1)
    p, n = pl["params"], frames()
    first, wrap = pl["inst"][0], pl["inst"][n]          # frame 1 and frame N+1
    key = lambda r: (round(r[1][0], 9), round(r[1][1], 9), round(r[2], 9),    # noqa: E731
                     round(math.remainder(r[3], 2 * math.pi), 9), r[4], round(r[5], 9))
    same = sorted(map(key, first)) == sorted(map(key, wrap))
    cov = sum(covered(r, p, pl["R"]) for r in pl["inst"][:n])
    print(f"{n} frames = {n / FPS:.3f} s @ {FPS} fps; frame N+1 == frame 1: {same}; "
          f"screen covered by the kept ancestors on {cov}/{n} frames")
    return same and cov == n


def render():
    import subprocess

    import bpy
    from songs.nothing import build as B
    pl = plan(extra=1)                                   # N+1: the wrap frame, to verify the seam
    n = frames()
    song = SimpleNamespace(aspect=SIZE, fps=FPS, ortho_scale=ORTHO)
    frames_dir = OUT / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    B.reset_scene(song, frames_dir / "frame_#####")
    ctx = SimpleNamespace(fps=FPS, section=SimpleNamespace(first=1, last=n + 1))
    dz.build(ctx, pl)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, n + 1
    bpy.ops.render.render(animation=True)
    import numpy as np
    a, b = (np.asarray(bpy.data.images.load(str(frames_dir / f"frame_{f:05d}.png")).pixels[:])
            for f in (1, n + 1))
    print(f"loop seam: frame {n + 1} vs frame 1, max diff {np.abs(a - b).max() * 255:.2f}/255")
    mp4 = OUT / "nothing_canvas_fractal_loop.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS),
                    "-i", str(frames_dir / "frame_%05d.png"), "-frames:v", str(n),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(mp4)], check=True)
    print(f"wrote {mp4}")


if __name__ == "__main__":
    import sys
    sys.exit(0 if check() else 1)

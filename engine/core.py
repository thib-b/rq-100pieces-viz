"""Pure, bpy-free math and helpers shared by every treatment.

These functions carry the two "features" that used to be a per-file copy-paste:

* Aspect ratio — `aspect_frame` + `plate_radius` reproduce the three legacy touch points
  (world frame size, and fitting the dish to the SHORT dimension) for any resolution, so
  16:9 / 9:16 / 1:1 (and anything else) come from one code path driven by the recipe.
* Time / warp — `resolve_timeline` turns phase *fractions* into absolute frame numbers for
  a given total length. Because phases are fractions of the total, changing a recipe's
  duration reflows the whole choreography proportionally: the same sequencing of phases,
  relative to the end length.
"""
from __future__ import annotations

import numpy as np


# ---------------- colour ----------------
def srgb_to_linear(c):
    """Scalar sRGB (0-1) -> linear."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_to_linear_arr(a):
    """Vectorised sRGB (0-1 ndarray) -> linear."""
    a = np.asarray(a, dtype=np.float64)
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def lin4(srgb3):
    """(r,g,b) sRGB -> (r,g,b,1.0) linear, for a Blender colour input."""
    return (srgb_to_linear(float(srgb3[0])), srgb_to_linear(float(srgb3[1])),
            srgb_to_linear(float(srgb3[2])), 1.0)


def hex_lin(hexstr):
    """'#rrggbb' -> (r,g,b,1.0) linear."""
    h = hexstr.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)) + (1.0,)


def smootherstep(p):
    """Ken Perlin's smootherstep, floored at 0.04 so a grown-in scale never hits exactly 0."""
    s = p * p * p * (p * (p * 6 - 15) + 10)
    return 0.04 + 0.96 * s


# ---------------- aspect ratio ----------------
def aspect_frame(res_x, res_y, ortho_scale):
    """World-space (width, height) the orthographic camera sees.

    ortho_scale maps to WIDTH (the engine pins camera sensor_fit='HORIZONTAL'), so width is
    always ortho_scale and height follows the pixel aspect. Matches the legacy formula
    frame_w, frame_h = ORTHO_SCALE, ORTHO_SCALE * (RES_Y / RES_X).
    """
    return float(ortho_scale), float(ortho_scale) * (res_y / res_x)


def plate_radius(frame_w, frame_h, plate_frac, fit="short"):
    """Radius (world units) of the petri dish.

    'short' fits the dish to the shorter world dimension (min(w,h)/2 * frac); this single
    rule reproduces all three legacy cases: landscape used frame_h (the short side),
    vertical used min(w,h) (= frame_w, the short side), square used frame_h (= frame_w).
    """
    if fit == "short":
        base = min(frame_w, frame_h)
    elif fit == "height":
        base = frame_h
    elif fit == "width":
        base = frame_w
    else:
        raise ValueError(f"unknown fit {fit!r}")
    return plate_frac * base / 2.0


# ---------------- time / warp ----------------
def resolve_timeline(total_frames, fracs):
    """Map a dict of phase *fractions* (of the total) to absolute frame numbers.

    Every value is round(frac * total_frames), floored at 1. Phase boundaries and spans
    (grow/fade) are all fractions, so a shorter or longer `total_frames` rescales the entire
    choreography uniformly — the warp/time-scale feature.
    """
    return {k: max(1, int(round(v * total_frames))) for k, v in fracs.items()}


def total_frames(duration_sec, fps):
    return int(round(duration_sec * fps))


# ---------------- frame subsample (uniform speed-up) ----------------
def pick_even(n, target):
    """Indices [0..n-1] of `target` evenly spaced frames, inclusive of both ends.

    Canonical copy of make_short.py's frame picker (the post-render uniform time-lapse).
    """
    if target >= n:
        return list(range(n))
    if target == 1:
        return [0]
    return [round(i * (n - 1) / (target - 1)) for i in range(target)]

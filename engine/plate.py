"""Pure, bpy-free image analysis: petri-dish detection, agar colour estimation, bloom
seeding/palette quantisation, and the stamp vein random-walk.

Everything here takes plain numpy arrays, so it is unit-testable without Blender. The
engine loads pixels via bpy and hands the numpy arrays to these functions.
"""
from __future__ import annotations

import math

import numpy as np


# ---------------- grid resampling (bpy hands us full-res pixels) ----------------
def resample_grid(px, grid):
    """Nearest-sample an (H,W,3) array down to (grid,grid,3) on an even index lattice."""
    h, w = px.shape[:2]
    rows = np.linspace(0, h - 1, grid).astype(int)
    cols = np.linspace(0, w - 1, grid).astype(int)
    return px[np.ix_(rows, cols)].copy()


def mask_from_alpha(alpha, grid, thresh):
    """Resample an (H,W) alpha array to (grid,grid) and threshold it to a boolean mask."""
    h, w = alpha.shape[:2]
    rows = np.linspace(0, h - 1, grid).astype(int)
    cols = np.linspace(0, w - 1, grid).astype(int)
    return alpha[np.ix_(rows, cols)] > thresh


# ---------------- plate detection / agar estimate ----------------
def detect_plate(arr):
    """Find the dish: background grey from the 4 corners, then the centre/radius of the
    non-grey region (area-based radius is outlier-proof). Returns (grey, cx, cy, r)."""
    grey = arr[[0, 0, -1, -1], [0, -1, 0, -1]].mean(axis=0)
    diff = np.linalg.norm(arr - grey, axis=2)
    ys, xs = np.where(diff > 0.10)
    icx, icy = float(np.median(xs)), float(np.median(ys))
    ir = math.sqrt(len(xs) / math.pi) * 1.02
    return grey, icx, icy, ir


def estimate_agar(arr, icx, icy, ir):
    """Estimate the warm agar rim/core colours from the annulus just inside the dish edge."""
    grid = arr.shape[0]
    yy, xx = np.mgrid[0:grid, 0:grid]
    d = np.sqrt((xx - icx) ** 2 + (yy - icy) ** 2) / ir
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    br = (r + g + b) / 3.0
    warm = (d > 0.80) & (d < 0.965) & (r > 0.45) & (r > g) & (g >= b) & \
           ((r - b) > 0.10) & (br > 0.35) & (br < 0.82)
    agar_edge = arr[warm].mean(axis=0) if warm.any() else np.array([0.86, 0.56, 0.36])
    agar_core = np.clip(agar_edge * np.array([1.02, 0.92, 0.80]), 0, 1)
    return agar_edge, agar_core


# ---------------- bloom seeding + palette ----------------
def seed_mould(arr, agar_edge, icx, icy, ir, n, np_random):
    """Sample n bloom seed positions across the whole disc (denser where there's detail).

    Placement uses the passed np.random.RandomState-like object (default np.random) — the
    legacy code used the global np.random after np.random.seed(42); the engine keeps that.
    Returns (rows, cols, colors) in the grid coordinate system.
    """
    grid = arr.shape[0]
    yy, xx = np.mgrid[0:grid, 0:grid]
    dist = np.sqrt((xx - icx) ** 2 + (yy - icy) ** 2)
    diff = np.linalg.norm(arr - agar_edge, axis=2)
    detail = np.clip(diff / 0.6, 0, 1)
    weight = np.where(dist <= ir * 0.99, 0.5 + 0.6 * detail, 0.0)
    w = weight.reshape(-1)
    w = w / w.sum()
    idx = np_random.choice(grid * grid, size=n, p=w)
    rows, cols = idx // grid, idx % grid
    return rows.astype(float), cols.astype(float), arr[rows, cols]


def quantise(colors, k):
    """Reduce sampled colours to the k most common representatives; return (reps, assign)."""
    L = 6
    q = np.clip((colors * L).astype(int), 0, L - 1)
    keys = q[:, 0] * L * L + q[:, 1] * L + q[:, 2]
    uniq, inv, counts = np.unique(keys, return_inverse=True, return_counts=True)
    reps = np.stack([colors[inv == i].mean(axis=0) for i in range(len(uniq))])
    top = np.argsort(counts)[::-1][:k]
    top_reps = reps[top]
    d = ((colors[:, None, :] - top_reps[None, :, :]) ** 2).sum(axis=2)
    return top_reps, d.argmin(axis=1)


# ---------------- stamp vein simulation ----------------
def edge_points(mask):
    """Boundary cells of a boolean mask (a cell that is set but has a non-set 4-neighbour)."""
    up = np.zeros_like(mask); up[:-1, :] = mask[1:, :]
    dn = np.zeros_like(mask); dn[1:, :] = mask[:-1, :]
    lf = np.zeros_like(mask); lf[:, :-1] = mask[:, 1:]
    rt = np.zeros_like(mask); rt[:, 1:] = mask[:, :-1]
    edge = mask & ~(up & dn & lf & rt)
    ys, xs = np.where(edge)
    return list(zip(xs.tolist(), ys.tolist()))


def simulate_stamp(mask, edges, n_fil, rng):
    """Grow n_fil filaments: seed on the letterform outline, random-walk while staying inside
    the mask. `rng` is a random.Random for reproducibility. Returns a list of point-lists."""
    H, W = mask.shape

    def inmask(x, y):
        xi, yi = int(x), int(y)
        return 0 <= xi < W and 0 <= yi < H and mask[yi, xi]

    fils = []
    if not edges:
        return fils
    for _ in range(n_fil):
        ex, ey = edges[rng.randrange(len(edges))]
        ang = rng.uniform(0, 2 * math.pi)
        x, y = float(ex), float(ey)
        pts = [(x, y)]
        for _ in range(rng.randint(16, 46)):
            ang += rng.uniform(-0.62, 0.62)
            step = rng.uniform(0.9, 1.7)
            nx, ny = x + math.cos(ang) * step, y + math.sin(ang) * step
            if inmask(nx, ny):
                x, y = nx, ny
                pts.append((x, y))
            else:
                ang = rng.uniform(0, 2 * math.pi)
        if len(pts) >= 2:
            fils.append(pts)
    return fils


def taper_radii(n):
    """Per-point curve radius tapering from 1.0 down to 0.22 along a filament."""
    return [1.0 - 0.78 * (i / (n - 1)) for i in range(n)] if n > 1 else [1.0]

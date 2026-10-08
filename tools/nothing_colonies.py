#!/usr/bin/env python3
"""Analyse the Nothing plate once → plates/nothing_colonies.json (committed).

The outro regrows the plate's own growths on black: same places, sizes and colours. This finds
the growth clusters (connected regions that differ from the navy agar) and scatters bloom seeds
inside them, each coloured by the photo at that spot (quantised to a few swatches, as in Haha).
Pillow is needed, which Blender's Python lacks — hence a committed data file.

    .venv/bin/python tools/nothing_colonies.py

Coordinates are in DISH RADII from the dish centre, y UP (world convention); radii likewise.
"""
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from engine import plate  # noqa: E402

G = 600                 # analysis grid (px)
N_SEEDS = 1600
N_SWATCH = 28
GROWTH_DIFF = 0.30      # colour distance from the agar that counts as growth (not halo)
MIN_CLUSTER_PX = 30     # ignore specks smaller than this (at G)
SPLIT_AREA = 3000       # regions bigger than this (px at G) are split at their bright cores …
SPLIT_SEP = 0.22        # … with cores at least this far apart (dish radii)
SEED = 20261007


def hexof(rgb):
    return "#" + "".join(f"{int(round(255 * float(c))):02x}" for c in rgb)


def main():
    Image.MAX_IMAGE_PIXELS = None
    im = np.asarray(Image.open(REPO / "plates/nothing.jpg").convert("RGB")
                    .resize((G, G), Image.LANCZOS), float) / 255
    br = im.mean(2)
    dark = br < 0.30
    rows = np.where(dark.sum(1) > 3)[0]
    cols = np.where(dark.sum(0) > 3)[0]
    cx, cy = (cols.min() + cols.max()) / 2, (rows.min() + rows.max()) / 2
    R = ((cols.max() - cols.min()) + (rows.max() - rows.min())) / 4
    yy, xx = np.mgrid[0:G, 0:G]
    d = np.hypot(xx - cx, yy - cy) / R
    inside = d < 0.965
    agar = np.median(im[inside & (br < 0.25)], axis=0)

    # growth = clearly different from the agar (soft-blurred to merge fluffy edges)
    k = np.fft.fftfreq(G)
    K = np.exp(-2 * (np.pi * 1.5) ** 2 * (k[:, None] ** 2 + k[None, :] ** 2))
    diff = np.linalg.norm(im - agar, axis=2)
    diff_b = np.real(np.fft.ifft2(np.fft.fft2(diff) * K))
    growth = inside & (diff_b > GROWTH_DIFF)

    # connected clusters (4-neighbour flood fill)
    label = -np.ones((G, G), int)
    clusters = []
    for y0, x0 in zip(*np.where(growth)):
        if label[y0, x0] >= 0:
            continue
        q, pts = deque([(y0, x0)]), []
        label[y0, x0] = len(clusters)
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < G and 0 <= nx < G and growth[ny, nx] and label[ny, nx] < 0:
                    label[ny, nx] = len(clusters)
                    q.append((ny, nx))
        clusters.append(np.array(pts))
    keep = [i for i, c in enumerate(clusters) if len(c) >= MIN_CLUSTER_PX]

    # touching puffs merge into one region: split big regions at their brightness peaks (each
    # puff's bright core), giving every pixel to the nearest peak
    Kp = np.exp(-2 * (np.pi * 9) ** 2 * (k[:, None] ** 2 + k[None, :] ** 2))
    br_b = np.real(np.fft.ifft2(np.fft.fft2(br) * Kp))
    min_sep = SPLIT_SEP * R
    for i in list(keep):
        pts = clusters[i]
        if len(pts) < SPLIT_AREA:
            continue
        vals = br_b[pts[:, 0], pts[:, 1]]
        peaks = []
        for j in np.argsort(-vals):
            y, x = pts[j]
            win = br_b[max(0, y - 6):y + 7, max(0, x - 6):x + 7]
            if vals[j] < win.max() - 1e-9:
                continue                                   # not a local maximum
            if all(np.hypot(y - py, x - px) >= min_sep for py, px in peaks):
                peaks.append((y, x))
        if len(peaks) < 2:
            continue
        pk = np.array(peaks)
        owner = np.argmin(((pts[:, None, :] - pk[None, :, :]) ** 2).sum(2), axis=1)
        keep.remove(i)
        for o in range(len(peaks)):
            sub = pts[owner == o]
            if len(sub) < MIN_CLUSTER_PX:
                continue
            label[sub[:, 0], sub[:, 1]] = len(clusters)
            keep.append(len(clusters))
            clusters.append(sub)

    out_clusters = []
    remap = {}
    for i in sorted(keep, key=lambda i: -len(clusters[i])):
        pts = clusters[i]
        py, px = pts[:, 0].mean(), pts[:, 1].mean()
        remap[i] = len(out_clusters)
        out_clusters.append({
            "id": len(out_clusters),
            "x": round((px - cx) / R, 4), "y": round(-(py - cy) / R, 4),
            "r": round(np.sqrt(len(pts) / np.pi) / R, 4),
            "area": int(len(pts)),
            "colour": hexof(im[pts[:, 0], pts[:, 1]].mean(axis=0)),
        })

    # bloom seeds inside the kept clusters, denser where the photo is brighter/detailed
    rng = np.random.default_rng(SEED)
    member = np.isin(label, keep)
    w = np.where(member, 0.4 + np.clip(diff_b, 0, 1), 0.0).reshape(-1)
    idx = rng.choice(G * G, size=N_SEEDS, p=w / w.sum(), replace=False)
    sr, sc = idx // G, idx % G
    colours = im[sr, sc]
    reps, assign = plate.quantise(colours, N_SWATCH)
    seeds = []
    for r_, c_, a in zip(sr, sc, assign):
        cl = remap[label[r_, c_]]
        size = out_clusters[cl]["r"]
        seeds.append({"x": round((c_ - cx) / R, 4), "y": round(-(r_ - cy) / R, 4),
                      # bloom radius: a fraction of its cluster, clamped (dots stay dots)
                      "r": round(float(np.clip(0.22 * size + rng.uniform(-0.01, 0.01), 0.012, 0.07)), 4),
                      "swatch": int(a), "cluster": cl})
    data = {
        "source": "plates/nothing.jpg", "grid": G,
        "dish": {"cx": round(cx / G, 4), "cy": round(cy / G, 4), "r": round(R / G, 4)},
        "agar": hexof(agar),
        "swatches": [hexof(c) for c in reps],
        "clusters": out_clusters,
        "seeds": seeds,
    }
    dst = REPO / "plates/nothing_colonies.json"
    dst.write_text(json.dumps(data, indent=1))
    print(f"agar {data['agar']}  clusters {len(out_clusters)}  seeds {len(seeds)} -> {dst}")
    for c in out_clusters[:20]:
        n = sum(1 for s in seeds if s["cluster"] == c["id"])
        print(f"  {c['id']:2d} ({c['x']:+.2f},{c['y']:+.2f}) r={c['r']:.3f} area={c['area']:5d} "
              f"{c['colour']} seeds={n}")


if __name__ == "__main__":
    main()

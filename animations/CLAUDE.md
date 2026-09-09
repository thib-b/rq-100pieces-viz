# Haha single — animation render pipeline (cold-start)

This directory holds the real music-video animation for the **"Haha" single**. Read this before
touching anything — it lets a fresh session start warm.

## What is (and isn't) the real code

- **The animation is `animations/haha_reveal.py`** — one self-contained Blender headless Python
  script. This is what you edit and render. `animations/slime_mold_reveal.py` is an older variant
  (a stamp-reveal treatment) kept for reference.
- **Ignore the repo-root scaffold**: `render.py`, `test_render.py`, `scenes/`, `scripts/`,
  root `README.md`, `BLENDER_HEADLESS_GUIDE.md`. That's a generic cubes/spheres Blender-pipeline
  demo and has nothing to do with this video.

## The video (current version)

On bare light-grey, ~2400 soft "fluffy bloom" colonies grow into the petri-dish area, each colored
by sampling the source artwork, so together they reconstruct the picture. Then the blooms **fade
out** to reveal the real, full-resolution artwork photograph underneath. Beat map (FPS = 60):

| Time | Frame | What happens |
|------|-------|--------------|
| 0:00 → 1:55 | 1 → 6900 | Blooms appear on an accelerating ("exponential") curve; full coverage at 1:55 |
| 1:55 → 2:15 | 6900 → 8100 | Held still — nothing changes |
| 2:15 → 3:01 | 8100 → 10860 | Blooms **fade to transparent** one-by-one (accelerating, random order); real plate photo fades in underneath |
| 3:01 → 3:13 | 10860 → 11580 | Static: the revealed plate photo, cropped to the dish |

## Assets

- Source artwork: `/Users/thib/dev/the100-visual-assets/Haha-Artwork.jpg` (`ART_PATH`). The blooms
  sample it (color) AND it is the photo revealed at the end (used at full resolution).
- The artwork on disk was **flipped vertically (top-to-bottom mirror)** on 2026-09-02 for the current
  orientation. Both the blooms and the reveal read the same file, so they stay consistent.
- (The `hundred_pieces_stamp.png` stamp used by an earlier version is no longer used.)

## Render environment

- Blender binary: `/opt/homebrew/bin/blender` (Blender 5.2.1 LTS).
- Renderer: EEVEE, orthographic camera, `view_transform = 'Standard'`.
- Output: PNG RGBA frames `frame_XXXXX.png` (fixed 5-digit pad) at 2048×1152. The PNG frames are the
  true lossless master. A **full render auto-encodes** them to `<output>/haha_reveal.mp4` via
  `encode_mp4()` (ffmpeg H.264, **crf 12, preset veryslow**, yuv420p, 60fps, **silent** — audio is
  added by thibault himself). Quality preference: keep it near-visually-lossless, never a small/lossy
  default — the final held frame is a complex high-res photo; down-compression is done afterward.
- Latest render output: `render_haha_v4/` (v4 = transparency-fade dissolve + full-res reveal).
  Earlier `render_haha*/` dirs are prior versions kept for comparison.

## How to render (args go after `--`)

```bash
# preview — 30 frames evenly spread across the timeline, fast broad check (~40% res; --fullres = 100%)
/opt/homebrew/bin/blender --background --python animations/haha_reveal.py -- --preview --output DIR

# final frame only — quick full-res spot-check (writes last_frame.png)
/opt/homebrew/bin/blender --background --python animations/haha_reveal.py -- --last --output DIR

# full render — all 11580 frames at 100%, then auto-encodes DIR/haha_reveal.mp4
/opt/homebrew/bin/blender --background --python animations/haha_reveal.py -- --output DIR
```
The `--preview` frames come from `np.linspace(1, TOTAL_FRAMES-120, 30)` in the `--preview` branch of
`main()` — change the count/range there. Always run a `--preview` (and/or `--last`) before a full
render; a full render is ~2h + a slow encode.

## Timing / tuning knobs (config block at top of `haha_reveal.py`)

- `FPS`, `DURATION_SEC`, `TOTAL_FRAMES` — length. Frame N ↔ song time = seconds × FPS.
- `MOULD_END` (full coverage at 1:55), `BLOOM_GROW`, `N_BLOOM`, `BLOOM_APPEAR_EXP` — the accelerating
  build. `BLOOM_APPEAR_EXP < 1` back-loads births (slower start; smaller = slower). The **same
  exponent shapes the dissolve**, so build and dissolve accelerate symmetrically.
- `HOLD_END`, `DISSOLVE_END`, `BLOOM_FADE` — the hold, then the fade-out dissolve (`BLOOM_FADE` =
  frames each bloom takes to fade to transparent).

## How the two tricky bits work

- **Bloom dissolve = opacity fade, not shrink.** Blooms grow in via `scale` (0.001→1). They die by
  fading `obj.color` alpha 1→0, keyframed per bloom in `build_blooms()`. `make_fluff_material()`
  multiplies its spherical ramp by **Object Info → Alpha** (each object's `obj.color[3]`), so one
  shared material fades each bloom independently. Do NOT go back to scaling to 0 — the look is a
  see-through fade at full size.
- **Reveal photo is full-resolution.** `build_reveal_photo()` loads `ART_PATH` **directly as a
  Blender image texture** (full ~4500px) on a plane at z=0 behind the blooms; the circular dish crop
  + feathered rim + the `reveal` 0→1 fade are all done in **shader nodes** (Object-coord radial mask
  × a keyframed `reveal` Value node across `HOLD_END → DISSOLVE_END`). Do NOT reintroduce the old
  downsampled-numpy-plane version — that caused the pixelated reveal.

## Gotchas

- **Random seeds are fixed** (`np.random.seed(42)`, `random.Random(42)`) for reproducibility.
- **Two RNGs**: bloom *placement* uses `np.random`; bloom *birth/death times* and *shapes* use the
  `rng` (`random.Random`). Reordering or inserting `rng` draws changes the visual result — keep the
  call order in `main()` intact when editing.
- `build_base_plane()` (clean orange agar dish) exists but is intentionally **not called**.

## Bigger-picture plans (not yet done)

There is a plan to publish this as a self-contained, recipe-driven GitHub repo (`rq-100pieces-viz`),
where each song is a recipe (plate image + timestamps), the engine is renamed `100pieces.py` (and the
stamp variant `100pieces-stamp.py`), private until the song releases. Ask thibault before acting on it.
</content>

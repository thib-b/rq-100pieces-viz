# rq-100pieces-viz

Recipe-driven, headless-Blender pipeline that renders petri-dish "bloom reveal" music
videos for **The 100** (starting with the *Haha* single). Soft "fluffy bloom" colonies
grow onto a dish to reconstruct a song's artwork, then dissolve away to reveal the real
photograph underneath — plus stamp-drawing and overlay variants of the same visual world.

Everything a song needs is a small **recipe** (a plate image + a timeline + a few knobs), so
new songs and new formats are data, not new copies of the code.

## Requirements

- [Blender](https://www.blender.org/) 5.x — the engine runs in Blender's bundled Python
  (which already includes numpy). Default binary path: `/opt/homebrew/bin/blender`.
- `ffmpeg` on your `PATH` — used to auto-encode the rendered frames into a master.

Nothing else to install to render. (The test harness has its own deps; see *Tests*.)

## Render a recipe

Arguments go after `--`:

```bash
# full render (all frames) -> auto-encodes a master into the output dir
blender --background --python 100pieces.py -- --recipe recipes/haha_landscape.toml --output out/haha

# fast spot-checks
blender --background --python 100pieces.py -- --recipe recipes/haha_landscape.toml --last --output out/check
blender --background --python 100pieces.py -- --recipe recipes/haha_vertical.toml --preview --fullres --output out/prev
```

Modes: `--last` (final frame only), `--preview [--fullres]` (a spread of frames; 40% res
unless `--fullres`), or no mode flag for the full render. `--output DIR` sets where frames and
the encoded master go. Frames are `frame_#####.png` (5-digit pad); the master is named after
the recipe.

## Recipes

A recipe is a TOML file in [`recipes/`](recipes/). It picks a **treatment**, points at an image
in [`plates/`](plates/), and sets the format and tuning. Fields not given fall back to
per-treatment defaults (see [`engine/recipe.py`](engine/recipe.py)).

| Treatment | What it does | Background | Encodes |
|-----------|--------------|-----------|---------|
| `reveal` | blooms reconstruct the artwork, hold, then dissolve to reveal the photo | grey | H.264 mp4 |
| `bloom_overlay` | blooms reconstruct the artwork on a transparent film, then hold | transparent | ProRes 4444 mov (alpha) |
| `stamp` | the stamp letterforms draw themselves in on a transparent film | transparent | ProRes 4444 mov (alpha) |
| `stamp_blooms` | the stamp draws in with blooms growing everywhere around it | deep orange | frames only |

Shipped recipes: `haha_landscape` (16:9), `haha_vertical` (9:16), `haha_bloom_overlay`
(1:1), `stamp_white`, `stamp_black`, `stamp_blooms`.

**Two things that used to mean copying a whole script are now recipe fields:**

- **Aspect ratio** — `aspect = "landscape" | "vertical" | "square"` (or `[width, height]`).
  One engine renders 16:9, 9:16, and 1:1; the dish is fit to the short dimension for any ratio.
- **Length / warp** — the phase boundaries are stored as *fractions* of the total, so changing
  `duration_sec` reflows the whole choreography proportionally: the same sequencing of phases,
  scaled to the new end length. (For a uniform speed-up of an already-rendered sequence, see
  the legacy `animations/make_short.py`.)

### Add a new song

1. Drop the artwork in `plates/<song>.jpg` (or a stamp mask PNG).
2. Copy a recipe, e.g. `recipes/haha_landscape.toml` → `recipes/<song>_landscape.toml`, and
   point `art`/`stamp_image` at your plate. Adjust `duration_sec`, `aspect`, or any knob.
3. `--preview` it, then do the full render.

## Layout

```
100pieces.py        entry point (run under Blender)
engine/
  core.py           pure math: colour, aspect-ratio, warp/timeline, frame subsample
  plate.py          pure image analysis: dish detection, seeding, palette, stamp vein walk
  recipe.py         the Recipe dataclass + TOML loader + per-treatment defaults
  render.py         the Blender engine: consumes a recipe, builds the scene, renders, encodes
recipes/            one TOML per song/format
plates/             committed source images (artwork, stamp mask)
tests/              unit tests (pure logic) + golden characterization tests (render one frame)
animations/         LEGACY standalone scripts, kept as historical artifacts (see below)
```

`engine/core.py` and `engine/plate.py` are deliberately free of `bpy`, so they run — and are
unit-tested — under a plain Python interpreter; only `engine/render.py` imports Blender.

## Legacy scripts

[`animations/`](animations/) holds the original standalone scripts that produced the released
Haha renders (`haha_reveal.py`, `haha_reveal_vertical.py`, `haha_bloom_overlay.py`,
`stamp_overlay.py`, `slime_mold_reveal.py`, `make_short.py`). They are **kept unchanged as
artifacts** — the recipe engine is a clean re-implementation for future work, not a replacement
of that history. The golden tests render one frame of each so they keep working.

## Tests

The suite mixes fast pure-logic unit tests with golden characterization tests that render a
single frame per treatment (~1–3s each) and compare a downsampled thumbnail, guarding both the
exact output resolution (aspect ratio) and the visual content.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest            # everything (needs Blender for the golden tests)
.venv/bin/python -m pytest -m "not blender"   # pure-logic tests only, no Blender needed
```

Regenerate golden thumbnails after a deliberate visual change:
`.venv/bin/python tests/gen_goldens.py`.

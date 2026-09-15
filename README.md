# rq-100pieces-viz

Recipe-driven, headless-Blender pipeline that renders petri-dish "bloom reveal" music
videos as used in Robocobra Quartet's *Hundred Pieces* music videos. (starting with the *Haha* single). Soft "fluffy bloom" colonies
grow onto a dish to reconstruct a song's artwork, then dissolve away to reveal the real
photograph underneath — plus stamp-drawing and overlay variants of the same visual world.

Everything a song needs is a small **recipe** (a plate image + a timeline + a few knobs), so
new songs and new formats are data, not new copies of the code.
:wq
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

For targeted work (used a lot when tuning the lyrics overlay) there are three more modes:

```bash
# a single frame, at a chosen resolution %
blender --background --python 100pieces.py -- --recipe recipes/haha_lyrics_test.toml --frame 5790 --respct 40 --output out/spot

# an inclusive frame range (optionally every Nth frame with --step)
blender --background --python 100pieces.py -- --recipe recipes/haha_lyrics_test.toml --range 630 900 --respct 100 --output out/win
```

- `--frame N` renders just frame `N`; `--range A B [--step S]` renders frames `A..B`.
- `--respct N` sets the resolution percentage (e.g. `--respct 40` for a quick low-res pass);
  `--last`/`--preview` set their own, and the full render is always 100%.
- Both write `frame_#####.png` at the real frame indices, so they splice straight back into a
  full sequence — handy for re-rendering only the frames a change actually touches.

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
| `lyrics` | song lyrics trace themselves in word-by-word beside the dish, then un-trace; for compositing over another render | transparent | frames only (you composite + encode — see below) |

Shipped recipes: `haha_landscape` (16:9), `haha_vertical` (9:16), `haha_bloom_overlay`
(1:1), `stamp_white`, `stamp_black`, `stamp_blooms`, `haha_lyrics` (16:9 lyrics overlay, 60fps)
and `haha_lyrics_test` (30fps, for fast look-tests).

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

## Lyrics overlay (the `lyrics` treatment)

The `lyrics` treatment renders a song's lyrics as a **transparent overlay** to composite over an
existing plate render (e.g. the Haha reveal) — it does **not** produce a finished video on its
own (`encode = "none"`). Each line traces itself in **word-by-word**, synced to the vocal via
forced alignment, in Helvetica-Neue-referenced black filaments in the free columns beside the
dish, then un-traces away; "Haha" words fade black→orange (and the last one stays to the end).

Song-specific data lives under a `haha_` prefix (`tools/haha_lyrics.txt`, `haha_cues.json`, …)
and `plates/haha_lyrics/`; the scripts in `tools/` are generic. Pipeline (Haha as the example):

```bash
# 1. lyrics text -> per-line alpha masks + word boxes
.venv/bin/python tools/make_lyrics_masks.py            # -> plates/haha_lyrics/*.png, tools/haha_lyrics_layout.json

# 2. forced-align the lyrics to the master audio for word timings
#    (needs stable-ts/torch in a separate .venv-align — NOT committed)
.venv-align/bin/python tools/align_lyrics.py --audio "Robocobra Quartet - Haha.wav"   # -> tools/haha_align_words_large.json

# 3. merge masks + timings into cues (applies tools/haha_time_fixes.json, clamps durations,
#    places lines L/R, flags the final Haha to stay)
.venv/bin/python tools/build_cues.py                   # -> tools/haha_cues.json

# 4. render the transparent overlay (60fps, all frames)
blender --background --python 100pieces.py -- --recipe recipes/haha_lyrics.toml --output out/haha_lyrics_ov
#    fast look-tests: recipes/haha_lyrics_test.toml at 30fps with --frame / --range --respct 40

# 5. composite over the plate, hold its last frame to the audio length, mux the master bit-exact
ffmpeg -y \
  -framerate 60 -start_number 1 -i renders/render_haha_v4/frame_%05d.png \
  -framerate 60 -start_number 1 -i out/haha_lyrics_ov/frame_%05d.png \
  -i "Robocobra Quartet - Haha.wav" \
  -filter_complex "[0]tpad=stop=38:stop_mode=clone[p];[p][1]overlay=format=auto,format=yuv420p[v]" \
  -map "[v]" -map 2:a -c:v libx264 -crf 10 -preset slow -c:a copy -shortest -movflags +faststart \
  out/haha_lyrics.mov
```

In the composite: `-c:a copy` keeps the mastered audio **bit-exact** (never re-encode a music
master), `-shortest` ends the video exactly when the audio does, and `tpad=stop=38` holds the
plate's last frame for the tail (here 38 frames) so the picture lasts as long as the audio —
set that to `audio_frames − plate_frames`. Because PCM can't live in an `.mp4`, the output is an
`.mov` (H.264 video + PCM audio); YouTube accepts it, or re-export via DaVinci if preferred.

## Layout

```
100pieces.py        entry point (run under Blender)
engine/
  core.py           pure math: colour, aspect-ratio, warp/timeline, frame subsample
  plate.py          pure image analysis: dish detection, seeding, palette, stamp vein walk
  recipe.py         the Recipe dataclass + TOML loader + per-treatment defaults
  render.py         the Blender engine: consumes a recipe, builds the scene, renders, encodes
recipes/            one TOML per song/format
plates/             committed source images (artwork, stamp mask, lyric masks)
tools/              lyrics pipeline: mask generation, forced alignment, cue building (+ song data)
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

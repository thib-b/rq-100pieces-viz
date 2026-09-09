"""Unit tests for engine.recipe — parsing, defaults, aspect presets, and warp coupling."""
import textwrap

import pytest

from engine import core, recipe


def test_minimal_reveal_gets_defaults():
    r = recipe.from_dict({"name": "haha", "treatment": "reveal", "art": "x.jpg"})
    assert r.background == "grey"
    assert r.n_bloom == 2400
    assert r.encode == "mp4"
    assert set(r.timeline) == {"mould_end", "hold_end", "dissolve_end",
                               "bloom_grow", "bloom_fade"}
    assert r.total_frames == 11580
    assert r.output_name == "haha"          # defaults to name


def test_aspect_presets_and_explicit():
    assert recipe.from_dict({"name": "a", "treatment": "reveal",
                             "aspect": "vertical"}).aspect == (1152, 2048)
    assert recipe.from_dict({"name": "a", "treatment": "reveal",
                             "aspect": [800, 600]}).aspect == (800, 600)
    assert recipe.from_dict({"name": "a", "treatment": "reveal",
                             "aspect": {"width": 100, "height": 200}}).aspect == (100, 200)


def test_bad_aspect_preset_raises():
    with pytest.raises(ValueError):
        recipe.from_dict({"name": "a", "treatment": "reveal", "aspect": "widescreen"})


def test_unknown_treatment_and_unknown_key_raise():
    with pytest.raises(ValueError):
        recipe.from_dict({"name": "a", "treatment": "nonsense"})
    with pytest.raises(ValueError):
        recipe.from_dict({"name": "a", "treatment": "reveal", "bogus_key": 1})


def test_stamp_blooms_defaults():
    r = recipe.from_dict({"name": "s", "treatment": "stamp_blooms",
                          "stamp_image": "stamp.png"})
    assert r.background == "orange"
    assert r.n_bloom == 130
    assert r.encode == "none"
    assert r.bloom_palette_whites and r.bloom_palette_darks


def test_timeline_override_merges_over_defaults():
    r = recipe.from_dict({"name": "s", "treatment": "reveal",
                          "timeline": {"mould_end": 0.5}})
    assert r.timeline["mould_end"] == 0.5             # overridden
    assert r.timeline["hold_end"] == 8100 / 11580     # default retained


def test_duration_change_warps_phase_frames_proportionally():
    base = recipe.from_dict({"name": "s", "treatment": "reveal"})
    short = recipe.from_dict({"name": "s", "treatment": "reveal", "duration_sec": 96.5})
    full_tl = core.resolve_timeline(base.total_frames, base.timeline)
    short_tl = core.resolve_timeline(short.total_frames, short.timeline)
    assert short_tl["mould_end"] == pytest.approx(full_tl["mould_end"] / 2, abs=2)


def test_load_from_toml_file(tmp_path):
    p = tmp_path / "song.toml"
    p.write_text(textwrap.dedent("""
        treatment = "reveal"
        art = "plates/song.jpg"
        aspect = "square"
        duration_sec = 120
    """))
    r = recipe.load(p)
    assert r.name == "song"          # from filename
    assert r.treatment == "reveal"
    assert r.aspect == (2048, 2048)
    assert r.duration_sec == 120

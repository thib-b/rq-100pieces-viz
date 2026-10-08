"""The cue grid agrees with itself and with the section map (pure)."""
import pytest

from songs.nothing import cues, timeline


def test_grid_constants():
    assert cues.beat() == pytest.approx(0.77928)
    assert cues.bar() == pytest.approx(3.11712)
    assert cues.downbeat(0) == pytest.approx(12.0555, abs=1e-3)


def test_ratchet_lands_on_kicks_and_ends_on_the_landing():
    land = cues.ratchet_landings()
    assert len(land) == 57
    assert all(cues.is_kick_beat(t) for t in land)
    assert land[-1] == pytest.approx(cues.scene1()["landing"], abs=2e-3)
    s = cues.scene1()
    assert s["ratchet_first_land"] - s["ratchet_first_move"] == pytest.approx(2 * cues.beat(), abs=1e-3)


def test_landing_is_a_downbeat():
    t = cues.scene1()["landing"]
    assert cues.is_kick_beat(t)
    assert any(abs(cues.downbeat(k) - t) < 2e-3 for k in range(20, 40))


def test_flip_counts_and_order():
    flips = cues.nothing_flips()
    assert len(flips) == 11
    assert cues.nothing_typed() < flips[0]
    assert flips[-1] < cues.scene1()["music_stop"]
    claps = cues.clap_flips()
    s1 = cues.scene1()
    assert len(claps) == 27 and claps == sorted(claps)
    assert s1["music_stop"] < claps[0] and claps[-1] < s1["strings_bridge"]   # all before the bass
    gaps = [b - a for a, b in zip(claps, claps[1:])]
    assert max(gaps[:5]) > min(gaps[-10:]) * 1.5            # the claps accelerate


def test_section_map_matches_cues():
    song = timeline.load()
    s1 = cues.scene1()
    start = {s.id: s.start_sec for s in song.sections}
    assert start["verse2"] == pytest.approx(s1["landing"], abs=1e-3)
    assert start["nothing2"] == pytest.approx(cues.nothing_typed(), abs=1e-3)
    assert start["claps"] == pytest.approx(s1["music_stop"], abs=1e-3)
    assert start["strings_bridge"] == pytest.approx(s1["strings_bridge"], abs=1e-3)

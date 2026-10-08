"""Pure tests for the Nothing section pipeline (no Blender)."""
import re
from pathlib import Path

import pytest

from songs.nothing import manifest, timeline
from songs.nothing.lyrics import Lyrics, Word
from songs.nothing.seeding import section_rng
from songs.nothing.state import State

REPO = Path(__file__).resolve().parents[1]


def song_dict(**over):
    d = {"name": "t", "fps": 60, "aspect": "landscape", "duration_sec": 10.0,
         "initial": {"background": "#f5f5f5", "image": ""},
         "section": [
             {"id": "a", "style": "hold", "start": 0.0, "params": {"background": "#111111"}},
             {"id": "b", "style": "hold", "start": 4.0},
             {"id": "c", "style": "hold", "start": 7.5, "params": {"background": "#222222"}},
         ]}
    d.update(over)
    return d


# ---------------- timeline ----------------
def check_tiling(song):
    secs = song.sections
    assert secs[0].first == 1 and secs[-1].last == song.total_frames
    for a, b in zip(secs, secs[1:]):
        assert b.first == a.last + 1                   # no gaps, no overlaps
    assert sum(len(s.frames) for s in secs) == song.total_frames


def test_real_song_tiles_and_matches_audio_length():
    song = timeline.load()
    check_tiling(song)
    assert song.total_frames == 18597                  # 309.945601 s @ 60fps, rounded up
    assert song.aspect == (2048, 1152)


def test_synthetic_tiling_and_snapping():
    song = timeline.from_dict(song_dict())
    check_tiling(song)
    assert [s.first for s in song.sections] == [1, 241, 451]
    assert song.section_at_frame(450).id == "b" and song.section_at_frame(451).id == "c"


@pytest.mark.parametrize("bad", [
    {"section": [{"id": "a", "style": "hold", "start": 1.0}]},                     # not at 0
    {"section": [{"id": "a", "style": "hold", "start": 0.0},
                 {"id": "a", "style": "hold", "start": 2.0}]},                     # dup id
    {"section": [{"id": "a", "style": "hold", "start": 0.0},
                 {"id": "b", "style": "hold", "start": 0.004}]},                   # same frame
    {"section": [{"id": "a", "style": "hold", "start": 0.0, "colour": 1}]},        # typo'd key
])
def test_bad_songs_rejected(bad):
    with pytest.raises(ValueError):
        timeline.from_dict(song_dict(**bad))


# ---------------- seeding ----------------
def test_section_rng_is_stable_and_independent():
    a1 = section_rng("nothing", "verse1", 0).random(5)
    a2 = section_rng("nothing", "verse1", 0).random(5)
    assert (a1 == a2).all()
    assert not (a1 == section_rng("nothing", "verse2", 0).random(5)).any()
    assert not (a1 == section_rng("nothing", "verse1", 1).random(5)).any()
    assert not (a1 == section_rng("nothing", "verse1", 0, "blooms").random(5)).any()


def test_no_global_rng_in_nothing_code():
    """Only per-section Generators: global random/np.random would couple sections."""
    banned = re.compile(r"np\.random\.(seed|rand|randn|randint|random|choice|uniform|normal|shuffle)\b"
                        r"|^\s*import random\b(?!.*# ok)|random\.(random|randint|uniform|choice|seed)\(")
    offenders = []
    for p in (REPO / "songs").rglob("*.py"):
        for n, line in enumerate(p.read_text().splitlines(), 1):
            if banned.search(line) and "seeding.py" not in p.name:
                offenders.append(f"{p.relative_to(REPO)}:{n}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


# ---------------- state ----------------
def test_state_hash_is_canonical():
    a = State({"b": 1, "a": [0.1 + 0.2, {"y": 2, "x": 1}]})
    b = State({"a": [0.3, {"x": 1, "y": 2}], "b": 1})
    assert a.hash() == b.hash() and a == b
    assert a.with_(b=2).hash() != a.hash()
    assert State({"v": -0.0}) == State({"v": 0.0})
    with pytest.raises(TypeError):
        State({"x": object()})


# ---------------- manifest / cascade ----------------
def recorded_from(runs):
    return {r.section.id: {"parts": r.parts, "frames": [r.section.first, r.section.last]}
            for r in runs}


def stale_ids(song, recorded, tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir(exist_ok=True)
    for s in song.sections:
        for f in s.frames:
            (frames / f"frame_{f:05d}.png").touch()
    runs = manifest.walk(song, Lyrics([]))
    return {r.section.id: reasons for r, ok, reasons in manifest.status(runs, recorded, frames)
            if not ok}


def test_fresh_render_is_not_stale(tmp_path):
    song = timeline.from_dict(song_dict())
    rec = recorded_from(manifest.walk(song, Lyrics([])))
    assert stale_ids(song, rec, tmp_path) == {}


def test_edit_that_keeps_exit_state_does_not_cascade(tmp_path):
    song = timeline.from_dict(song_dict())
    rec = recorded_from(manifest.walk(song, Lyrics([])))
    d = song_dict()
    d["section"][0]["seed"] = 7                       # hold ignores randomness: same exit state
    assert stale_ids(timeline.from_dict(d), rec, tmp_path) == {"a": ["entry"]}


def test_edit_that_changes_exit_state_cascades_until_absorbed(tmp_path):
    song = timeline.from_dict(song_dict())
    rec = recorded_from(manifest.walk(song, Lyrics([])))
    d = song_dict()
    d["section"][0]["params"]["background"] = "#333333"
    stale = stale_ids(timeline.from_dict(d), rec, tmp_path)
    # b inherits a's background (cascade); c sets its own background, so it never reads the
    # inherited one — the change is absorbed and c stays valid.
    assert stale == {"a": ["entry", "plan"], "b": ["plan", "enter"]}


def test_missing_frames_make_section_stale(tmp_path):
    song = timeline.from_dict(song_dict())
    rec = recorded_from(manifest.walk(song, Lyrics([])))
    stale_ids(song, rec, tmp_path)                    # creates all frame files
    (tmp_path / "frames" / "frame_00300.png").unlink()
    runs = manifest.walk(song, Lyrics([]))
    st = {r.section.id: reasons for r, ok, reasons in
          manifest.status(runs, rec, tmp_path / "frames") if not ok}
    assert st == {"b": ["frames missing on disk"]}


def test_lyric_fix_only_invalidates_the_section_containing_it(tmp_path):
    song = timeline.from_dict(song_dict())
    words = [Word("one", 1.0, 1.5, 0), Word("two", 5.0, 5.5, 1)]
    rec = recorded_from(manifest.walk(song, Lyrics(words)))
    words[1] = Word("two", 5.1, 5.5, 1)
    runs = manifest.walk(song, Lyrics(words))
    frames = tmp_path / "frames"
    frames.mkdir()
    for f in range(1, song.total_frames + 1):
        (frames / f"frame_{f:05d}.png").touch()
    st = {r.section.id: reasons for r, ok, reasons in manifest.status(runs, rec, frames) if not ok}
    assert st == {"b": ["words"]}


def test_real_lyrics_load_and_slice():
    song = timeline.load()
    lyr = Lyrics.load(song.words)
    assert len(lyr.words) > 100
    assert [w.text for w in lyr.between(102.0, 104.6)][:2] == ["A", "knock"]


# ---------------- scenes ----------------
def scened(**over):
    d = song_dict(scene={"one": {"title": "One", "params": {"background": "#0000ff", "k": 1}},
                         "two": {"title": "Two"}})
    for s, sc in zip(d["section"], ["one", "one", "two"]):
        s["scene"] = sc
    d.update(over)
    return d


def test_scene_params_are_section_defaults():
    song = timeline.from_dict(scened())
    a, b, c = song.sections
    assert a.params == {"background": "#111111", "k": 1}     # section's own value wins
    assert b.params == {"background": "#0000ff", "k": 1}     # inherited from the scene
    assert c.params == {"background": "#222222"}
    assert song.scenes == (("one", "One"), ("two", "Two"))


def test_scene_param_edit_invalidates_only_that_scene(tmp_path):
    song = timeline.from_dict(scened())
    rec = recorded_from(manifest.walk(song, Lyrics([])))
    d = scened()
    d["scene"]["one"]["params"]["k"] = 2
    assert set(stale_ids(timeline.from_dict(d), rec, tmp_path)) == {"a", "b"}


@pytest.mark.parametrize("mutate", [
    lambda d: d["section"][1].update(scene="nope"),                       # unknown scene
    lambda d: d["section"][1].update(scene="two") or d["section"][2].update(scene="one"),  # split
    lambda d: d["scene"]["one"].update(colour=1),                         # typo'd key
])
def test_bad_scenes_rejected(mutate):
    d = scened()
    mutate(d)
    with pytest.raises(ValueError):
        timeline.from_dict(d)


def test_code_fingerprint_ignores_docstrings_and_comments(tmp_path):
    a, b, c = tmp_path / "a.py", tmp_path / "b.py", tmp_path / "c.py"
    a.write_text('"""One."""\ndef f(x):\n    """Doc."""\n    return x + 1  # note\n')
    b.write_text('"""Two, longer."""\ndef f(x):\n    """Other doc."""\n    return x + 1\n')
    c.write_text('"""One."""\ndef f(x):\n    return x + 2\n')
    assert manifest.code_hash(a) == manifest.code_hash(b)
    assert manifest.code_hash(a) != manifest.code_hash(c)

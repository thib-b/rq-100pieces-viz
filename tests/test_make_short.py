"""Unit tests for make_short.py — the existing time/warp (uniform speed-up) utility.

make_short.py is bpy-free, so this runs under the plain venv interpreter with no Blender.
It locks the frame-selection math (`pick_even`) and the numeric frame ordering
(`find_frames`) that a refactor's warp/time-scale feature must reproduce.
"""
from pathlib import Path

from helpers import ANIM, load_module_from

ms = load_module_from(ANIM / "make_short.py", "make_short")


def test_pick_even_target_ge_n_returns_all():
    assert ms.pick_even(5, 10) == [0, 1, 2, 3, 4]
    assert ms.pick_even(5, 5) == [0, 1, 2, 3, 4]


def test_pick_even_single_target():
    assert ms.pick_even(100, 1) == [0]


def test_pick_even_endpoints_count_and_monotonic():
    picks = ms.pick_even(11580, 1800)
    assert len(picks) == 1800
    assert picks[0] == 0
    assert picks[-1] == 11579          # both ends inclusive
    assert picks == sorted(picks)      # non-decreasing


def test_pick_even_known_values():
    # round(i * (n-1) / (target-1)) with n=10, target=5 -> 0, 2.25, 4.5, 6.75, 9
    # (Python's round-half-to-even makes 4.5 -> 4)
    assert ms.pick_even(10, 5) == [0, 2, 4, 7, 9]


def test_find_frames_sorts_numerically_not_lexically(tmp_path):
    for i in (1, 2, 10, 100):
        (tmp_path / f"frame_{i:05d}.png").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("ignore me")   # non-matching file skipped
    got = [Path(p).name for p in ms.find_frames(str(tmp_path))]
    assert got == ["frame_00001.png", "frame_00002.png",
                   "frame_00010.png", "frame_00100.png"]

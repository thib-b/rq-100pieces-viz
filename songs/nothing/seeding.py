"""Per-section random streams. Pure (no bpy).

Every random draw in a section comes from `section_rng(song, section)`, which depends only on
the song name, the section id and its seed — never on other sections or on draw order elsewhere.
Global `random` / `np.random` must not be used anywhere in songs/nothing (a test enforces it).
"""
from __future__ import annotations

import hashlib
import random

import numpy as np


def _seed_int(*parts):
    h = hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:16], "big")


def section_rng(song_name, section_id, seed=0, *labels):
    """A fresh, independent numpy Generator for one section. Extra `labels` give independent
    named sub-streams, so adding draws to one part of a style (e.g. filaments) doesn't shift
    another part (e.g. bloom placement)."""
    return np.random.Generator(np.random.PCG64(_seed_int(song_name, section_id, seed, *labels)))


def py_random(rng):
    """A `random.Random` derived from a Generator — for engine.plate helpers that want one
    (e.g. simulate_stamp). Consumes one draw from `rng`, so it stays deterministic."""
    return random.Random(int(rng.integers(0, 2 ** 63)))


"""Musical cue grid for Nothing (pure). Loaded from cues.toml; styles call these helpers.

Units: seconds. The felt beat is a quarter note at 77 bpm (two grid 8ths); a bar is 4 beats.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

try:
    import tomllib as _toml
except ModuleNotFoundError:
    import tomli as _toml

CUES_TOML = Path(__file__).resolve().parent / "cues.toml"


@lru_cache(maxsize=None)
def _load(path=CUES_TOML):
    with open(path, "rb") as f:
        return _toml.load(f)


def raw():
    return _load()


def eighth():
    return raw()["grid"]["eighth"]


def beat():
    return 2 * eighth()


def sixteenth():
    return eighth() / 2


def bar():
    return 4 * beat()


def at_eighth(n):
    """Time of grid 8th-note index n."""
    g = raw()["grid"]
    return g["eighth0"] + n * g["eighth"]


def downbeat(k):
    """Time of the k-th bar downbeat counted from the 8th index `downbeat_mod` (k may be < 0)."""
    return at_eighth(raw()["grid"]["downbeat_mod"] + 8 * k)


def is_kick_beat(t, tol=0.02):
    """True if t is on beat 1 or 3 of a bar (the kick)."""
    g = raw()["grid"]
    n = (t - g["eighth0"]) / g["eighth"]
    r = round(n)
    return abs(n - r) * g["eighth"] <= tol and (r - g["downbeat_mod"]) % 4 == 0


def scene1():
    return raw()["scene1"]


def ratchet_landings():
    """Every ratchet landing time (beats 1 and 3), first to last inclusive."""
    s = scene1()
    out, t, step = [], s["ratchet_first_land"], 2 * beat()
    while t <= s["ratchet_last_land"] + 1e-6:
        out.append(t)
        t += step
    return out


def nothing_typed():
    s = scene1()
    return at_eighth(s["nothing_typed_eighth"]) - s["nothing_vocal_lead"]


def nothing_flips():
    s = scene1()
    return [at_eighth(n) - s["nothing_vocal_lead"] for n in s["nothing_flip_eighths"]]


def clap_flips():
    """The clap flip times: one per measured hand clap (cues.toml clap_hits)."""
    return list(scene1()["clap_hits"])

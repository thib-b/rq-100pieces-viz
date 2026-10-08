"""The State handed from one section to the next. Pure (no bpy).

A State describes what the frame looks like at a section boundary — whatever the next section
needs to continue seamlessly (background, what is on screen and where, colours, camera …).
It is plain JSON-able data with a canonical serialisation, so its hash tells us whether a
section's edit changed what the following section inherits.
"""
from __future__ import annotations

import hashlib
import json

FLOAT_DIGITS = 6        # floats are rounded before hashing so 1e-12 noise can't cascade


def _canon(v):
    if isinstance(v, float):
        r = round(v, FLOAT_DIGITS)
        return 0.0 if r == 0 else r
    if isinstance(v, dict):
        return {str(k): _canon(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    if hasattr(v, "tolist"):                  # numpy scalars / arrays
        return _canon(v.tolist())
    if v is None or isinstance(v, (bool, int, str)):
        return v
    raise TypeError(f"State values must be JSON-able, got {type(v).__name__}")


def canonical_json(obj):
    return json.dumps(_canon(obj), sort_keys=True, separators=(",", ":"))


def digest(obj):
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


class State:
    """Immutable mapping of boundary facts. Use `with_(...)` to derive the next one."""

    __slots__ = ("_data",)

    def __init__(self, data=None):
        object.__setattr__(self, "_data", json.loads(canonical_json(data or {})))

    def __getitem__(self, k):
        return self._data[k]

    def get(self, k, default=None):
        return self._data.get(k, default)

    def with_(self, **changes):
        return State({**self._data, **changes})

    def to_dict(self):
        return json.loads(json.dumps(self._data))

    def hash(self):
        return digest(self._data)

    def __eq__(self, other):
        return isinstance(other, State) and self.hash() == other.hash()

    def __repr__(self):
        return f"State({canonical_json(self._data)[:120]})"


class TrackedState(State):
    """A State that remembers which keys were read (get/[]). Passing values through with
    `with_` is not a read. manifest.walk() hands one to each section so its fingerprint covers
    only the inherited facts it actually depends on — an upstream edit to something a section
    overrides or ignores then doesn't force a re-render."""

    __slots__ = ("reads",)

    def __init__(self, data=None):
        super().__init__(data)
        object.__setattr__(self, "reads", set())

    def __getitem__(self, k):
        self.reads.add(k)
        return super().__getitem__(k)

    def get(self, k, default=None):
        self.reads.add(k)
        return super().get(k, default)

    def read_hash(self):
        return digest({k: self._data.get(k) for k in sorted(self.reads)})

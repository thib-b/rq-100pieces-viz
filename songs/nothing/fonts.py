"""Pick one face out of a TrueType collection (.ttc), for Blender — which only ever loads a
collection's first face. Pure stdlib (runs under Blender's Python too).

The face is written to the gitignored render cache, never committed: the system fonts are
Apple's to distribute, not ours.
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

from songs.nothing.timeline import REPO

HELVETICA_NEUE = "/System/Library/Fonts/HelveticaNeue.ttc"
MEDIUM = 10            # the face the verse-1 lyric masks are drawn in (tools/make_lyrics_masks.py)
CACHE = REPO / "renders" / "nothing" / "cache"


def extract_face(ttc_bytes, index):
    """The bytes of a standalone font file holding face `index` of a TTC."""
    if ttc_bytes[:4] != b"ttcf":
        raise ValueError("not a TrueType collection")
    n_fonts = struct.unpack(">I", ttc_bytes[8:12])[0]
    if not 0 <= index < n_fonts:
        raise IndexError(f"face {index} of {n_fonts}")
    off = struct.unpack(">I", ttc_bytes[12 + 4 * index:16 + 4 * index])[0]
    head = ttc_bytes[off:off + 12]
    n_tables = struct.unpack(">H", head[4:6])[0]
    records = [struct.unpack(">4sIII", ttc_bytes[off + 12 + 16 * i:off + 28 + 16 * i])
               for i in range(n_tables)]
    out_dir, body = [], b""
    pos = 12 + 16 * n_tables
    for tag, checksum, t_off, length in records:
        data = ttc_bytes[t_off:t_off + length]
        out_dir.append(struct.pack(">4sIII", tag, checksum, pos + len(body), length))
        body += data + b"\0" * (-len(data) % 4)
    return head + b"".join(out_dir) + body


def face_path(ttc=HELVETICA_NEUE, index=MEDIUM):
    """Path to the cached single-face font file (written on first use)."""
    src = Path(ttc)
    out = CACHE / f"{src.stem}-{index}.ttf"
    if not out.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_bytes(extract_face(src.read_bytes(), index))
        tmp.replace(out)                            # atomic: parallel workers may race here
    return out

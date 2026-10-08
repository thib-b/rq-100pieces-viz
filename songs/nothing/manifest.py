"""Walk the song, fingerprint each section, and track which rendered sections are stale. Pure.

A section's fingerprint covers everything that can change its pixels:
  entry   its own song.toml entry (style, params, seed, frame range)
  code    its style module + the shared modules, as syntax trees (docstrings/comments ignored)
  plan    the plan itself — the exact data its frames are built from
  enter   the inherited State values it actually reads (an upstream edit only cascades into a
          section if it changes something that section looks at)
  words   the lyric timings that fall inside it
  assets  contents of the files it reads
renders/nothing/manifest.json records the fingerprint parts of each section's last complete
full-resolution render; a section is stale when any part differs.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from songs.nothing import styles
from songs.nothing.lyrics import Lyrics
from songs.nothing.state import State, TrackedState, digest
from songs.nothing.timeline import REPO, asset



def out_dir(song):
    """renders/<song name>/ — frames/, manifest.json, preview/, inprogress/ live here."""
    return REPO / "renders" / song.name


def frames_dir(song):
    return out_dir(song) / "frames"


def manifest_path(song):
    return out_dir(song) / "manifest.json"

# Code every section's pixels depend on, besides its own style module.
SHARED_CODE = [
    "songs/nothing/build.py", "songs/nothing/seeding.py", "songs/nothing/styles/__init__.py",
    "engine/core.py", "engine/plate.py", "engine/render.py",
]

_file_hash_cache = {}


def file_hash(path):
    p = Path(path)
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    if key not in _file_hash_cache:
        _file_hash_cache[key] = hashlib.sha256(p.read_bytes()).hexdigest()
    return _file_hash_cache[key]


def code_hash(path):
    """Hash of what code DOES, identical under any Python version (Blender's and the venv's):
    the token stream with comments, blank lines and docstrings (statements that are only a
    string) removed — editing descriptions never forces a re-render."""
    p = Path(path)
    if p.suffix != ".py":
        return file_hash(p)
    st = p.stat()
    key = ("tok", str(p), st.st_mtime_ns, st.st_size)
    if key not in _file_hash_cache:
        import io
        import tokenize
        src = p.read_text()
        lines = src.splitlines(keepends=True)
        skip = {tokenize.COMMENT, tokenize.NL, tokenize.ENCODING}
        raw = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
               if t.type not in skip]
        # Python ≥ 3.12 splits f-strings into FSTRING_START … FSTRING_END; fold each back into
        # one STRING token (its exact source text), as older Pythons tokenize it
        fs_start = getattr(tokenize, "FSTRING_START", None)
        fs_end = getattr(tokenize, "FSTRING_END", None)
        toks, depth, start = [], 0, None
        for t in raw:
            if fs_start is not None and t.type == fs_start:
                depth += 1
                start = start or t
                continue
            if depth:
                if t.type == fs_end:
                    depth -= 1
                    if depth == 0:
                        (r0, c0), (r1, c1) = start.start, t.end
                        text = ("".join(lines[r0 - 1:r1])[c0:]
                                [:len("".join(lines[r0 - 1:r1 - 1])) - c0 + c1])
                        toks.append(tokenize.TokenInfo(tokenize.STRING, text, start.start,
                                                       t.end, t.line))
                        start = None
                continue
            toks.append(t)
        keep, prev = [], tokenize.NEWLINE
        for i, t in enumerate(toks):
            nxt = toks[i + 1].type if i + 1 < len(toks) else tokenize.ENDMARKER
            if (t.type == tokenize.STRING and nxt == tokenize.NEWLINE
                    and prev in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)):
                prev = tokenize.NEWLINE
                continue                                    # a docstring: drop it …
            if t.type == tokenize.NEWLINE and prev == tokenize.NEWLINE:
                continue                                    # … and its line
            keep.append(f"{tokenize.tok_name[t.type]}:{t.string}")
            prev = t.type
        _file_hash_cache[key] = hashlib.sha256("\n".join(keep).encode()).hexdigest()
    return _file_hash_cache[key]


@dataclass
class Run:
    """One section, resolved: its context, plan, exit state and fingerprint parts."""
    section: object
    ctx: object
    plan: object
    exit: State
    parts: dict
    layer_plans: tuple = ()      # ((style name, plan), ...) drawn over the base, in order

    @property
    def fingerprint(self):
        return digest(self.parts)


def walk(song, lyrics=None):
    """Plan every section in order, threading State through. Pure and fast (no rendering)."""
    lyrics = lyrics if lyrics is not None else Lyrics.load(song.words)
    state = State(song.initial)
    runs = []
    for sec in song.sections:
        style = styles.get(sec.style)
        enter = TrackedState(state.to_dict())
        ctx = styles.Context(song=song, section=sec, enter=enter, lyrics=lyrics)
        plan = style.plan(ctx)
        exit_ = style.exit_state(ctx, plan)
        mods = [(sec.style, style)] + [(n, styles.get(n)) for n in sec.layers]
        layer_plans = tuple((n, m.plan(ctx)) for n, m in mods[1:])
        code = [styles.source_path(n) for n, _ in mods] + [REPO / f for f in SHARED_CODE]
        assets = []
        for _, m in mods:
            code += [asset(f) for f in getattr(m, "DEPENDS", [])]
            assets += getattr(m, "assets", lambda c: [])(ctx)
        parts = {
            "entry": digest(sec.entry()),
            "code": digest({str(Path(p).relative_to(REPO)): code_hash(p) for p in code}),
            # the exact data the frames are drawn from: catches a data change made anywhere
            # (cue times, shared modules) without re-rendering on cosmetic code edits
            "plan": digest([plan] + [lp for _, lp in layer_plans]),
            "enter": enter.read_hash(),
            "words": lyrics.slice_hash(ctx.time(sec.first), ctx.time(sec.last + 1)),
            "assets": digest({str(p): file_hash(p) for p in assets}),
            "format": digest({"fps": song.fps, "aspect": song.aspect,
                              "ortho": song.ortho_scale}),
        }
        runs.append(Run(sec, ctx, plan, exit_, parts, layer_plans))
        state = exit_
    return runs


def read(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


@contextlib.contextmanager
def _locked(path):
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)          # parallel section renders share the manifest
        yield


def record(run, path):
    """Mark a section as rendered with its current fingerprint (call only once all its
    frames are written)."""
    path = Path(path)
    with _locked(path):
        data = read(path)
        data[run.section.id] = {"fingerprint": run.fingerprint, "parts": run.parts,
                                "frames": [run.section.first, run.section.last],
                                "rendered_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
        tmp.replace(path)


def missing_frames(section, frames):
    return [f for f in section.frames if not (Path(frames) / f"frame_{f:05d}.png").exists()]


def status(runs, recorded, frames):
    """[(run, ok: bool, reasons: [str])] — why each section needs (re)rendering, if it does."""
    out = []
    for r in runs:
        rec = recorded.get(r.section.id)
        if rec is None:
            reasons = ["never rendered"]
        else:
            reasons = [k for k in r.parts if rec["parts"].get(k) != r.parts[k]]
            if rec.get("frames") != [r.section.first, r.section.last]:
                reasons.append("frame range")
            if not reasons and missing_frames(r.section, frames):
                reasons.append("frames missing on disk")
        out.append((r, not reasons, reasons))
    return out

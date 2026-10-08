"""Nothing render CLI.

    .venv/bin/python -m songs.nothing.cli status                     # no Blender needed
    blender -b --python nothing.py -- render --section intro [--resume]
    blender -b --python nothing.py -- render --stale                 # every stale section, in order
    blender -b --python nothing.py -- render --section intro --respct 40 --step 10   # preview
    blender -b --python nothing.py -- frame 5790 [--respct 40] [--output out/spot]
    blender -b --python nothing.py -- range 93 99.5 --seconds [--respct 40] [--step 2]   # preview clip
    blender -b --python nothing.py -- edges --section intro [--respct 40]   # seam check

Full-resolution section renders write global frames into renders/<song>/frames/ and are
recorded in renders/<song>/manifest.json once complete. Anything with --respct < 100 or
--step > 1 is a preview: it goes to renders/<song>/preview/ and never touches the manifest.
Run different sections in parallel Blender processes to use more cores.
"""
from __future__ import annotations

import argparse
import json
import sys

from songs.nothing import manifest, timeline


def _fmt_t(sec):
    return f"{int(sec // 60)}:{sec % 60:05.2f}"


def _status(song, runs):
    return manifest.status(runs, manifest.read(manifest.manifest_path(song)),
                           manifest.frames_dir(song))


def cmd_status(song, runs):
    rows = _status(song, runs)
    print(f"{song.name}: {song.total_frames} frames @ {song.fps}fps, {len(runs)} sections")
    titles = dict(song.scenes)
    for r, ok, reasons in rows:
        s = r.section
        if s.scene and (s.index == 0 or song.sections[s.index - 1].scene != s.scene):
            print(f"  -- {titles[s.scene]} --")
        print(f"  {'ok   ' if ok else 'STALE'} {s.index:2d} {s.id:<18} {s.style:<12} "
              f"{_fmt_t(s.start_sec):>8}  frames {s.first:>5}-{s.last:<5} ({len(s.frames):>5})"
              f"{'' if ok else '  <- ' + ', '.join(reasons)}")
    stale = [r.section.id for r, ok, _ in rows if not ok]
    print(f"{len(stale)} stale" + (f": {' '.join(stale)}" if stale else ""))
    return stale


def _render_full(run, resume):
    """Render a section's frames at full res into the shared frames dir, then record it."""
    import bpy
    from songs.nothing import build
    sec, song = run.section, run.ctx.song
    frames = manifest.frames_dir(song)
    INPROGRESS_DIR = manifest.out_dir(song) / "inprogress"
    INPROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    marker = INPROGRESS_DIR / f"{sec.id}.json"
    if resume:
        prev = json.loads(marker.read_text()) if marker.exists() else {}
        if prev.get("fingerprint") != run.fingerprint:
            raise SystemExit(f"--resume refused for {sec.id}: no interrupted render with the "
                             f"current fingerprint (frames on disk may be from an older version)")
    marker.write_text(json.dumps({"fingerprint": run.fingerprint}))
    frames.mkdir(parents=True, exist_ok=True)
    build.build_section(run, frames / "frame_#####", 100)
    bpy.context.scene.render.use_overwrite = not resume
    print(f"render {sec.id}: frames {sec.first}-{sec.last}")
    bpy.ops.render.render(animation=True)
    missing = manifest.missing_frames(sec, frames)
    if missing:
        raise SystemExit(f"{sec.id}: {len(missing)} frames missing after render, e.g. {missing[:5]}")
    manifest.record(run, manifest.manifest_path(song))
    marker.unlink(missing_ok=True)
    print(f"recorded {sec.id} ({run.fingerprint[:12]})")


def _render_frames(run, frames, out_dir, respct):
    import bpy
    from songs.nothing import build
    out_dir.mkdir(parents=True, exist_ok=True)
    build.build_section(run, out_dir / "frame_#####", respct)
    scene = bpy.context.scene
    for f in frames:
        scene.frame_set(f)
        scene.render.filepath = str(out_dir / f"frame_{f:05d}")
        bpy.ops.render.render(write_still=True)
    print(f"wrote {len(frames)} frame(s) of {run.section.id} -> {out_dir}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nothing")
    ap.add_argument("--song", default=str(timeline.SONG_TOML),
                    help="song file (default songs/nothing/song.toml); outputs go to renders/<name>/")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    r = sub.add_parser("render")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--section", action="append", help="section id (repeatable)")
    g.add_argument("--stale", action="store_true")
    r.add_argument("--respct", type=int, default=100)
    r.add_argument("--step", type=int, default=1)
    r.add_argument("--resume", action="store_true",
                   help="continue an interrupted full render, keeping frames already written")
    fr = sub.add_parser("frame")
    fr.add_argument("frame", type=int)
    fr.add_argument("--respct", type=int, default=100)
    fr.add_argument("--output", default=None)
    rg = sub.add_parser("range", help="preview frames A..B (any sections) to a folder")
    rg.add_argument("a", type=float)
    rg.add_argument("b", type=float)
    rg.add_argument("--seconds", action="store_true", help="A and B are times, not frames")
    rg.add_argument("--respct", type=int, default=40)
    rg.add_argument("--step", type=int, default=1)
    rg.add_argument("--output", default=None)
    e = sub.add_parser("edges")
    e.add_argument("--section", required=True)
    e.add_argument("--respct", type=int, default=40)
    args = ap.parse_args(argv)

    song = timeline.load(timeline.asset(args.song))
    runs = manifest.walk(song)
    PREVIEW_DIR = manifest.out_dir(song) / "preview"
    by_id = {r.section.id: r for r in runs}

    if args.cmd == "status":
        cmd_status(song, runs)
        return

    if args.cmd == "render":
        if args.stale:
            ids = [r.section.id for r, ok, _ in _status(song, runs) if not ok]
        else:
            ids = args.section
            for sid in ids:
                song.section(sid)                   # validates the id
        preview = args.respct < 100 or args.step > 1
        for sid in ids:
            run = by_id[sid]
            if preview:
                frames = list(run.section.frames)[::args.step]
                if frames[-1] != run.section.last:
                    frames.append(run.section.last)
                _render_frames(run, frames, PREVIEW_DIR / sid, args.respct)
            else:
                _render_full(run, args.resume)
        return

    if args.cmd == "frame":
        run = by_id[song.section_at_frame(args.frame).id]
        out = PREVIEW_DIR / "spot" if args.output is None else timeline.asset(args.output)
        _render_frames(run, [args.frame], out, args.respct)
        return

    if args.cmd == "range":
        a, b = ((song.frame_of(args.a), song.frame_of(args.b)) if args.seconds
                else (int(args.a), int(args.b)))
        out = PREVIEW_DIR / f"range_{a}_{b}" if args.output is None else timeline.asset(args.output)
        frames = list(range(max(1, a), min(b, song.total_frames) + 1, args.step))
        for sec in song.sections:                  # one scene build per section touched
            fs = [f for f in frames if sec.first <= f <= sec.last]
            if fs:
                _render_frames(by_id[sec.id], fs, out, args.respct)
        print(out)
        return

    if args.cmd == "edges":
        sec = song.section(args.section)
        out = PREVIEW_DIR / "edges" / sec.id
        if sec.index > 0:                        # the seam coming in
            prev = song.sections[sec.index - 1]
            _render_frames(by_id[prev.id], [prev.last], out, args.respct)
        _render_frames(by_id[sec.id], [sec.first, sec.last], out, args.respct)
        if sec.index + 1 < len(song.sections):  # the seam going out
            nxt = song.sections[sec.index + 1]
            _render_frames(by_id[nxt.id], [nxt.first], out, args.respct)
        return


if __name__ == "__main__":
    main(sys.argv[1:])

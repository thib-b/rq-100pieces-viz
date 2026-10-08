#!/usr/bin/env python3
"""Assemble a section-rendered song: all global frames + the master audio → one .mov.

Refuses while any section is stale or frames are missing (use --force to encode anyway, e.g.
for a rough cut). The master audio is stream-copied (bit-exact) and verified by checksum.

    .venv/bin/python tools/nothing_assemble.py [--song songs/nothing/song.toml] [--force]
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from songs.nothing import manifest, timeline  # noqa: E402


def audio_md5(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a", "-f", "md5", "-"],
                         capture_output=True, text=True, check=True).stdout
    return out.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--song", default=str(timeline.SONG_TOML))
    ap.add_argument("--out", default=None)
    ap.add_argument("--force", action="store_true", help="encode even if sections are stale")
    args = ap.parse_args()

    song = timeline.load(timeline.asset(args.song))
    frames = manifest.frames_dir(song)
    rows = manifest.status(manifest.walk(song), manifest.read(manifest.manifest_path(song)), frames)
    stale = [(r.section.id, reasons) for r, ok, reasons in rows if not ok]
    if stale:
        print("stale sections:", *(f"  {sid}: {', '.join(why)}" for sid, why in stale), sep="\n")
        if not args.force:
            raise SystemExit("refusing to assemble (re-render them, or pass --force)")
    missing = [f for f in range(1, song.total_frames + 1)
               if not (frames / f"frame_{f:05d}.png").exists()]
    if missing:
        raise SystemExit(f"{len(missing)} frames missing, e.g. {missing[:5]}")

    audio = timeline.asset(song.audio)
    out = Path(args.out) if args.out else manifest.out_dir(song) / f"{song.name}.mov"
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats",
           "-framerate", str(song.fps), "-start_number", "1", "-i", str(frames / "frame_%05d.png"),
           "-i", str(audio), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-crf", "10", "-preset", "slow", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-dn", "-map_chapters", "-1", "-write_tmcd", "0",
           "-movflags", "+faststart", str(out)]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    if audio_md5(out) != audio_md5(audio):
        raise SystemExit(f"audio in {out} does not match the master bit-for-bit!")
    print(f"wrote {out} ({song.total_frames} frames, audio bit-exact)")


if __name__ == "__main__":
    main()

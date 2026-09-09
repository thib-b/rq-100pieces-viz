#!/usr/bin/env python3
"""
make_short.py — build an accelerated short clip from an already-rendered PNG frame sequence.

No Blender, no re-render: it evenly samples frames from a full-length `frame_XXXXX.png` sequence
and re-encodes them at the target fps, giving a uniform time-lapse (whole timeline sped up equally).
Encode settings match haha_reveal*.py's encode_mp4() — near-lossless (libx264 crf 12, veryslow,
yuv420p, silent) so the held photo frame stays crisp; down-compress yourself afterward.

  python3 animations/make_short.py --frames renders/haha_vertical_full \
      --duration 30 --fps 60 --out renders/haha_vertical_30s/haha_reveal_vertical_30s.mp4

Example: a 11580-frame source, --duration 30 --fps 60 -> 1800 frames picked evenly (~6.4x speed-up).
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import tempfile


def find_frames(frames_dir):
    """Return the sorted list of frame_XXXXX.png paths in frames_dir."""
    files = glob.glob(os.path.join(frames_dir, "frame_*.png"))
    # sort by the numeric index embedded in the filename, not lexically
    def idx(p):
        m = re.search(r"frame_(\d+)\.png$", os.path.basename(p))
        return int(m.group(1)) if m else -1
    files = [p for p in files if idx(p) >= 0]
    files.sort(key=idx)
    return files


def pick_even(n, target):
    """Indices [0..n-1] of `target` evenly spaced frames, inclusive of both ends."""
    if target >= n:
        return list(range(n))
    if target == 1:
        return [0]
    return [round(i * (n - 1) / (target - 1)) for i in range(target)]


def main():
    ap = argparse.ArgumentParser(description="Build an accelerated short clip from a PNG frame sequence.")
    ap.add_argument("--frames", required=True, help="dir containing frame_XXXXX.png")
    ap.add_argument("--duration", type=float, default=30.0, help="target clip length in seconds (default 30)")
    ap.add_argument("--fps", type=int, default=60, help="output fps (default 60)")
    ap.add_argument("--out", required=True, help="output mp4 path")
    args = ap.parse_args()

    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not (shutil.which("ffmpeg") or os.path.exists(ffmpeg)):
        raise SystemExit("ffmpeg not found on PATH or at /opt/homebrew/bin/ffmpeg")

    src = find_frames(args.frames)
    if not src:
        raise SystemExit(f"no frame_XXXXX.png found in {args.frames}")

    target = round(args.duration * args.fps)
    picks = pick_even(len(src), target)
    print(f"source frames: {len(src)}  ->  selecting {len(picks)} "
          f"({args.duration}s @ {args.fps}fps, ~{len(src)/max(len(picks),1):.2f}x speed-up)")

    tmp = tempfile.mkdtemp(prefix="make_short_")
    try:
        for i, p in enumerate(picks, start=1):
            os.symlink(os.path.abspath(src[p]), os.path.join(tmp, f"frame_{i:05d}.png"))

        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        cmd = [ffmpeg, "-y", "-framerate", str(args.fps), "-start_number", "1",
               "-i", os.path.join(tmp, "frame_%05d.png"),
               "-c:v", "libx264", "-crf", "12", "-preset", "veryslow",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
        print("encoding:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        print("wrote", args.out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

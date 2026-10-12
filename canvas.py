#!/usr/bin/env python3
"""Spotify Canvas loops for Nothing (run under Blender; loop name after `--`).

    blender -b --python canvas.py -- fractal_loop
"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

name = sys.argv[sys.argv.index("--") + 1]
mod = importlib.import_module(f"songs.nothing.canvas.{name}")
if not mod.check():
    raise SystemExit(f"{name}: checks failed")
mod.render()

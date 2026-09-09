#!/usr/bin/env python3
"""100 Pieces — recipe-driven headless-Blender render entry point.

Run under Blender (args after `--`):

    blender --background --python 100pieces.py -- --recipe recipes/haha_landscape.toml
    blender --background --python 100pieces.py -- --recipe recipes/haha_vertical.toml --last
    blender --background --python 100pieces.py -- --recipe recipes/stamp.toml --preview --fullres --output DIR

This thin shim puts the repo on sys.path and hands off to engine.render.main().
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import render

render.main()

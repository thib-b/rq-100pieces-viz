#!/usr/bin/env python3
"""Nothing — section-based render entry point (run under Blender; args after `--`).

    blender --background --python nothing.py -- render --section intro
    blender --background --python nothing.py -- render --stale
    blender --background --python nothing.py -- frame 5790 --respct 40

`status` doesn't need Blender: .venv/bin/python -m songs.nothing.cli status
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from songs.nothing import cli

cli.main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

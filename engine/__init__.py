"""100 Pieces — recipe-driven headless-Blender render engine.

Pure (bpy-free) logic lives in `core` and `plate` so it can be unit-tested under a plain
Python interpreter; `recipe` defines the per-song config; `render` is the Blender entry
point (imports bpy) that consumes a recipe and produces frames + an encoded master.
"""

#!/usr/bin/env python3
"""
Main rendering script for Blender headless visualization pipeline.

This script provides a flexible interface for generating and rendering
scenes using Blender's Python API (bpy).

Usage:
    blender --background --python render.py -- <scene_file> [output_path]
    
Examples:
    blender --background --python render.py -- scenes/basic.py /tmp/basic.png
    blender --background --python render.py -- scenes/parametric.py /tmp/parametric.png --arg1 value1 --arg2 value2
"""
import bpy
import sys
import os
import importlib.util
import time


def parse_arguments():
    """Parse command line arguments."""
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return args


def clear_scene():
    """Clear all objects from the current scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def setup_default_render_settings(output_path, width=1920, height=1080, samples=32):
    """Setup default render settings."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.cycles.samples = samples
    scene.cycles.device = 'GPU' if 'GPU' in bpy.context.preferences.addons['cycles'].preferences.devices else 'CPU'
    
    # Enable GPU if available
    try:
        bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'
        bpy.context.scene.cycles.device = 'GPU'
    except:
        pass


def render_frame(output_path):
    """Render a single frame."""
    start_time = time.time()
    bpy.ops.render.render(write_still=True)
    end_time = time.time()
    print(f"Rendered to: {output_path} in {end_time - start_time:.2f} seconds")
    return end_time - start_time


def load_scene_module(module_path):
    """Load a scene definition module dynamically."""
    spec = importlib.util.spec_from_file_location("scene_module", module_path)
    if spec is None:
        raise ImportError(f"Could not load module: {module_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["scene_module"] = module
    spec.loader.exec_module(module)
    return module


def extract_scene_args(args):
    """Extract scene file and output path from arguments."""
    if len(args) < 1:
        print("Usage: blender --background --python render.py -- <scene_file> [output_path] [scene_args...]")
        sys.exit(1)
    
    scene_file = args[0]
    output_path = args[1] if len(args) > 1 else f"/tmp/{os.path.basename(scene_file).replace('.py', '')}.png"
    scene_args = args[2:] if len(args) > 2 else []
    
    return scene_file, output_path, scene_args


def main():
    """Main rendering entry point."""
    args = parse_arguments()
    scene_file, output_path, scene_args = extract_scene_args(args)
    
    # Validate scene file
    if not os.path.exists(scene_file):
        print(f"Error: Scene file not found: {scene_file}")
        sys.exit(1)
    
    # Clear existing scene
    clear_scene()
    
    # Load and execute scene definition
    print(f"Loading scene: {scene_file}")
    scene_module = load_scene_module(scene_file)
    
    # Call create_scene function if it exists
    if hasattr(scene_module, 'create_scene'):
        scene_module.create_scene(scene_args)
    else:
        print("Warning: No create_scene function found in module")
    
    # Setup render settings
    setup_default_render_settings(output_path)
    
    # Render
    render_frame(output_path)


if __name__ == "__main__":
    main()

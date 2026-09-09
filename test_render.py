#!/usr/bin/env python3
"""
Minimal working example for Blender headless rendering.

Usage:
    blender --background --python test_render.py -- /tmp/my_render.png
    
    or use default output:
    blender --background --python test_render.py
"""
import bpy
import sys
import os


def parse_arguments():
    """Parse command line arguments passed after -- separator."""
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return args


def main():
    """Main rendering function."""
    args = parse_arguments()
    output_path = args[0] if args else "/tmp/test_render.png"
    
    # Clear existing objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # Create a red cube
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    
    # Add material
    mat = bpy.data.materials.new(name="RedMaterial")
    mat.diffuse_color = (1, 0, 0, 1)  # Red
    cube.data.materials.append(mat)
    
    # Setup camera
    bpy.ops.object.camera_add(location=(5, 5, 5), rotation=(1, 0, 0))
    camera = bpy.context.active_object
    bpy.context.scene.camera = camera
    
    # Add light
    bpy.ops.object.light_add(type='POINT', location=(3, 3, 3))
    
    # Configure render
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.cycles.samples = 32
    
    # Render
    bpy.ops.render.render(write_still=True)
    
    print(f"Rendered to: {output_path}")


if __name__ == "__main__":
    main()

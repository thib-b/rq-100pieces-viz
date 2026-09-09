#!/usr/bin/env python3
"""
Basic test scene - a red cube with simple lighting.

This is the simplest possible scene to verify the pipeline works.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.geometry import create_cube, clear_scene
from scripts.materials import create_red_material, assign_material
from scripts.lighting import setup_basic_lighting
from scripts.camera import setup_perspective_camera, set_active_camera


def create_scene(args=None):
    """Create a basic test scene."""
    # Clear existing objects
    clear_scene()
    
    # Create a red cube
    cube = create_cube(size=2, location=(0, 0, 0), name="RedCube")
    red_mat = create_red_material()
    assign_material(cube, red_mat)
    
    # Setup camera
    camera = setup_perspective_camera(
        location=(5, -5, 5),
        target=(0, 0, 0),
        name="MainCamera"
    )
    set_active_camera(camera)
    
    # Setup lighting
    setup_basic_lighting(energy=100)
    
    print("Created basic scene with red cube")


if __name__ == "__main__":
    create_scene()

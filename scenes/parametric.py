#!/usr/bin/env python3
"""
Parametric scene - demonstrates dynamic scene generation based on arguments.

This scene creates multiple objects based on command-line parameters.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.geometry import create_cube, create_sphere, clear_scene
from scripts.materials import (
    create_red_material, create_green_material, create_blue_material,
    create_gold_material, create_silver_material, assign_material
)
from scripts.lighting import setup_three_point_lighting
from scripts.camera import setup_perspective_camera, set_active_camera


def create_scene(args=None):
    """Create a parametric scene based on arguments."""
    # Parse arguments
    num_objects = 3  # Default
    object_type = "cube"  # Default
    
    if args and len(args) > 0:
        num_objects = int(args[0]) if args[0].isdigit() else num_objects
    
    if args and len(args) > 1:
        object_type = args[1]
    
    # Clear existing objects
    clear_scene()
    
    # Create materials
    materials = [
        create_red_material(),
        create_green_material(),
        create_blue_material(),
        create_gold_material(),
        create_silver_material()
    ]
    
    # Create objects
    objects = []
    spacing = 3.0
    
    for i in range(num_objects):
        if object_type == "sphere":
            obj = create_sphere(
                radius=1,
                location=((i - num_objects/2) * spacing, 0, 0),
                name=f"Sphere_{i}"
            )
        else:
            obj = create_cube(
                size=1.5,
                location=((i - num_objects/2) * spacing, 0, 0),
                name=f"Cube_{i}"
            )
        
        # Assign material
        assign_material(obj, materials[i % len(materials)])
        objects.append(obj)
    
    # Setup camera
    camera = setup_perspective_camera(
        location=(0, -10, 8),
        target=(0, 0, 0),
        name="MainCamera"
    )
    set_active_camera(camera)
    
    # Setup lighting
    setup_three_point_lighting(energy=500)
    
    print(f"Created parametric scene with {num_objects} {object_type}s")


if __name__ == "__main__":
    create_scene(sys.argv[1:] if len(sys.argv) > 1 else None)

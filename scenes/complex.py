#!/usr/bin/env python3
"""
Complex scene - demonstrates advanced features like animations, materials, and lighting.

This scene creates a more sophisticated setup with multiple object types,
complex materials, and professional lighting.
"""
import sys
import os
import math

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.geometry import (
    create_cube, create_sphere, create_cylinder, create_torus,
    create_plane, create_monkey, clear_scene
)
from scripts.materials import (
    create_material, create_glass_material, create_emission_material,
    create_red_material, create_blue_material, assign_material
)
from scripts.lighting import setup_studio_lighting, setup_environment_light
from scripts.camera import setup_perspective_camera, set_active_camera, create_iso_camera


def create_scene(args=None):
    """Create a complex scene with multiple elements."""
    # Clear existing objects
    clear_scene()
    
    # Create ground plane
    ground = create_plane(size=20, location=(0, 0, -1), name="Ground")
    ground_mat = create_material(
        name="GroundMaterial",
        color=(0.3, 0.3, 0.3, 1),
        metallic=0.0,
        roughness=1.0
    )
    assign_material(ground, ground_mat)
    
    # Create central objects
    center_cube = create_cube(size=2, location=(0, 0, 0), name="CenterCube")
    red_mat = create_red_material()
    assign_material(center_cube, red_mat)
    
    # Create surrounding spheres
    num_spheres = 6
    radius = 4
    for i in range(num_spheres):
        angle = (i / num_spheres) * 2 * math.pi
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        z = 0
        
        sphere = create_sphere(
            radius=0.8,
            location=(x, y, z),
            name=f"Sphere_{i}"
        )
        
        # Use different materials for variety
        if i % 3 == 0:
            mat = create_material(
                name=f"SphereMat_{i}",
                color=(1, 0.5, 0, 1),  # Orange
                metallic=0.5,
                roughness=0.3
            )
        elif i % 3 == 1:
            mat = create_material(
                name=f"SphereMat_{i}",
                color=(0, 0.5, 1, 1),  # Light blue
                metallic=0.0,
                roughness=0.8
            )
        else:
            mat = create_glass_material(name=f"GlassMat_{i}", ior=1.45)
        
        assign_material(sphere, mat)
    
    # Create a torus
    torus = create_torus(
        major_radius=2,
        minor_radius=0.3,
        location=(0, 0, 1),
        name="Torus"
    )
    torus_mat = create_material(
        name="TorusMaterial",
        color=(0.5, 0, 0.5, 1),  # Purple
        metallic=0.8,
        roughness=0.1
    )
    assign_material(torus, torus_mat)
    
    # Create a monkey head
    monkey = create_monkey(location=(-3, -3, 0.5), name="Suzanne")
    monkey_mat = create_blue_material()
    assign_material(monkey, monkey_mat)
    
    # Create a light emitting cylinder
    light_cyl = create_cylinder(
        radius=0.5,
        depth=2,
        location=(3, 3, 1),
        name="LightCylinder"
    )
    emission_mat = create_emission_material(
        name="LightMaterial",
        color=(1, 1, 0.8, 1),
        strength=2.0
    )
    assign_material(light_cyl, emission_mat)
    
    # Setup camera - isometric view
    camera = create_iso_camera(distance=15, angle=30, name="IsoCamera")
    set_active_camera(camera)
    
    # Setup professional lighting
    setup_studio_lighting(energy=2000)
    
    # Setup environment lighting
    setup_environment_light(color=(0.8, 0.8, 1.0, 1), strength=0.1)
    
    print("Created complex scene with multiple objects and advanced lighting")


if __name__ == "__main__":
    create_scene()

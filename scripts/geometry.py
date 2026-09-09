"""
Geometry creation helpers for Blender headless rendering.
"""
import bpy


def clear_scene():
    """Clear all objects from the current scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def create_cube(size=2, location=(0, 0, 0), name="Cube"):
    """Create a cube mesh."""
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    cube = bpy.context.active_object
    cube.name = name
    return cube


def create_sphere(radius=1, location=(0, 0, 0), name="Sphere"):
    """Create a sphere mesh."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location)
    sphere = bpy.context.active_object
    sphere.name = name
    return sphere


def create_cylinder(radius=1, depth=2, location=(0, 0, 0), name="Cylinder"):
    """Create a cylinder mesh."""
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location)
    cylinder = bpy.context.active_object
    cylinder.name = name
    return cylinder


def create_plane(size=2, location=(0, 0, 0), name="Plane"):
    """Create a plane mesh."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    plane = bpy.context.active_object
    plane.name = name
    return plane


def create_torus(major_radius=1, minor_radius=0.25, location=(0, 0, 0), name="Torus"):
    """Create a torus mesh."""
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        location=location
    )
    torus = bpy.context.active_object
    torus.name = name
    return torus


def create_cone(radius=1, depth=2, location=(0, 0, 0), name="Cone"):
    """Create a cone mesh."""
    bpy.ops.mesh.primitive_cone_add(radius=radius, depth=depth, location=location)
    cone = bpy.context.active_object
    cone.name = name
    return cone


def create_grid(size=10, x_subdivisions=10, y_subdivisions=10, location=(0, 0, 0), name="Grid"):
    """Create a grid mesh."""
    bpy.ops.mesh.primitive_grid_add(
        size=size,
        x_subdivisions=x_subdivisions,
        y_subdivisions=y_subdivisions,
        location=location
    )
    grid = bpy.context.active_object
    grid.name = name
    return grid


def create_monkey(location=(0, 0, 0), name="Suzanne"):
    """Create a Suzanne monkey head mesh."""
    bpy.ops.mesh.primitive_monkey_add(location=location)
    monkey = bpy.context.active_object
    monkey.name = name
    return monkey


def create_ico_sphere(radius=1, subdivisions=2, location=(0, 0, 0), name="IcoSphere"):
    """Create an ico sphere mesh."""
    bpy.ops.mesh.primitive_ico_sphere_add(
        radius=radius,
        subdivisions=subdivisions,
        location=location
    )
    sphere = bpy.context.active_object
    sphere.name = name
    return sphere


def duplicate_object(obj, name=None, translation=(0, 0, 0)):
    """Duplicate an existing object."""
    obj.select_set(True)
    bpy.ops.object.duplicate()
    new_obj = bpy.context.active_object
    
    if name:
        new_obj.name = name
    
    new_obj.location.x += translation[0]
    new_obj.location.y += translation[1]
    new_obj.location.z += translation[2]
    
    obj.select_set(False)
    return new_obj


def scale_object(obj, scale=(1, 1, 1)):
    """Scale an object."""
    obj.scale = scale


def rotate_object(obj, rotation_euler=(0, 0, 0)):
    """Rotate an object using Euler angles (in radians)."""
    obj.rotation_euler = rotation_euler


def move_object(obj, location):
    """Move an object to a new location."""
    obj.location = location

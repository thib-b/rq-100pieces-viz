"""
Camera setup helpers for Blender headless rendering.
"""
import bpy
import math


def create_camera(location=(0, 0, 0), rotation=(0, 0, 0), name="Camera"):
    """Create a new camera."""
    bpy.ops.object.camera_add(location=location, rotation=rotation)
    camera = bpy.context.active_object
    camera.name = name
    bpy.context.scene.camera = camera
    return camera


def setup_camera_for_object(camera, target_obj, distance=5, angle=(0, 0, 0)):
    """Position a camera to look at a specific object."""
    # Get object's world position
    target_pos = target_obj.location
    
    # Calculate camera position based on distance and angle
    # Convert spherical coordinates to Cartesian
    theta = angle[0]  # Azimuth (around Y axis)
    phi = angle[1]    # Elevation (from XZ plane)
    
    cam_x = target_pos[0] + distance * math.cos(theta) * math.cos(phi)
    cam_y = target_pos[1] + distance * math.sin(theta) * math.cos(phi)
    cam_z = target_pos[2] + distance * math.sin(phi)
    
    camera.location = (cam_x, cam_y, cam_z)
    
    # Make camera look at target
    direction = target_pos - camera.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()
    
    return camera


def create_track_to_constraint(camera, target_obj):
    """Create a track-to constraint so camera always points at target."""
    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = target_obj
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'
    return constraint


def setup_camera_lens(camera, focal_length=50, sensor_width=36):
    """Configure camera lens settings."""
    camera.data.lens = focal_length
    camera.data.sensor_width = sensor_width
    return camera


def setup_camera_clip(camera, clip_start=0.1, clip_end=1000):
    """Configure camera clipping planes."""
    camera.data.clip_start = clip_start
    camera.data.clip_end = clip_end
    return camera


def setup_camera_viewport(camera, width=1920, height=1080):
    """Configure camera viewport settings."""
    camera.data.display_size_x = width
    camera.data.display_size_y = height
    return camera


def create_top_down_camera(height=10, name="TopDownCamera"):
    """Create a top-down orthographic camera."""
    cam = create_camera(location=(0, 0, height), name=name)
    cam.rotation_euler = (math.pi / 2, 0, 0)  # Look straight down
    
    # Set to orthographic
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 5
    
    return cam


def create_front_camera(distance=10, name="FrontCamera"):
    """Create a front-facing camera."""
    cam = create_camera(location=(0, -distance, 0), name=name)
    cam.rotation_euler = (0, 0, 0)  # Look along positive Y
    return cam


def create_side_camera(distance=10, name="SideCamera"):
    """Create a side camera."""
    cam = create_camera(location=(-distance, 0, 0), name=name)
    cam.rotation_euler = (0, math.pi / 2, 0)  # Look along positive X
    return cam


def create_iso_camera(distance=15, angle=45, name="IsoCamera"):
    """Create an isometric camera view."""
    # Calculate isometric position
    height = distance * math.sin(math.radians(angle))
    horizontal = distance * math.cos(math.radians(angle))
    
    cam = create_camera(
        location=(-horizontal, -horizontal, height),
        name=name
    )
    
    # Point towards origin
    from mathutils import Vector
    direction = Vector((0, 0, 0)) - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    return cam


def setup_camera_dof(camera, focus_distance=5, f_stop=2.8):
    """Enable and configure depth of field."""
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = focus_distance
    camera.data.dof.aperture_fstop = f_stop
    return camera


def setup_perspective_camera(location=(5, -5, 5), target=(0, 0, 0), name="PerspectiveCamera"):
    """Create a perspective camera looking at a target point."""
    cam = create_camera(location=location, name=name)
    
    # Point towards target
    direction = (target[0] - location[0],
                 target[1] - location[1],
                 target[2] - location[2])
    
    from mathutils import Vector
    direction_vec = Vector(direction)
    rot_quat = direction_vec.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    return cam


def create_360_camera_rig(center=(0, 0, 0), radius=5, name_prefix="Cam_360"):
    """Create multiple cameras for 360-degree coverage."""
    cameras = []
    num_cameras = 8  # 8 cameras for full 360 coverage
    
    for i in range(num_cameras):
        angle = (i / num_cameras) * 2 * math.pi
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        z = center[2] + radius * 0.2  # Slightly elevated
        
        cam = create_camera(
            location=(x, y, z),
            name=f"{name_prefix}_{i:02d}"
        )
        
        # Point towards center
        direction = (center[0] - x, center[1] - y, center[2] - z)
        from mathutils import Vector
        direction_vec = Vector(direction)
        rot_quat = direction_vec.to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot_quat.to_euler()
        
        cameras.append(cam)
    
    return cameras


def set_active_camera(camera):
    """Set a camera as the active scene camera."""
    bpy.context.scene.camera = camera
    return camera

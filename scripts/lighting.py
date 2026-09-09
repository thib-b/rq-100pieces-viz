"""
Lighting setup helpers for Blender headless rendering.
"""
import bpy


def create_sun_light(location=(0, 0, 10), energy=1.0, name="Sun"):
    """Create a sun light (directional light at infinite distance)."""
    bpy.ops.object.light_add(type='SUN', location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    return light


def create_point_light(location=(0, 0, 5), energy=1000, radius=1.0, name="PointLight"):
    """Create a point light (omnidirectional)."""
    bpy.ops.object.light_add(type='POINT', location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    light.data.shadow_soft_size = radius
    return light


def create_spot_light(location=(0, 0, 5), energy=1000, target=None, name="SpotLight"):
    """Create a spot light (directional cone)."""
    bpy.ops.object.light_add(type='SPOT', location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    
    if target:
        # Track to target
        constraint = light.constraints.new(type='TRACK_TO')
        constraint.target = target
        constraint.track_axis = 'TRACK_NEGATIVE_Z'
        constraint.up_axis = 'UP_Y'
    
    return light


def create_hemi_light(location=(0, 0, 5), energy=0.5, name="HemiLight"):
    """Create a hemisphere light (soft ambient light)."""
    bpy.ops.object.light_add(type='HEMI', location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    return light


def create_area_light(location=(0, 0, 5), size=2, energy=100, name="AreaLight"):
    """Create an area light (rectangular light source)."""
    bpy.ops.object.light_add(type='AREA', location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    light.data.shape = 'SQUARE'
    light.data.size = size
    return light


def setup_three_point_lighting(energy=500):
    """Setup classic three-point lighting: key, fill, rim."""
    key_light = create_point_light(
        location=(3, -3, 4),
        energy=energy,
        name="KeyLight"
    )
    
    fill_light = create_point_light(
        location=(-3, -3, 2),
        energy=energy * 0.5,
        name="FillLight"
    )
    
    rim_light = create_point_light(
        location=(0, 3, 3),
        energy=energy * 0.7,
        name="RimLight"
    )
    
    return {
        'key': key_light,
        'fill': fill_light,
        'rim': rim_light
    }


def setup_studio_lighting(energy=1000):
    """Setup studio lighting with multiple point lights."""
    lights = []
    
    # Top light
    lights.append(create_point_light(
        location=(0, 0, 10),
        energy=energy,
        name="TopLight"
    ))
    
    # Front lights
    lights.append(create_point_light(
        location=(3, -2, 5),
        energy=energy * 0.6,
        name="FrontRightLight"
    ))
    
    lights.append(create_point_light(
        location=(-3, -2, 5),
        energy=energy * 0.6,
        name="FrontLeftLight"
    ))
    
    # Back lights for rim
    lights.append(create_point_light(
        location=(3, 2, 4),
        energy=energy * 0.4,
        name="BackRightLight"
    ))
    
    lights.append(create_point_light(
        location=(-3, 2, 4),
        energy=energy * 0.4,
        name="BackLeftLight"
    ))
    
    return lights


def setup_environment_light(color=(1, 1, 1, 1), strength=0.5):
    """Setup environment/world lighting."""
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new(name="World")
        bpy.context.scene.world = world
    
    world.use_nodes = True
    nodes = world.node_tree.nodes
    
    # Clear default nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create background shader
    bg = nodes.new(type='ShaderNodeBackground')
    bg.inputs['Color'].default_value = color
    bg.inputs['Strength'].default_value = strength
    
    # Create output node
    output = nodes.new(type='ShaderNodeOutputWorld')
    output.location = (200, 0)
    
    # Link nodes
    links = world.node_tree.links
    links.new(bg.outputs['Background'], output.inputs['Surface'])
    
    return world


def setup_hdri_lighting(hdri_path):
    """Setup HDRI environment lighting."""
    try:
        # Load HDRI image
        image = bpy.data.images.load(hdri_path)
    except RuntimeError:
        print(f"HDRI file not found: {hdri_path}")
        return None
    
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new(name="HDRIWorld")
        bpy.context.scene.world = world
    
    world.use_nodes = True
    nodes = world.node_tree.nodes
    
    # Clear default nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create environment texture
    env_tex = nodes.new(type='ShaderNodeTexEnvironment')
    env_tex.image = image
    env_tex.location = (-200, 0)
    
    # Create background shader
    bg = nodes.new(type='ShaderNodeBackground')
    bg.location = (0, 0)
    
    # Create mapping for rotation if needed
    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (-400, 0)
    
    # Create texture coordinate
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-600, 0)
    
    # Create output node
    output = nodes.new(type='ShaderNodeOutputWorld')
    output.location = (200, 0)
    
    # Link nodes
    links = world.node_tree.links
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
    links.new(env_tex.outputs['Color'], bg.inputs['Color'])
    links.new(bg.outputs['Background'], output.inputs['Surface'])
    
    return world


def create_light_probe(location=(0, 0, 0), name="LightProbe"):
    """Create a light probe for capturing lighting."""
    bpy.ops.object.lightprobe_add(type='GRID', location=location)
    probe = bpy.context.active_object
    probe.name = name
    return probe


def setup_basic_lighting(energy=100):
    """Setup basic single light for simple scenes."""
    return create_point_light(
        location=(5, 5, 5),
        energy=energy,
        name="MainLight"
    )

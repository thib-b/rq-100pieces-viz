"""
Material and shader utilities for Blender headless rendering.
"""
import bpy


def create_material(name, color=(1, 1, 1, 1), metallic=0, roughness=0.5, specular=0.5):
    """Create a new principled BSDF material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    # Clear default nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create principled BSDF shader
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    
    # Create output node
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)
    
    # Link nodes
    links = mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat


def create_diffuse_material(name, color=(1, 1, 1, 1)):
    """Create a simple diffuse material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    for node in nodes:
        nodes.remove(node)
    
    bsdf = nodes.new(type='ShaderNodeBsdfDiffuse')
    bsdf.inputs['Color'].default_value = color
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)
    
    links = mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat


def create_glossy_material(name, color=(1, 1, 1, 1), roughness=0.2):
    """Create a glossy material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    for node in nodes:
        nodes.remove(node)
    
    bsdf = nodes.new(type='ShaderNodeBsdfGlossy')
    bsdf.inputs['Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)
    
    links = mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat


def create_glass_material(name, color=(1, 1, 1, 1), roughness=0.0, ior=1.5):
    """Create a glass material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    for node in nodes:
        nodes.remove(node)
    
    bsdf = nodes.new(type='ShaderNodeBsdfGlass')
    bsdf.inputs['Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['IOR'].default_value = ior
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)
    
    links = mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat


def create_emission_material(name, color=(1, 1, 1, 1), strength=1.0):
    """Create an emission material (for light sources)."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    for node in nodes:
        nodes.remove(node)
    
    emission = nodes.new(type='ShaderNodeEmission')
    emission.inputs['Color'].default_value = color
    emission.inputs['Strength'].default_value = strength
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)
    
    links = mat.node_tree.links
    links.new(emission.outputs['Emission'], output.inputs['Surface'])
    
    return mat


def create_textured_material(name, image_path, uv_map="UVMap"):
    """Create a material with an image texture."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    for node in nodes:
        nodes.remove(node)
    
    # Load image texture
    try:
        image = bpy.data.images.load(image_path)
    except RuntimeError:
        # Create a blank image if not found
        image = bpy.data.images.new(name="placeholder", width=1024, height=1024)
    
    # Create texture node
    tex_node = nodes.new(type='ShaderNodeTexImage')
    tex_node.image = image
    tex_node.location = (-200, 0)
    
    # Create principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    
    # Create output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)
    
    # Link nodes
    links = mat.node_tree.links
    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat


def assign_material(obj, material):
    """Assign a material to an object."""
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)


def create_gradient_material(name, color1=(1, 0, 0, 1), color2=(0, 0, 1, 1)):
    """Create a material with a color gradient."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    for node in nodes:
        nodes.remove(node)
    
    # Create gradient texture
    gradient = nodes.new(type='ShaderNodeTexGradient')
    gradient.location = (-200, 0)
    
    # Create color ramp (optional enhancement)
    ramp = nodes.new(type='ShaderNodeValToRGB')
    ramp.location = (0, 0)
    ramp.color_ramp.elements[0].color = color1
    ramp.color_ramp.elements[1].color = color2
    
    # Create principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)
    
    # Create output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (400, 0)
    
    # Link nodes
    links = mat.node_tree.links
    links.new(gradient.outputs['Color'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat


# Predefined color materials for convenience

def create_red_material(name="RedMaterial"):
    """Create a red material."""
    return create_diffuse_material(name, (1, 0, 0, 1))


def create_green_material(name="GreenMaterial"):
    """Create a green material."""
    return create_diffuse_material(name, (0, 1, 0, 1))


def create_blue_material(name="BlueMaterial"):
    """Create a blue material."""
    return create_diffuse_material(name, (0, 0, 1, 1))


def create_white_material(name="WhiteMaterial"):
    """Create a white material."""
    return create_diffuse_material(name, (1, 1, 1, 1))


def create_black_material(name="BlackMaterial"):
    """Create a black material."""
    return create_diffuse_material(name, (0, 0, 0, 1))


def create_gold_material(name="GoldMaterial"):
    """Create a gold material."""
    return create_material(name, (0.8, 0.6, 0.2, 1), metallic=1.0, roughness=0.2)


def create_silver_material(name="SilverMaterial"):
    """Create a silver material."""
    return create_material(name, (0.8, 0.8, 0.8, 1), metallic=1.0, roughness=0.1)

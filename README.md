# Blender Headless Visualization Pipeline

A complete pipeline for generating and rendering 3D scenes headlessly using Blender's Python API.

## Overview

This project provides a framework for programmatically creating 3D scenes and rendering them without opening Blender's GUI. It's ideal for:

- Automated rendering pipelines
- Procedural scene generation
- Batch processing of 3D assets
- Integration with other applications
- Scientific visualization

## Requirements

- **Blender 3.0+** (tested with Blender 5.2.1 LTS)
- Python 3.x (Blender ships with its own Python interpreter)

## Installation

1. Ensure Blender is installed and available in your PATH
2. Clone this repository
3. No additional pip packages required for basic functionality

### Verify Blender Installation

```bash
blender --version
# Should output: Blender 5.2.1
```

## Quick Start

### Run the Minimal Example

```bash
# Test basic rendering
blender --background --python test_render.py -- /tmp/test_render.png

# Verify output
ls -la /tmp/test_render.png
```

### Use the Main Render Script

```bash
# Render a scene definition
blender --background --python render.py -- scenes/basic.py /tmp/basic.png

# Render with custom arguments
blender --background --python render.py -- scenes/parametric.py /tmp/parametric.png -- 5 cube
```

## Project Structure

```
blender/
├── scripts/                      # Reusable helper modules
│   ├── __init__.py
│   ├── geometry.py              # Geometry creation helpers
│   ├── materials.py             # Material and shader utilities
│   ├── lighting.py              # Lighting setup helpers
│   └── camera.py                # Camera setup utilities
│
├── scenes/                      # Scene definition scripts
│   ├── basic.py                 # Simple test scene
│   ├── parametric.py            # Parameterized scene generation
│   └── complex.py               # Advanced scene with multiple elements
│
├── render.py                    # Main rendering script
├── test_render.py               # Minimal working example
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Usage Examples

### Basic Rendering

```python
import bpy

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create a cube
bpy.ops.mesh.primitive_cube_add(size=2)

# Set render output
bpy.context.scene.render.filepath = '/tmp/cube.png'

# Render
bpy.ops.render.render(write_still=True)
```

Run with:
```bash
blender --background --python my_script.py
```

### Using the Pipeline

1. **Create a new scene file** in `scenes/`:

```python
# scenes/my_scene.py
from scripts.geometry import create_cube, clear_scene
from scripts.materials import create_red_material, assign_material
from scripts.camera import setup_perspective_camera, set_active_camera
from scripts.lighting import setup_basic_lighting

def create_scene(args=None):
    clear_scene()
    
    cube = create_cube(size=2)
    assign_material(cube, create_red_material())
    
    camera = setup_perspective_camera(location=(5, -5, 5), target=(0, 0, 0))
    set_active_camera(camera)
    
    setup_basic_lighting()
```

2. **Render it**:

```bash
blender --background --python render.py -- scenes/my_scene.py /tmp/my_scene.png
```

## API Reference

### Geometry Module (`scripts/geometry.py`)

```python
from scripts.geometry import (
    clear_scene,
    create_cube, create_sphere, create_cylinder,
    create_plane, create_torus, create_cone,
    create_grid, create_monkey, create_ico_sphere,
    duplicate_object, scale_object, rotate_object, move_object
)
```

### Materials Module (`scripts/materials.py`)

```python
from scripts.materials import (
    create_material, create_diffuse_material,
    create_glossy_material, create_glass_material,
    create_emission_material, create_textured_material,
    create_gradient_material, assign_material,
    create_red_material, create_green_material,
    create_blue_material, create_gold_material,
    create_silver_material
)
```

### Lighting Module (`scripts/lighting.py`)

```python
from scripts.lighting import (
    create_sun_light, create_point_light,
    create_spot_light, create_hemi_light,
    create_area_light, setup_three_point_lighting,
    setup_studio_lighting, setup_environment_light,
    setup_hdri_lighting, create_light_probe,
    setup_basic_lighting
)
```

### Camera Module (`scripts/camera.py`)

```python
from scripts.camera import (
    create_camera, setup_camera_for_object,
    create_track_to_constraint, setup_camera_lens,
    setup_camera_clip, setup_camera_viewport,
    create_top_down_camera, create_front_camera,
    create_side_camera, create_iso_camera,
    setup_camera_dof, setup_perspective_camera,
    create_360_camera_rig, set_active_camera
)
```

## Render Settings

Configure render settings in your scene or use the defaults from `render.py`:

```python
scene = bpy.context.scene
scene.render.engine = 'CYCLES'  # or 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.filepath = '/path/to/output.png'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.cycles.samples = 32  # Higher = better quality, slower
scene.cycles.device = 'GPU'  # Use GPU if available
```

## Performance Tips

1. **Lower resolution for testing**:
   ```python
   scene.render.resolution_percentage = 50  # 50% of full resolution
   ```

2. **Fewer samples for testing**:
   ```python
   scene.cycles.samples = 16  # Low for testing
   ```

3. **Use GPU rendering**:
   ```python
   scene.cycles.device = 'GPU'
   ```

4. **Save and reuse Blender processes** for batch rendering (advanced)

## Advanced Usage

### Animation

```python
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 100
scene.render.filepath = '/tmp/frame_####.png'  # Frame numbering

# Animate objects
for frame in range(1, 101):
    bpy.context.scene.frame_set(frame)
    obj.rotation_euler.z = frame * 0.01
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)

# Render animation
bpy.ops.render.render(animation=True)
```

### Batch Processing

```bash
#!/bin/bash

# Render multiple scenes
for scene in scenes/*.py; do
    output="/tmp/$(basename $scene .py).png"
    blender --background --python render.py -- "$scene" "$output"
done
```

### Using with Python (without Blender)

Note: You cannot import `bpy` from regular Python. You must run scripts through Blender:

```bash
# This works
blender --background --python my_script.py

# This does NOT work
python my_script.py  # bpy will not be available
```

## Debugging

1. **Check Blender version**:
   ```bash
   blender --version
   ```

2. **Test bpy availability**:
   ```bash
   blender --background --python-expr "import bpy; print('bpy available')"
   ```

3. **View error output**:
   ```bash
   blender --background --python my_script.py 2>&1
   ```

4. **Write debug to file** (from within your script):
   ```python
   with open('/tmp/blender_debug.log', 'w') as f:
       f.write("Debug info here")
   ```

## Known Issues

1. **Blender's Python is isolated**: Packages installed via pip in your system Python won't be available to Blender's embedded Python.

2. **GPU rendering**: May require additional setup depending on your hardware and Blender version.

3. **Memory usage**: Complex scenes can consume significant memory, especially with high sample counts.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Submit a pull request

## License

MIT License

## Resources

- [Blender Python API Documentation](https://docs.blender.org/api/current/)
- [Blender Manual - Python Scripting](https://docs.blender.org/manual/en/latest/advanced/scripting/index.html)
- [Blender Stack Exchange](https://blender.stackexchange.com/)

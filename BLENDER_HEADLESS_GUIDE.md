# Blender Headless Visualization Pipeline - Quick Start Guide

## Summary

This guide provides everything needed to run Blender headlessly for programmatic 3D rendering.

## TL;DR - The Core Concept

You need exactly **3 things** (all already on your system):

1. **`blender --background`** - Runs Blender without GUI
2. **`bpy`** - Blender's built-in Python API
3. **A Python script** - Your code that creates scenes and calls `bpy.ops.render.render()`

## Quick Example

```python
# save as scene.py
import bpy
bpy.ops.mesh.primitive_cube_add(size=2)
bpy.context.scene.render.filepath = "/tmp/out.png"
bpy.ops.render.render(write_still=True)
```

```bash
blender --background --python scene.py
```

Output: `/tmp/out.png` with a rendered cube

---

## Prerequisites

- **Blender 3.0+** - Installed at `/opt/homebrew/bin/blender` (v5.2.1 LTS confirmed working)
- **Python** - Already embedded in Blender (no separate pip install needed for basic usage)

Verify installation:
```bash
blender --version
# Should output: Blender 5.2.1 LTS
```

---

## Project Structure (Implemented)

```
blender/
├── README.md                    # Full documentation
├── BLENDER_HEADLESS_GUIDE.md    # This file
├── render.py                    # Main rendering entry point
├── test_render.py               # Minimal working example
├── requirements.txt             # Optional dependencies
├── scripts/
│   ├── geometry.py              # Create cubes, spheres, etc.
│   ├── materials.py             # Materials, shaders, colors
│   ├── lighting.py              # Sun, point, spot, area lights
│   └── camera.py                # Camera setup utilities
└── scenes/
    ├── basic.py                 # Simple red cube scene
    ├── parametric.py            # Dynamic scene (accepts args)
    └── complex.py               # Advanced multi-object scene
```

---

## How-To

### Basic Rendering

```python
import bpy

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Add geometry
bpy.ops.mesh.primitive_cube_add(size=2)

# Configure render
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.render.filepath = '/tmp/cube.png'
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600
bpy.context.scene.cycles.samples = 32

# Render
bpy.ops.render.render(write_still=True)
```

Run:
```bash
blender --background --python my_script.py
```

### Using the Pipeline

```bash
# Render a predefined scene
blender --background --python render.py -- scenes/basic.py /tmp/basic.png

# Render with parameters (5 spheres)
blender --background --python render.py -- scenes/parametric.py /tmp/para.png 5 sphere

# Render minimal example
blender --background --python test_render.py -- /tmp/test.png
```

---

## API Reference

### Geometry (scripts/geometry.py)

```python
from scripts.geometry import (
    clear_scene, create_cube, create_sphere, create_cylinder,
    create_plane, create_torus, create_cone, create_grid,
    create_monkey, duplicate_object, scale_object, rotate_object, move_object
)
```

### Materials (scripts/materials.py)

```python
from scripts.materials import (
    create_material, create_diffuse_material, create_glossy_material,
    create_glass_material, create_emission_material, assign_material,
    create_red_material, create_green_material, create_blue_material,
    create_gold_material, create_silver_material
)
```

### Lighting (scripts/lighting.py)

```python
from scripts.lighting import (
    create_sun_light, create_point_light, create_spot_light,
    create_hemi_light, create_area_light,
    setup_three_point_lighting, setup_studio_lighting,
    setup_environment_light, setup_basic_lighting
)
```

### Camera (scripts/camera.py)

```python
from scripts.camera import (
    create_camera, create_top_down_camera, create_iso_camera,
    setup_perspective_camera, setup_camera_for_object,
    set_active_camera, create_track_to_constraint
)
```

---

## Scene Creation Example

```python
# scenes/my_scene.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.geometry import create_cube, clear_scene
from scripts.materials import create_red_material, assign_material
from scripts.camera import setup_perspective_camera, set_active_camera
from scripts.lighting import setup_basic_lighting

def create_scene(args=None):
    clear_scene()
    
    # Create object
    cube = create_cube(size=2, location=(0, 0, 0))
    assign_material(cube, create_red_material())
    
    # Setup camera
    camera = setup_perspective_camera(location=(5, -5, 5), target=(0, 0, 0))
    set_active_camera(camera)
    
    # Setup lighting
    setup_basic_lighting(energy=100)
```

---

## Key Gotchas & Fixes

### 1. Blender 5.2 API Change - Principled BSDF
**Issue:** `Specular` input was removed from Principled BSDF shader.

**Fix:** Remove `specular` parameter from `create_material()`. The function signature changed from:
```python
# OLD (Blender < 5.2)
def create_material(name, color=(1,1,1,1), metallic=0, roughness=0.5, specular=0.5):
    # ...
    bsdf.inputs['Specular'].default_value = specular
```

To:
```python
# NEW (Blender 5.2+)
def create_material(name, color=(1,1,1,1), metallic=0, roughness=0.5, specular=0.5):
    # ...
    # specular parameter is ignored, removed from inputs
```

### 2. Vector Math - Tuple vs Vector
**Issue:** Cannot subtract tuple from Vector directly.

**Fix:** Convert tuple to Vector:
```python
from mathutils import Vector

# Wrong: (0, 0, 0) - cam.location
# Right: Vector((0, 0, 0)) - cam.location
```

### 3. bpy Only Works Inside Blender
**Important:** `import bpy` only works when executed via Blender's Python interpreter.

This **does NOT work**:
```bash
python my_script.py  # System Python - bpy not available
```

This **DOES work**:
```bash
blender --background --python my_script.py  # Blender's Python - bpy available
```

---

## Argument Passing

### To test_render.py
```bash
blender --background --python test_render.py -- /output/path.png
```

The `--` separates Blender args from Python script args. Everything after `--` is passed to `sys.argv`.

### To render.py
```bash
blender --background --python render.py -- scenes/basic.py /output/path.png
```

- `scenes/basic.py` = scene definition file
- `/output/path.png` = output file
- Additional args after these are passed to `create_scene()` function

Example with scene args:
```bash
blender --background --python render.py -- scenes/parametric.py /out.png 5 sphere
# Creates 5 spheres
```

**Note:** Do NOT use a second `--` in the command. This will break argument parsing.

---

## Render Settings

```python
scene = bpy.context.scene

# Engine
scene.render.engine = 'CYCLES'  # or 'BLENDER_EEVEE_NEXT'

# Resolution
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100  # 50 = half resolution

# Output
scene.render.filepath = '/path/to/output.png'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'

# Quality (Cycles)
scene.cycles.samples = 32  # Lower for testing, higher for final
scene.cycles.device = 'GPU'  # Use GPU if available

# Camera
scene.camera = bpy.data.objects['Camera']
```

---

## Performance Tips

1. **Lower resolution for testing:**
   ```python
   scene.render.resolution_percentage = 50
   ```

2. **Fewer samples for testing:**
   ```python
   scene.cycles.samples = 16
   ```

3. **Use GPU:**
   ```python
   scene.cycles.device = 'GPU'
   ```

4. **Batch rendering:** Create a shell script to render multiple scenes sequentially.

---

## Debugging

### Check bpy is available
```bash
blender --background --python-expr "import bpy; print('bpy OK')"
```

### View full error output
```bash
blender --background --python my_script.py 2>&1
```

### Write debug to file (from within script)
```python
with open('/tmp/blender_debug.log', 'w') as f:
    f.write(str(dir(bpy.context)))
```

### Check Blender Python version
```bash
blender --background --python-expr "import sys; print(sys.version)"
```

---

## Output Formats

```python
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.file_format = 'TIFF'
```

---

## Animation

```python
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 100
scene.render.filepath = '/tmp/frame_####.png'  # Auto frame numbering

# Animate an object
for frame in range(1, 101):
    bpy.context.scene.frame_set(frame)
    obj.rotation_euler.z = frame * 0.01
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)

# Render animation
bpy.ops.render.render(animation=True)
```

---

## Batch Processing Example

```bash
#!/bin/bash
# render_all.sh

SCENES_DIR="./scenes"
OUTPUT_DIR="/tmp/renders"

mkdir -p "$OUTPUT_DIR"

for scene in "$SCENES_DIR"/*.py; do
    name=$(basename "$scene" .py)
    output="$OUTPUT_DIR/$name.png"
    echo "Rendering $name..."
    blender --background --python render.py -- "$scene" "$output"
done

chmod +x render_all.sh
./render_all.sh
```

---

## Resources

- [Blender Python API Docs](https://docs.blender.org/api/current/)
- [Blender Manual - Scripting](https://docs.blender.org/manual/en/latest/advanced/scripting/index.html)
- [Blender Stack Exchange](https://blender.stackexchange.com/)

---

## Verified Working Commands

```bash
# Verify Blender
blender --version

# Test bpy availability
blender --background --python-expr "import bpy; print('OK')"

# Minimal render
blender --background --python test_render.py -- /tmp/test.png

# Full pipeline test
blender --background --python render.py -- scenes/basic.py /tmp/basic.png
blender --background --python render.py -- scenes/parametric.py /tmp/para.png 5 cube
blender --background --python render.py -- scenes/complex.py /tmp/complex.png
```

---

## File Summary

| File | Lines | Purpose |
|------|-------|---------|
| test_render.py | 50 | Minimal working example |
| render.py | 120 | Main rendering script |
| scripts/geometry.py | 110 | Geometry creation |
| scripts/materials.py | 210 | Materials and shaders |
| scripts/lighting.py | 190 | Lighting setups |
| scripts/camera.py | 170 | Camera utilities |
| scenes/basic.py | 40 | Simple scene |
| scenes/parametric.py | 75 | Parameterized scene |
| scenes/complex.py | 120 | Advanced scene |

**Total: 10 files, ~1,100 lines of code**

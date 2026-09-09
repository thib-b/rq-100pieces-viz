#!/usr/bin/env python3
"""
"Haha" single — image-matched fluffy-bloom reveal → dissolve-to-photo (Blender headless).

On bare light grey, soft radial-gradient blob colonies ("fluffy blooms") GROW into the petri-dish
area, each coloured by SAMPLING the Haha artwork at its position — collectively reconstructing the
artwork. Appearance is accelerating ("exponential"): almost nothing at first, then more and more,
reaching full coverage at 1:55. The picture is held still 1:55 -> 2:15. Then 2:15 -> 3:01 the blooms
disappear one-by-one (accelerating) and, as they go, the REAL artwork photograph (cropped to the
dish circle) is revealed underneath. From 3:01 to the 3:13 end it holds static on the plate photo.

  blender --background --python animations/haha_reveal.py -- --last [--output DIR]      # spot-check
  blender --background --python animations/haha_reveal.py -- --preview [--fullres] --output DIR
  blender --background --python animations/haha_reveal.py -- --output DIR               # full render (auto-encodes DIR/haha_reveal.mp4)
"""
import bpy, bmesh, sys, os, math, random
import numpy as np

# ---------------- config ----------------
ART_PATH = "/Users/thib/dev/the100-visual-assets/Haha-Artwork.jpg"
FPS = 60
DURATION_SEC = 193
TOTAL_FRAMES = DURATION_SEC * FPS          # 11580

# mould blooms (reconstruct the artwork; accelerating build, full coverage at 1:55)
MOULD_END = 115 * FPS                       # 6900 — last bloom finishes growing here (full coverage, 1:55)
BLOOM_GROW = 300                            # frames a bloom takes to grow in from a point
N_BLOOM = 2400                              # higher: blooms alone must fill the whole dish (no orange base)
BLOOM_APPEAR_EXP = 0.4                      # birth/death CDF shaping (<1 => slow start, accelerating)
N_SWATCH = 30
LOBE_SEG = 20
BLOOM_DIAM_MIN, BLOOM_DIAM_MAX = 0.24, 0.60

# dissolve-to-photo reveal (blooms disappear one-by-one, revealing the plate photo)
HOLD_END = 135 * FPS                        # 8100 — picture held still until here (2:15), then dissolve starts
DISSOLVE_END = 181 * FPS                    # 10860 — all blooms gone here (3:01), plate photo fully revealed
BLOOM_FADE = 180                            # frames a bloom takes to fade to transparent (~3s)

RES_X, RES_Y = 2048, 1152
ORTHO_SCALE = 10.0
OUTPUT_DIR = "/tmp/haha_animation"

IMG_GRID = 700
PLATE_FRAC = 0.88                           # a touch smaller so soft bloom edges don't clip the frame


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_to_linear_arr(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def lin4(srgb3):
    return (srgb_to_linear(float(srgb3[0])), srgb_to_linear(float(srgb3[1])),
            srgb_to_linear(float(srgb3[2])), 1.0)


def args_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get_output(args):
    if "--output" in args:
        i = args.index("--output")
        if i + 1 < len(args):
            return args[i + 1]
    return OUTPUT_DIR


def clear_scene():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.curves,
                 bpy.data.materials, bpy.data.cameras, bpy.data.images):
        for item in list(coll):
            coll.remove(item)


# ---------------- image loading ----------------
def load_rgb(path, grid):
    img = bpy.data.images.load(path)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    px = buf.reshape(h, w, 4)[:, :, :3]            # row 0 = bottom; sRGB-encoded floats
    rows = np.linspace(0, h - 1, grid).astype(int)
    cols = np.linspace(0, w - 1, grid).astype(int)
    arr = px[np.ix_(rows, cols)].copy()
    bpy.data.images.remove(img)
    return arr


# ---------------- plate detection / agar estimate ----------------
def detect_plate(arr):
    grey = arr[[0, 0, -1, -1], [0, -1, 0, -1]].mean(axis=0)     # 4 corners
    diff = np.linalg.norm(arr - grey, axis=2)
    ys, xs = np.where(diff > 0.10)
    icx, icy = float(np.median(xs)), float(np.median(ys))       # robust centre
    ir = math.sqrt(len(xs) / math.pi) * 1.02                    # area-based radius (outlier-proof)
    return grey, icx, icy, ir


def estimate_agar(arr, icx, icy, ir):
    grid = arr.shape[0]
    yy, xx = np.mgrid[0:grid, 0:grid]
    d = np.sqrt((xx - icx) ** 2 + (yy - icy) ** 2) / ir
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    br = (r + g + b) / 3.0
    warm = (d > 0.80) & (d < 0.965) & (r > 0.45) & (r > g) & (g >= b) & \
           ((r - b) > 0.10) & (br > 0.35) & (br < 0.82)
    agar_edge = arr[warm].mean(axis=0) if warm.any() else np.array([0.86, 0.56, 0.36])
    agar_core = np.clip(agar_edge * np.array([1.02, 0.92, 0.80]), 0, 1)
    return agar_edge, agar_core


# ---------------- base plate (clean orange dish on grey, smooth feathered rim) ----------------
def build_base_plane(agar_edge, agar_core, grey, r_world, frame_w, frame_h):
    wb, hb = 1280, 720
    ye, xe = np.mgrid[0:hb, 0:wb]
    wx = (xe / (wb - 1) - 0.5) * frame_w
    wy = (ye / (hb - 1) - 0.5) * frame_h                 # row 0 = bottom (blender image)
    dist = np.sqrt(wx ** 2 + wy ** 2) / r_world
    t = np.clip(dist, 0, 1)[..., None]
    agar = agar_core * (1 - t) + agar_edge * t
    edge = np.clip((1.0 - dist) / 0.02, 0, 1)[..., None]  # smooth agar->grey over a thin rim band
    col = grey * (1 - edge) + agar * edge
    lin = srgb_to_linear_arr(col)
    rgba = np.concatenate([lin, np.ones((hb, wb, 1))], axis=2).astype(np.float32)

    img = bpy.data.images.new("base", wb, hb, alpha=True)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(rgba.reshape(-1))

    mat = bpy.data.materials.new("base")
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    texco = nt.nodes.new('ShaderNodeTexCoord')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Cubic'
    nt.links.new(texco.outputs['UV'], tex.inputs['Vector'])
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])

    me = bpy.data.meshes.new("baseplane")
    verts = [(-frame_w / 2, -frame_h / 2, 0), (frame_w / 2, -frame_h / 2, 0),
             (frame_w / 2, frame_h / 2, 0), (-frame_w / 2, frame_h / 2, 0)]
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    uvs = {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}
    for i, loop in enumerate(me.loops):
        uvl.data[i].uv = uvs[loop.vertex_index]
    me.materials.append(mat)
    obj = bpy.data.objects.new("baseplane", me)
    bpy.context.collection.objects.link(obj)


# ---------------- revealed plate photo (real artwork, cropped to dish, fades in as blooms leave) ----
def build_reveal_photo(icx, icy, ir, r_world, frame_w, frame_h):
    """Full-resolution artwork on a plane at z=0 (behind blooms), circular-cropped to the dish and
    faded 0->1 across the dissolve window. The source image file is used directly as the texture (no
    downsample), so the revealed plate is sharp; the circular crop + reveal fade are done in shader
    nodes. icx/icy/ir are in the IMG_GRID coordinate system used to detect the plate."""
    grid = IMG_GRID
    img = bpy.data.images.load(ART_PATH)                 # full resolution; default sRGB colorspace

    mat = bpy.data.materials.new("reveal")
    mat.use_nodes = True
    for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED'),
                      ('show_transparent_back', False)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    nt = mat.node_tree; nt.nodes.clear()
    # colour: sample the artwork via dish-aligned UVs (set on the mesh below), Cubic filtered
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
    tex.interpolation = 'Cubic'; tex.extension = 'EXTEND'
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    # circular crop centred on the dish (= world/object origin), feathered rim -> grey outside
    texco = nt.nodes.new('ShaderNodeTexCoord')
    length = nt.nodes.new('ShaderNodeVectorMath'); length.operation = 'LENGTH'
    nt.links.new(texco.outputs['Object'], length.inputs[0])
    ndist = nt.nodes.new('ShaderNodeMath'); ndist.operation = 'DIVIDE'
    nt.links.new(length.outputs['Value'], ndist.inputs[0]); ndist.inputs[1].default_value = r_world
    crop = nt.nodes.new('ShaderNodeMapRange')            # 1 inside dish, ramp to 0 over a thin rim
    crop.inputs['From Min'].default_value = 0.98
    crop.inputs['From Max'].default_value = 1.0
    crop.inputs['To Min'].default_value = 1.0
    crop.inputs['To Max'].default_value = 0.0
    crop.clamp = True
    nt.links.new(ndist.outputs['Value'], crop.inputs['Value'])
    # reveal fade 0 -> 1 across the dissolve window (hidden before HOLD_END, full by DISSOLVE_END)
    reveal = nt.nodes.new('ShaderNodeValue'); reveal.label = 'reveal'
    fac = nt.nodes.new('ShaderNodeMath'); fac.operation = 'MULTIPLY'
    nt.links.new(crop.outputs['Result'], fac.inputs[0])
    nt.links.new(reveal.outputs['Value'], fac.inputs[1])
    trans = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fac.outputs['Value'], mix.inputs['Fac'])
    nt.links.new(trans.outputs['BSDF'], mix.inputs[1])
    nt.links.new(em.outputs['Emission'], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    reveal.outputs['Value'].default_value = 0.0
    reveal.outputs['Value'].keyframe_insert('default_value', frame=HOLD_END)
    reveal.outputs['Value'].default_value = 1.0
    reveal.outputs['Value'].keyframe_insert('default_value', frame=DISSOLVE_END)

    # full-frame quad; UVs map world -> artwork so the plate fills r_world at the origin. The
    # world->UV mapping is affine, so per-corner UVs interpolate exactly across the quad.
    me = bpy.data.meshes.new("revealplane")
    verts = [(-frame_w / 2, -frame_h / 2, 0), (frame_w / 2, -frame_h / 2, 0),
             (frame_w / 2, frame_h / 2, 0), (-frame_w / 2, frame_h / 2, 0)]
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")

    def uvof(wx, wy):
        return ((icx + (wx / r_world) * ir) / (grid - 1), (icy + (wy / r_world) * ir) / (grid - 1))
    corner_uv = {0: uvof(-frame_w / 2, -frame_h / 2), 1: uvof(frame_w / 2, -frame_h / 2),
                 2: uvof(frame_w / 2, frame_h / 2), 3: uvof(-frame_w / 2, frame_h / 2)}
    for i, loop in enumerate(me.loops):
        uvl.data[i].uv = corner_uv[loop.vertex_index]
    me.materials.append(mat)
    obj = bpy.data.objects.new("revealplane", me)
    bpy.context.collection.objects.link(obj)


# ---------------- mould seeding + palette ----------------
def seed_mould(arr, agar_edge, icx, icy, ir, n, rng):
    grid = arr.shape[0]
    yy, xx = np.mgrid[0:grid, 0:grid]
    dist = np.sqrt((xx - icx) ** 2 + (yy - icy) ** 2)
    diff = np.linalg.norm(arr - agar_edge, axis=2)
    # cover the WHOLE plate (agar + mould): a base density everywhere on the disc, boosted on detail
    detail = np.clip(diff / 0.6, 0, 1)
    weight = np.where(dist <= ir * 0.99, 0.5 + 0.6 * detail, 0.0)
    w = weight.reshape(-1)
    w = w / w.sum()
    idx = np.random.choice(grid * grid, size=n, p=w)
    rows, cols = idx // grid, idx % grid
    return rows.astype(float), cols.astype(float), arr[rows, cols]


def quantise(colors, k):
    L = 6
    q = np.clip((colors * L).astype(int), 0, L - 1)
    keys = q[:, 0] * L * L + q[:, 1] * L + q[:, 2]
    uniq, inv, counts = np.unique(keys, return_inverse=True, return_counts=True)
    reps = np.stack([colors[inv == i].mean(axis=0) for i in range(len(uniq))])
    top = np.argsort(counts)[::-1][:k]
    top_reps = reps[top]
    d = ((colors[:, None, :] - top_reps[None, :, :]) ** 2).sum(axis=2)
    return top_reps, d.argmin(axis=1)


# ---------------- fluffy bloom geometry + material ----------------
def smootherstep(p):
    s = p * p * p * (p * (p * 6 - 15) + 10)
    return 0.04 + 0.96 * s


def colony_mesh(name, lobes):
    """One flat mesh of gradient lobe-discs; each disc UV-mapped to the unit circle (centre 0,0)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for (lx, ly, r) in lobes:
        c = bm.verts.new((lx, ly, 0.0))
        rim = []
        for i in range(LOBE_SEG):
            a = 2 * math.pi * i / LOBE_SEG
            ca, sa = math.cos(a), math.sin(a)
            rim.append((bm.verts.new((lx + ca * r, ly + sa * r, 0.0)), ca, sa))
        for i in range(LOBE_SEG):
            v1, c1, s1 = rim[i]
            v2, c2, s2 = rim[(i + 1) % LOBE_SEG]
            f = bm.faces.new((c, v1, v2))
            for loop in f.loops:
                if loop.vert is c:
                    loop[uvl].uv = (0.0, 0.0)
                elif loop.vert is v1:
                    loop[uvl].uv = (c1, s1)
                else:
                    loop[uvl].uv = (c2, s2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def make_fluff_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED'),
                      ('show_transparent_back', False)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    nt = mat.node_tree; nt.nodes.clear()
    texco = nt.nodes.new('ShaderNodeTexCoord')
    grad = nt.nodes.new('ShaderNodeTexGradient'); grad.gradient_type = 'SPHERICAL'
    nt.links.new(texco.outputs['UV'], grad.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0, 0, 0, 1)
    el[1].position = 1.0; el[1].color = (0.92, 0.92, 0.92, 1)   # denser core so blooms fill the dish
    mid = ramp.color_ramp.elements.new(0.34); mid.color = (0.82, 0.82, 0.82, 1)
    nt.links.new(grad.outputs['Fac'], ramp.inputs['Fac'])
    emis = nt.nodes.new('ShaderNodeEmission')
    emis.inputs['Color'].default_value = color
    emis.inputs['Strength'].default_value = 1.0
    trans = nt.nodes.new('ShaderNodeBsdfTransparent')
    # per-bloom opacity: multiply the spherical ramp by THIS object's alpha (obj.color[3], read via
    # Object Info) so the dissolve can fade each bloom to transparent independently, one shared material
    objinfo = nt.nodes.new('ShaderNodeObjectInfo')
    opacity = nt.nodes.new('ShaderNodeMath'); opacity.operation = 'MULTIPLY'
    nt.links.new(ramp.outputs['Color'], opacity.inputs[0])
    nt.links.new(objinfo.outputs['Alpha'], opacity.inputs[1])
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(opacity.outputs['Value'], mix.inputs['Fac'])
    nt.links.new(trans.outputs['BSDF'], mix.inputs[1])
    nt.links.new(emis.outputs['Emission'], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return mat


def build_blooms(seeds_world, swatch_assign, births, deaths, fluff_mats, rng):
    for i, ((wx, wy), sw, birth, death) in enumerate(zip(seeds_world, swatch_assign, births, deaths)):
        diam = rng.uniform(BLOOM_DIAM_MIN, BLOOM_DIAM_MAX)
        lobes = [(0.0, 0.0, diam * 0.34)]
        for _ in range(rng.randint(3, 5)):
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(0.08, 0.24) * diam
            r = rng.uniform(0.09, 0.18) * diam
            lobes.append((math.cos(a) * d, math.sin(a) * d, r))
        me = colony_mesh(f"bloom_{i}", lobes)
        me.materials.append(fluff_mats[int(sw)])
        obj = bpy.data.objects.new(f"bloom_{i}", me)
        obj.location = (wx, wy, 0.01 + 0.05 * (birth / MOULD_END))
        bpy.context.collection.objects.link(obj)
        obj.scale = (0.001, 0.001, 0.001)          # invisible before birth (clean open)
        obj.keyframe_insert('scale', frame=max(1, int(birth)))
        obj.scale = (1.0, 1.0, 1.0)
        obj.keyframe_insert('scale', frame=max(2, int(birth) + BLOOM_GROW))
        # dissolve: scale stays 1 (no more scale keys, so it holds flat through the 1:55->2:15 pause);
        # instead fade THIS bloom's opacity 1->0 (obj.color alpha, read via Object Info in the material)
        obj.color = (1.0, 1.0, 1.0, 1.0)
        obj.keyframe_insert('color', frame=int(death))
        obj.color = (1.0, 1.0, 1.0, 0.0)
        obj.keyframe_insert('color', frame=int(death) + BLOOM_FADE)


# ---------------- scene ----------------
def setup_world(grey):
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree; nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = lin4(grey)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])


def setup_camera():
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ORTHO_SCALE
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (0, 0, 10)
    bpy.context.scene.camera = cam


def setup_render(out_dir, res_pct):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RES_X, RES_Y
    scene.render.resolution_percentage = res_pct
    scene.render.fps = FPS
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.filepath = os.path.join(out_dir, "frame_#####")   # 5-digit pad -> frame_00001..frame_11580
    try:
        scene.view_settings.view_transform = 'Standard'
    except TypeError:
        pass


def encode_mp4(out_dir):
    """Encode the rendered frame_XXXXX.png sequence into an H.264 mp4 (silent, 60fps to match).
    Runs automatically after a full render; needs ffmpeg on PATH (or /opt/homebrew/bin/ffmpeg)."""
    import shutil, subprocess
    ffmpeg = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    if not (shutil.which('ffmpeg') or os.path.exists(ffmpeg)):
        print("ffmpeg not found — skipping mp4 encode; frames are in", out_dir)
        return
    mp4 = os.path.join(out_dir, "haha_reveal.mp4")
    cmd = [ffmpeg, '-y', '-framerate', str(FPS), '-start_number', '1',
           '-i', os.path.join(out_dir, 'frame_%05d.png'),
           '-c:v', 'libx264', '-crf', '12', '-preset', 'veryslow',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4]
    print("encoding mp4:", ' '.join(cmd))
    try:
        subprocess.run(cmd, check=True)
        print("wrote", mp4)
    except (subprocess.CalledProcessError, OSError) as e:
        print("mp4 encode failed:", e, "— frames remain in", out_dir)


def main():
    args = args_after_ddash()
    np.random.seed(42)
    rng = random.Random(42)
    clear_scene()

    frame_w, frame_h = ORTHO_SCALE, ORTHO_SCALE * (RES_Y / RES_X)
    r_world = PLATE_FRAC * frame_h / 2.0

    arr = load_rgb(ART_PATH, IMG_GRID)
    grey, icx, icy, ir = detect_plate(arr)
    agar_edge, agar_core = estimate_agar(arr, icx, icy, ir)
    print(f"plate c=({icx:.0f},{icy:.0f}) r={ir:.0f} agar_edge={np.round(agar_edge,3)}")

    setup_world(grey)
    setup_camera()
    # the real artwork photo sits underneath (z=0), hidden until the dissolve reveals it
    build_reveal_photo(icx, icy, ir, r_world, frame_w, frame_h)

    # image-matched fluffy blooms: accelerating build to full coverage at 1:55, held to 2:15,
    # then dissolved away (accelerating) by 3:01 to reveal the photo underneath
    rows, cols, colors = seed_mould(arr, agar_edge, icx, icy, ir, N_BLOOM, rng)
    reps, assign = quantise(colors, N_SWATCH)
    fluff_mats = [make_fluff_material(f"fluff_{i}", lin4(reps[i])) for i in range(len(reps))]
    seeds_world = [(((c - icx) / ir) * r_world, ((r - icy) / ir) * r_world) for r, c in zip(rows, cols)]
    last_birth = MOULD_END - BLOOM_GROW                  # 6600 — last bloom finishes growing at 6900 (1:55)
    births = [1 + last_birth * (rng.random() ** BLOOM_APPEAR_EXP) for _ in range(len(seeds_world))]
    death_span = (DISSOLVE_END - BLOOM_FADE) - HOLD_END
    deaths = [HOLD_END + death_span * (rng.random() ** BLOOM_APPEAR_EXP) for _ in range(len(seeds_world))]
    build_blooms(seeds_world, assign, births, deaths, fluff_mats, rng)
    print(f"blooms={len(seeds_world)} swatches={len(reps)}")

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = TOTAL_FRAMES
    out_dir = get_output(args)
    os.makedirs(out_dir, exist_ok=True)

    if "--last" in args:
        setup_render(out_dir, 100)
        scene.frame_set(TOTAL_FRAMES)
        scene.render.filepath = os.path.join(out_dir, "last_frame")
        bpy.ops.render.render(write_still=True)
    elif "--preview" in args:
        setup_render(out_dir, 100 if "--fullres" in args else 40)
        for f in (int(round(v)) for v in np.linspace(1, TOTAL_FRAMES - 120, 30)):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out_dir, f"preview_{f:05d}")
            bpy.ops.render.render(write_still=True)
    else:
        setup_render(out_dir, 100)
        bpy.ops.render.render(animation=True)
        encode_mp4(out_dir)        # auto-encode the frame sequence to mp4 when the full render finishes
    print("Done!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Stamp-growth OVERLAY — square, transparent background (Blender headless).

The "ROBOCOBRA QUARTET / 100 / HUNDRED PIECES" stamp draws itself in: veins seed on the letterform
OUTLINE and random-walk INSIDE the letters, tracing them with a continuous ease-in over 5 seconds.
No background (transparent film -> drops into a video editor as an overlay), no blooms. The vein
colour is selectable so the same script makes both the WHITE and the BLACK overlay:

  blender --background --python animations/stamp_overlay.py -- --color white --output DIR   # white stamp
  blender --background --python animations/stamp_overlay.py -- --color black --output DIR   # black stamp
  ... -- --color white --last [--output DIR]                                               # fast spot-check

Timeline (60fps): 5s of growth = 300 frames. Output: 2048x2048 RGBA PNG frames, auto-encoded to a
ProRes 4444 .mov (alpha preserved), named stamp_overlay_<color>.mov.
"""
import bpy, bmesh, sys, os, math, random
import numpy as np

# ---------------- config ----------------
PNG_PATH = "/Users/thib/dev/the100-visual-assets/hundred_pieces_stamp.png"
FPS = 60
DURATION_SEC = 5
TOTAL_FRAMES = DURATION_SEC * FPS          # 300 — 5s of growth

# stamp reveal — draws in continuously over the 5s
REVEAL_FRAMES = 240                        # births spread over the first ~4s (accelerating)
STAMP_GROW = 60                            # frames a filament takes to draw in (~1s)
STAMP_EASE = 0.40                          # birth = REVEAL*rand**EASE => accelerating density
STAMP_BUCKET = 15                          # fine time-bucket (<< STAMP_GROW => continuous, no pauses)

# vein colours (chosen by --color); white or black stamp on transparent
COLOR_HEX = {"white": "#ffffff", "black": "#000000"}

LOBE_SEG = 22                                 # (unused here; kept for the shared colony_mesh helper)

RES_X, RES_Y = 2048, 2048                     # square overlay
OUTPUT_DIR = "/tmp/stamp_overlay"

GRID = 480
ALPHA_THRESH = 0.35
FIL_CAP = 3200
STAMP_HEIGHT_FRAC = 0.70
ORTHO_SCALE = 10.0
BEVEL = 0.013


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(hexstr):
    h = hexstr.lstrip('#')
    return tuple(srgb_to_linear(int(h[i:i+2], 16) / 255.0) for i in (0, 2, 4)) + (1.0,)


def args_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get_output(args):
    if "--output" in args:
        i = args.index("--output")
        if i + 1 < len(args):
            return args[i + 1]
    return OUTPUT_DIR


def get_color(args):
    """--color white|black (default white). Returns (name, hex)."""
    name = "white"
    if "--color" in args:
        i = args.index("--color")
        if i + 1 < len(args) and args[i + 1] in COLOR_HEX:
            name = args[i + 1]
    return name, COLOR_HEX[name]


def clear_scene():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.curves,
                 bpy.data.materials, bpy.data.cameras, bpy.data.images):
        for item in list(coll):
            coll.remove(item)


# ---------------- stamp mask + vein simulation ----------------
def load_mask():
    img = bpy.data.images.load(PNG_PATH)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    alpha = buf.reshape(h, w, 4)[:, :, 3]          # row 0 = bottom -> world Y upright
    rows = np.linspace(0, h - 1, GRID).astype(int)
    cols = np.linspace(0, w - 1, GRID).astype(int)
    mask = alpha[np.ix_(rows, cols)] > ALPHA_THRESH
    bpy.data.images.remove(img)
    ys, xs = np.where(mask)
    return mask, (xs.min(), ys.min(), xs.max(), ys.max())


def edge_points(mask):
    up = np.zeros_like(mask); up[:-1, :] = mask[1:, :]
    dn = np.zeros_like(mask); dn[1:, :] = mask[:-1, :]
    lf = np.zeros_like(mask); lf[:, :-1] = mask[:, 1:]
    rt = np.zeros_like(mask); rt[:, 1:] = mask[:, :-1]
    edge = mask & ~(up & dn & lf & rt)
    ys, xs = np.where(edge)
    return list(zip(xs.tolist(), ys.tolist()))


def simulate_stamp(mask, edges, n_fil, rng):
    H, W = mask.shape

    def inmask(x, y):
        xi, yi = int(x), int(y)
        return 0 <= xi < W and 0 <= yi < H and mask[yi, xi]

    fils = []
    if not edges:
        return fils
    for _ in range(n_fil):
        ex, ey = edges[rng.randrange(len(edges))]
        ang = rng.uniform(0, 2 * math.pi)
        x, y = float(ex), float(ey)
        pts = [(x, y)]
        for _ in range(rng.randint(16, 46)):
            ang += rng.uniform(-0.62, 0.62)
            step = rng.uniform(0.9, 1.7)
            nx, ny = x + math.cos(ang) * step, y + math.sin(ang) * step
            if inmask(nx, ny):
                x, y = nx, ny
                pts.append((x, y))
            else:
                ang = rng.uniform(0, 2 * math.pi)
        if len(pts) >= 2:
            fils.append(pts)
    return fils


# ---------------- blooms (soft fluffy blob colonies) ----------------
def make_blooms(stamp_half, frame_w, frame_h, rng):
    """Each colony: (cx, cy, diam, lobes[(lx,ly,r)...], hex_colour, birth). Lobes are local to centre."""
    hx, hy = stamp_half
    out = []
    for _ in range(N_BLOOMS):
        diam = rng.uniform(BLOOM_DIAM_MIN, BLOOM_DIAM_MAX)
        reach = diam * 0.5
        mx, my = hx * 1.05 + reach, hy * 1.05 + reach     # square no-go + colony reach
        cx = cy = None
        for _try in range(40):
            xp = rng.uniform(-frame_w / 2, frame_w / 2)
            yp = rng.uniform(-frame_h / 2, frame_h / 2)
            if abs(xp) > mx or abs(yp) > my:
                cx, cy = xp, yp
                break
        if cx is None:
            continue
        lobes = [(0.0, 0.0, diam * 0.30)]                 # main lobe
        for _i in range(rng.randint(4, 7)):               # offset lobes -> lumpy silhouette
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(0.10, 0.28) * diam
            r = rng.uniform(0.09, 0.19) * diam
            lobes.append((math.cos(a) * d, math.sin(a) * d, r))
        col = rng.choice(WHITES) if rng.random() < 0.5 else rng.choice(DARKS)
        birth = rng.uniform(1, TOTAL_FRAMES - BLOOM_GROW)
        out.append((cx, cy, diam, lobes, col, birth))
    return out


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


def build_blooms(bloom_specs, fluff_mats):
    for i, (cx, cy, diam, lobes, col, birth) in enumerate(bloom_specs):
        me = colony_mesh(f"colony_{i}", lobes)
        me.materials.append(fluff_mats[col])
        obj = bpy.data.objects.new(f"colony_{i}", me)
        # tiny per-colony z so later colonies composite over earlier ones (ortho: z = draw order)
        obj.location = (cx, cy, 0.002 * (birth / TOTAL_FRAMES))
        bpy.context.collection.objects.link(obj)
        s0, s1 = smootherstep(0.0), 1.0                   # grow from a point over the colony's window
        obj.scale = (s0, s0, s0)
        obj.keyframe_insert('scale', frame=max(1, int(birth)))
        obj.scale = (s1, s1, s1)
        obj.keyframe_insert('scale', frame=max(2, int(birth) + BLOOM_GROW))


# ---------------- materials ----------------
def make_emission_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = color
    em.inputs['Strength'].default_value = 1.0
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def make_fluff_material(name, color):
    """Radial-gradient soft blob: opaque-ish emission core -> transparent edge (shows the orange)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED'),
                      ('show_transparent_back', False)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    nt = mat.node_tree
    nt.nodes.clear()
    texco = nt.nodes.new('ShaderNodeTexCoord')
    grad = nt.nodes.new('ShaderNodeTexGradient')
    grad.gradient_type = 'SPHERICAL'                       # 1 at UV centre -> 0 at rim
    nt.links.new(texco.outputs['UV'], grad.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')              # shape the soft falloff (=> alpha)
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0, 0, 0, 1)        # rim -> transparent
    el[1].position = 1.0; el[1].color = (0.85, 0.85, 0.85, 1)   # centre -> ~0.85 opaque (soft)
    mid = ramp.color_ramp.elements.new(0.38); mid.color = (0.75, 0.75, 0.75, 1)
    nt.links.new(grad.outputs['Fac'], ramp.inputs['Fac'])
    emis = nt.nodes.new('ShaderNodeEmission')
    emis.inputs['Color'].default_value = color
    emis.inputs['Strength'].default_value = 1.0
    trans = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(ramp.outputs['Color'], mix.inputs['Fac'])
    nt.links.new(trans.outputs['BSDF'], mix.inputs[1])
    nt.links.new(emis.outputs['Emission'], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return mat


# ---------------- stamp geometry ----------------
def taper_radii(n):
    return [1.0 - 0.78 * (i / (n - 1)) for i in range(n)] if n > 1 else [1.0]


def make_wave_object(name, fils, start_frame, grow_frames, mat, bevel):
    """fils: list of (points[(x,y)...], radii[...]); one curve object grown 0->1 over its window."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = bevel
    cu.bevel_resolution = 1
    cu.use_fill_caps = True
    for pts, radii in fils:
        n = len(pts)
        sp = cu.splines.new('POLY')
        sp.points.add(n - 1)
        coords = []
        for (x, y) in pts:
            coords += [x, y, 0.0, 1.0]
        sp.points.foreach_set('co', coords)
        sp.points.foreach_set('radius', radii)
    cu.materials.append(mat)
    obj = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(obj)
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert('bevel_factor_end', frame=max(1, int(start_frame)))
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert('bevel_factor_end', frame=max(2, int(start_frame) + grow_frames))


def build_stamp(fils_grid, to_world, mat, rng):
    # continuous ease-in births + fine buckets => always-something-drawing, legible ~halfway
    buckets = {}
    for grid_pts in fils_grid:
        birth = REVEAL_FRAMES * (rng.random() ** STAMP_EASE)
        buckets.setdefault(int(birth / STAMP_BUCKET), []).append(grid_pts)
    for wv, bucket in buckets.items():
        fils = [([to_world(c, r) for (c, r) in gp], taper_radii(len(gp))) for gp in bucket]
        make_wave_object(f"stamp_{wv}", fils, 1 + wv * STAMP_BUCKET, STAMP_GROW, mat, BEVEL)


def world_mapping(bbox):
    minc, minr, maxc, maxr = bbox
    cx, cy = (minc + maxc) / 2.0, (minr + maxr) / 2.0
    frame_w, frame_h = ORTHO_SCALE, ORTHO_SCALE * (RES_Y / RES_X)
    scale = (STAMP_HEIGHT_FRAC * frame_h) / max(1, (maxr - minr))

    def to_world(col, row):
        return ((col - cx) * scale, (row - cy) * scale)

    stamp_half = ((maxc - minc) * scale / 2.0, (maxr - minr) * scale / 2.0)
    return to_world, stamp_half, frame_w, frame_h


# ---------------- scene ----------------
def setup_world():
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = DEEP_ORANGE
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])


def setup_camera():
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'HORIZONTAL'   # ortho_scale maps to width (square: width==height anyway)
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
    scene.render.film_transparent = True                # transparent background for overlay use
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.filepath = os.path.join(out_dir, "frame_#####")   # 5-digit pad -> frame_00001..


def encode_mov(out_dir, color_name):
    """Encode the RGBA frame sequence into a ProRes 4444 .mov that PRESERVES ALPHA (transparent
    background), silent, 60fps. ProRes 4444 is the standard alpha-overlay master codec; H.264/mp4
    cannot carry alpha. Needs ffmpeg on PATH (or /opt/homebrew/bin/ffmpeg)."""
    import shutil, subprocess
    ffmpeg = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    if not (shutil.which('ffmpeg') or os.path.exists(ffmpeg)):
        print("ffmpeg not found — skipping mov encode; RGBA frames are in", out_dir)
        return
    mov = os.path.join(out_dir, f"stamp_overlay_{color_name}.mov")
    cmd = [ffmpeg, '-y', '-framerate', str(FPS), '-start_number', '1',
           '-i', os.path.join(out_dir, 'frame_%05d.png'),
           '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le',
           '-movflags', '+faststart', mov]
    print("encoding mov (ProRes 4444, alpha):", ' '.join(cmd))
    try:
        subprocess.run(cmd, check=True)
        print("wrote", mov)
    except (subprocess.CalledProcessError, OSError) as e:
        print("mov encode failed:", e, "— RGBA frames remain in", out_dir)


def main():
    args = args_after_ddash()
    color_name, color_hex = get_color(args)
    clear_scene()
    setup_camera()
    # NOTE: no setup_world — the film is transparent (overlay); no blooms — just the stamp veins.

    mask, bbox = load_mask()
    to_world, stamp_half, frame_w, frame_h = world_mapping(bbox)
    rng = random.Random(42)

    edges = edge_points(mask)
    n_fil = min(FIL_CAP, max(400, len(edges) * 3))
    stamp_fils = simulate_stamp(mask, edges, n_fil, rng)
    print(f"color={color_name} edges={len(edges)} stamp_fils={len(stamp_fils)}")

    vein_mat = make_emission_material("Vein", hex_lin(color_hex))
    build_stamp(stamp_fils, to_world, vein_mat, rng)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = TOTAL_FRAMES
    out_dir = get_output(args)
    os.makedirs(out_dir, exist_ok=True)

    if "--last" in args:                                    # fast full-res spot-check of the final frame
        setup_render(out_dir, 100)
        scene.frame_set(TOTAL_FRAMES)
        scene.render.filepath = os.path.join(out_dir, "last_frame")
        bpy.ops.render.render(write_still=True)
    elif "--preview" in args:
        setup_render(out_dir, 100 if "--fullres" in args else 40)
        for f in (TOTAL_FRAMES // 3, 2 * TOTAL_FRAMES // 3, TOTAL_FRAMES):   # early / mid / full
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out_dir, f"preview_{f:05d}")
            bpy.ops.render.render(write_still=True)
    else:
        setup_render(out_dir, 100)
        bpy.ops.render.render(animation=True)
        encode_mov(out_dir, color_name)     # auto-encode the RGBA frames to a ProRes 4444 .mov (alpha)
    print("Done!")


if __name__ == "__main__":
    main()

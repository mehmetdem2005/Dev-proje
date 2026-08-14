"""Render a GLB from a few angles so an asset can actually be looked at.

    blender -b --python preview.py -- <file.glb> <out.png> [--mode grid|top] [--res 640]

Used as the verification step of the pipeline: every generator run should be
followed by a look at what it produced, not just a triangle count.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def scene_bounds():
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    found = False
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        found = True
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            lo = Vector((min(lo[i], world[i]) for i in range(3)))
            hi = Vector((max(hi[i], world[i]) for i in range(3)))
    if not found:
        return Vector((0, 0, 0)), Vector((1, 1, 1))
    return lo, hi


def apply_clay():
    """Replace every material with neutral clay.

    Re-imported GLBs come back with the glTF baseColor * COLOR_0 multiply
    baked into the node tree, so a terrain carrying a splat mask renders as
    red/green/blue mush. Clay strips the colour question out and lets the
    form be judged on its own.
    """
    clay = bpy.data.materials.new("clay")
    clay.use_nodes = True
    bsdf = clay.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.55, 0.53, 0.5, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.75
    bsdf.inputs["Metallic"].default_value = 0.0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        obj.data.materials.clear()
        obj.data.materials.append(clay)


def setup_world(strength=0.6):
    world = bpy.data.worlds.new("preview")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs[0].default_value = (0.42, 0.52, 0.68, 1.0)
    background.inputs[1].default_value = strength


def add_sun(rotation=(math.radians(52), 0.0, math.radians(38)), energy=4.0):
    light = bpy.data.lights.new("sun", type="SUN")
    light.energy = energy
    light.angle = math.radians(2.0)
    obj = bpy.data.objects.new("sun", light)
    obj.rotation_euler = rotation
    bpy.context.collection.objects.link(obj)
    return obj


def place_camera(centre, radius, azimuth_deg, elevation_deg, ortho=False):
    camera_data = bpy.data.cameras.new("cam")
    if ortho:
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = radius * 2.15
    else:
        camera_data.lens = 42.0
    camera = bpy.data.objects.new("cam", camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera

    azimuth = math.radians(azimuth_deg)
    elevation = math.radians(elevation_deg)
    distance = radius * (1.15 if ortho else 2.35)
    camera.location = centre + Vector((
        math.cos(azimuth) * math.cos(elevation) * distance,
        math.sin(azimuth) * math.cos(elevation) * distance,
        math.sin(elevation) * distance,
    ))
    direction = (centre - camera.location).normalized()
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return camera


def render(path, res, samples=24):
    scene = bpy.context.scene
    # Cycles on CPU, not EEVEE: this container has no EGL/GPU context, and
    # EEVEE cannot initialise without one.
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 4
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        print("usage: preview.py -- <file.glb> <out.png> [--mode grid|top] [--res N]")
        return

    source, out = argv[0], argv[1]
    mode = argv[argv.index("--mode") + 1] if "--mode" in argv else "grid"
    res = int(argv[argv.index("--res") + 1]) if "--res" in argv else 640
    clay = "--clay" in argv
    only = argv[argv.index("--only") + 1] if "--only" in argv else None

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=source)

    if only:
        for obj in list(bpy.context.scene.objects):
            if obj.type == "MESH" and only not in obj.name:
                bpy.data.objects.remove(obj, do_unlink=True)

    lo, hi = scene_bounds()
    centre = (lo + hi) * 0.5
    radius = max((hi - lo).length * 0.5, 0.5)

    if clay:
        apply_clay()

    setup_world()
    add_sun()

    views = {
        "grid": [(35, 24), (125, 18), (215, 30), (305, 20)],
        "top": [(0, 89)],
        "hero": [(40, 16)],
        "ridge": [(30, 12), (140, 22)],
    }[mode]

    base, ext = os.path.splitext(out)
    written = []
    for index, (azimuth, elevation) in enumerate(views):
        for camera in [o for o in bpy.context.scene.objects if o.type == "CAMERA"]:
            bpy.data.objects.remove(camera, do_unlink=True)
        place_camera(centre, radius, azimuth, elevation, ortho=(mode == "top"))
        path = out if len(views) == 1 else f"{base}_{index}{ext}"
        render(path, res)
        written.append(path)

    print("PREVIEW:" + ",".join(written))
    print(f"  bounds {tuple(round(v, 2) for v in lo)} .. {tuple(round(v, 2) for v in hi)}")


if __name__ == "__main__":
    main()

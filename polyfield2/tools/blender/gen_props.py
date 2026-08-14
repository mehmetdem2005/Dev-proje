"""Generate objective dressing props.

    blender -b --python gen_props.py

Supply crates, fuel barrels, ammo boxes and the capture mast that marks each
zone. Everything sits with its origin on the ground plane so the layout can
drop it straight onto a sampled terrain height.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Vector

import pf_lib as pf
from gen_fortifications import _bevelled_box


def _ground(obj):
    """Move an object so its lowest point sits at Z = 0, then bake it in."""
    lowest = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    obj.location.z -= lowest
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def make_crate(name="crate", seed=9100):
    """Supply crate: a box with corner battens and a painted band."""
    body = (0.70, 0.70, 0.55)
    parts = [_bevelled_box(f"{name}_body", body, bevel=0.02)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            batten = _bevelled_box(f"{name}_batten_{sx}_{sy}", (0.08, 0.08, body[2]), bevel=0.008)
            batten.location = (sx * body[0] * 0.46, sy * body[1] * 0.46, 0.0)
            parts.append(batten)
    for sz in (-1, 1):
        rail = _bevelled_box(f"{name}_rail_{sz}", (body[0] * 1.04, body[1] * 1.04, 0.05),
                             bevel=0.008)
        rail.location = (0.0, 0.0, sz * (body[2] * 0.5 - 0.03))
        parts.append(rail)

    obj = pf.join_objects(parts, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=0.85)
    pf.set_material(obj, "crate_wood")
    return _ground(obj)


def make_barrel(name="barrel", seed=9200):
    """Fuel barrel: 10-sided drum with two rolling hoops."""
    parts = [pf.make_cylinder(f"{name}_body", radius=0.29, depth=0.86, segments=10)]
    for level in (-0.22, 0.22):
        hoop = pf.make_cylinder(f"{name}_hoop_{level}", radius=0.312, depth=0.06, segments=10)
        hoop.location.z = level
        parts.append(hoop)
    cap = pf.make_cylinder(f"{name}_cap", radius=0.075, depth=0.03, segments=6)
    cap.location = (0.13, 0.0, 0.44)
    parts.append(cap)

    obj = pf.join_objects(parts, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_smooth(obj, angle_deg=42.0)
    pf.apply_modifiers(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=0.8)
    pf.set_material(obj, "metal_corrugated")
    return _ground(obj)


def make_ammo_box(name="ammo_box", seed=9300):
    """Steel ammunition box with a folded lid and a carry handle."""
    body = (0.34, 0.18, 0.14)
    parts = [_bevelled_box(f"{name}_body", body, bevel=0.014)]
    lid = _bevelled_box(f"{name}_lid", (body[0] * 1.03, body[1] * 1.05, 0.03), bevel=0.008)
    lid.location.z = body[2] * 0.5 + 0.015
    parts.append(lid)
    handle = _bevelled_box(f"{name}_handle", (0.13, 0.022, 0.018), bevel=0.005)
    handle.location = (0.0, 0.0, body[2] * 0.5 + 0.085)
    parts.append(handle)
    for sx in (-1, 1):
        post = _bevelled_box(f"{name}_post_{sx}", (0.02, 0.022, 0.055), bevel=0.004)
        post.location = (sx * 0.055, 0.0, body[2] * 0.5 + 0.05)
        parts.append(post)

    obj = pf.join_objects(parts, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=0.5)
    pf.set_material(obj, "metal_corrugated")
    return _ground(obj)


def make_capture_mast(name="capture_mast", seed=9400):
    """Zone marker: sandbagged base, mast, cross-spar and banner.

    Deliberately tall and thin — it has to be identifiable from anywhere on
    the ridge, which is a silhouette job, not a texture job.
    """
    parts = []
    base = pf.make_cylinder(f"{name}_base", radius=0.42, depth=0.18, segments=8)
    base.location.z = 0.09
    parts.append(base)

    mast = pf.make_cylinder(f"{name}_mast", radius=0.055, depth=4.2, segments=6)
    mast.location.z = 2.2
    parts.append(mast)

    spar = pf.make_cylinder(f"{name}_spar", radius=0.035, depth=0.9, segments=6)
    spar.rotation_euler = Euler((0.0, math.pi * 0.5, 0.0))
    spar.location = (0.42, 0.0, 4.0)
    parts.append(spar)

    for index, height in enumerate((1.1, 2.4)):
        rung = pf.make_cylinder(f"{name}_rung_{index}", radius=0.022, depth=0.36, segments=4)
        rung.rotation_euler = Euler((math.pi * 0.5, 0.0, 0.0))
        rung.location = (0.0, 0.0, height)
        parts.append(rung)

    metal = pf.join_objects(parts, f"{name}_metal")
    pf.select_only(metal)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(metal)
    pf.triangulate(metal)
    pf.box_project_uv(metal, scale=0.6)
    pf.set_material(metal, "metal_corrugated")
    _ground(metal)

    # Banner as a separate mesh so Godot can recolour it per owning team.
    bm = bmesh.new()
    width, drop, segments = 0.86, 0.62, 5
    verts = []
    for row in range(2):
        for index in range(segments + 1):
            t = index / segments
            wave = math.sin(t * math.pi * 1.6) * 0.05
            verts.append(bm.verts.new((0.06 + t * width, wave, 4.0 - row * drop - t * 0.06)))
    bm.verts.ensure_lookup_table()
    for index in range(segments):
        bm.faces.new((verts[index], verts[index + 1],
                      verts[segments + 1 + index + 1], verts[segments + 1 + index]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    banner = pf.bm_to_object(bm, f"{name}_banner")
    pf.shade_flat(banner)
    pf.triangulate(banner)
    pf.box_project_uv(banner, scale=1.0)
    pf.set_material(banner, "sandbag_burlap")

    return [metal, banner]


def main():
    pf.reset_scene()
    pf.report("Props")

    groups = {
        "crate": [make_crate()],
        "barrel": [make_barrel()],
        "ammo_box": [make_ammo_box()],
        "capture_mast": make_capture_mast(),
    }

    exported = []
    for offset, (name, objects) in enumerate(groups.items()):
        total = sum(pf.tri_count(o) for o in objects)
        print(f"  {name:<16} {total:5d} tris  ({len(objects)} mesh)")
        for obj in objects:
            obj.location.x += offset * 2.5
        exported.extend(objects)

    path = os.path.join(pf.MODEL_DIR, "props.glb")
    pf.export_glb(exported, path)


if __name__ == "__main__":
    main()

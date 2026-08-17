"""Generate trench and cover modules.

    blender -b --python gen_fortifications.py

The terrain carves the channel; these pieces stand in it and supply the
revetment, firing step, duckboards and sandbag cover that make a trench read
as a built position rather than a ditch.
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
import layout

TRENCH_LENGTH = 4.0
TRENCH_DEPTH = 2.6
TRENCH_FLOOR_WIDTH = 2.0


def _bevelled_box(name, size, bevel=0.06, segments=1, seed=None, jitter=0.0):
    """Box of the given FULL dimensions (not half-extents), centred on origin."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=bevel,
                        segments=segments, affect="EDGES", profile=0.5)
    if jitter > 0.0 and seed is not None:
        generator = np.random.default_rng(seed)
        for vert in bm.verts:
            vert.co += Vector(generator.normal(0.0, jitter, 3))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return pf.bm_to_object(bm, name)


def make_sandbag(name, seed, size=(0.52, 0.30, 0.20)):
    """One filled bag: a squashed, bevelled box with a slump on top.

    A single bevel segment, not two. Bags are the most-repeated object on the
    map — 47 emplacements plus every trench parapet — so the difference
    between 44 and 139 triangles a bag decides whether the fortifications fit
    in the frame budget at all.
    """
    obj = _bevelled_box(name, size, bevel=0.07, segments=1, seed=seed, jitter=0.012)
    mesh = obj.data
    generator = np.random.default_rng(seed + 3)
    for vert in mesh.vertices:
        # Bags sag: the top face droops in the middle, the sides bulge out.
        sag = (1.0 - abs(vert.co.x) / (size[0] * 0.6)) * (1.0 - abs(vert.co.y) / (size[1] * 0.6))
        sag = max(0.0, sag)
        if vert.co.z > 0:
            vert.co.z -= sag * size[2] * 0.22
        vert.co.x *= 1.0 + sag * 0.06
        vert.co.y *= 1.0 + sag * 0.10
        vert.co += Vector(generator.normal(0.0, 0.006, 3))
    mesh.update()
    return obj


def _stack_bags(prefix, rows, per_row, seed, stagger=0.5, curve=0.0):
    """Build a course-laid sandbag wall and return the bag objects."""
    generator = np.random.default_rng(seed)
    bags = []
    bag_size = (0.52, 0.30, 0.20)
    for row in range(rows):
        count = per_row - (row // 2)
        if count < 1:
            break
        offset = (row % 2) * stagger * bag_size[0]
        for index in range(count):
            x = (index - (count - 1) * 0.5) * bag_size[0] * 1.02 + offset
            bag = make_sandbag(f"{prefix}_{row}_{index}", seed + row * 17 + index * 5, bag_size)
            bag.location = (
                x,
                math.sin(x * curve) * 0.25 + generator.normal(0.0, 0.015),
                bag_size[2] * (row + 0.5) * 0.94,
            )
            bag.rotation_euler = Euler((
                generator.normal(0.0, 0.05),
                generator.normal(0.0, 0.04),
                generator.normal(0.0, 0.07),
            ))
            bags.append(bag)
    return bags


def make_sandbag_wall(name="sandbag_wall", seed=8100):
    bags = _stack_bags(name, rows=4, per_row=5, seed=seed, curve=0.35)
    obj = pf.join_objects(bags, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=0.6)
    pf.set_material(obj, "sandbag_burlap")
    return obj


def make_sandbag_stack(name="sandbag_stack", seed=8200):
    bags = _stack_bags(name, rows=3, per_row=3, seed=seed, stagger=0.4)
    obj = pf.join_objects(bags, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=0.6)
    pf.set_material(obj, "sandbag_burlap")
    return obj


def make_trench_section(name="trench_straight", seed=8300):
    """A 4 m revetted trench bay.

    Origin sits at ground level on the trench centreline, so the module drops
    straight onto the layout polyline: everything below Z=0 is inside the
    carved channel, the parapet bags sit above it.
    """
    generator = np.random.default_rng(seed)
    half_width = TRENCH_FLOOR_WIDTH * 0.5
    parts = []

    # Revetment: one strip mesh per side, with per-plank depth offsets that
    # read as separate boards. Modelling 30 individual bevelled planks looked
    # identical and cost twenty times the triangles.
    # 0.26 m planks gave a 4 m bay 15 columns a side. The board joints are read
    # from the bark texture, not the silhouette, and this module is repeated 114
    # times — it was the single heaviest thing on the map at 756 triangles.
    plank_width = 0.40
    count = int(TRENCH_LENGTH / plank_width)
    for side in (-1, 1):
        bm = bmesh.new()
        columns = []
        for index in range(count + 1):
            y = (index - count * 0.5) * plank_width
            depth = generator.uniform(0.0, 0.035) + (index % 2) * 0.02
            x = side * (half_width + 0.03 + depth)
            top = generator.uniform(-0.06, 0.02)
            columns.append((bm.verts.new((x, y, -TRENCH_DEPTH)),
                            bm.verts.new((x, y, top))))
        bm.verts.ensure_lookup_table()
        for index in range(count):
            low_a, high_a = columns[index]
            low_b, high_b = columns[index + 1]
            face = bm.faces.new((low_a, low_b, high_b, high_a))
            if side < 0:
                face.normal_flip()
        bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=0.05)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        parts.append(pf.bm_to_object(bm, f"{name}_revet_{side}"))

    # Waling: two horizontal beams holding the revetment back.
    for side in (-1, 1):
        for level in (-0.55, -1.9):
            beam = _bevelled_box(f"{name}_wale_{side}_{level}",
                                 (0.06, TRENCH_LENGTH, 0.07), bevel=0.015)
            beam.location = (side * (half_width - 0.03), 0.0, level)
            parts.append(beam)

    # Duckboard floor: slats on two bearers.
    # Duckboards sit at the bottom of a 2.6 m channel. Nobody counts the slats
    # from outside the trench, and inside it half as many still reads as a floor.
    slat_count = int(TRENCH_LENGTH / 0.55)
    for index in range(slat_count):
        y = (index - (slat_count - 1) * 0.5) * 0.30
        slat = _bevelled_box(f"{name}_slat_{index}",
                             (TRENCH_FLOOR_WIDTH * 0.92, 0.075, 0.025), bevel=0.0)
        slat.location = (0.0, y, -TRENCH_DEPTH + 0.06)
        parts.append(slat)
    for side in (-1, 1):
        bearer = _bevelled_box(f"{name}_bearer_{side}",
                               (0.05, TRENCH_LENGTH, 0.035), bevel=0.008)
        bearer.location = (side * half_width * 0.6, 0.0, -TRENCH_DEPTH + 0.02)
        parts.append(bearer)

    # Firing step on the parapet side.
    step = _bevelled_box(f"{name}_step", (0.56, TRENCH_LENGTH, 0.22), bevel=0.02)
    step.location = (-half_width + 0.28, 0.0, -TRENCH_DEPTH + 0.22)
    parts.append(step)
    step_face = _bevelled_box(f"{name}_step_face", (0.08, TRENCH_LENGTH, 0.24), bevel=0.01)
    step_face.location = (-half_width + 0.56, 0.0, -TRENCH_DEPTH + 0.24)
    parts.append(step_face)

    timber = pf.join_objects(parts, f"{name}_timber")
    pf.select_only(timber)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(timber)
    pf.triangulate(timber)
    pf.box_project_uv(timber, scale=1.1)
    pf.set_material(timber, "wood_plank")

    # Parapet sandbags along the forward lip.
    bags = []
    bag_size = (0.52, 0.30, 0.20)
    per_row = int(TRENCH_LENGTH / (bag_size[0] * 1.02)) + 1
    for row in range(1):
        for index in range(per_row - row):
            y = (index - (per_row - row - 1) * 0.5) * bag_size[0] * 1.02
            bag = make_sandbag(f"{name}_bag_{row}_{index}", seed + 500 + row * 31 + index)
            bag.rotation_euler = Euler((0.0, 0.0, math.pi * 0.5 + generator.normal(0.0, 0.06)))
            bag.location = (-half_width - 0.22 - row * 0.05, y,
                            bag_size[2] * (row + 0.5) * 0.94 + 0.02)
            bags.append(bag)
    sandbags = pf.join_objects(bags, f"{name}_bags")
    pf.select_only(sandbags)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(sandbags)
    pf.triangulate(sandbags)
    pf.box_project_uv(sandbags, scale=0.6)
    pf.set_material(sandbags, "sandbag_burlap")

    return [timber, sandbags]


def make_hedgehog(name="barrier_hedgehog", seed=8400):
    """Anti-vehicle obstacle: three crossed steel angles."""
    parts = []
    for index, rotation in enumerate(((0.9, 0.0, 0.0), (0.0, 0.9, 0.6), (0.55, -0.6, -0.7))):
        beam = _bevelled_box(f"{name}_{index}", (0.06, 0.06, 0.85), bevel=0.012)
        beam.rotation_euler = Euler(rotation)
        parts.append(beam)
    obj = pf.join_objects(parts, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.location.z = 0.72
    bpy.ops.object.transform_apply(location=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=0.9)
    pf.set_material(obj, "metal_corrugated")
    return obj


def make_dugout_roof(name="dugout_roof", seed=8500):
    """Corrugated shelter roof spanning a trench bay."""
    bm = bmesh.new()
    segments = 9
    width, length = 2.6, 2.2
    verts = []
    for row in range(2):
        for index in range(segments + 1):
            t = index / segments
            x = (t - 0.5) * width
            z = math.sin(t * math.pi) * 0.42 + (index % 2) * 0.035
            verts.append(bm.verts.new((x, (row - 0.5) * length, z)))
    bm.verts.ensure_lookup_table()
    for index in range(segments):
        a = verts[index]
        b = verts[index + 1]
        c = verts[segments + 1 + index + 1]
        d = verts[segments + 1 + index]
        bm.faces.new((a, b, c, d))
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=-0.04)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = pf.bm_to_object(bm, name)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=1.0)
    pf.set_material(obj, "metal_corrugated")
    return obj


def main():
    pf.reset_scene()
    pf.report("Fortifications")

    groups = {}
    groups["trench_straight"] = make_trench_section()
    groups["sandbag_wall"] = [make_sandbag_wall()]
    groups["sandbag_stack"] = [make_sandbag_stack()]
    groups["barrier_hedgehog"] = [make_hedgehog()]
    groups["dugout_roof"] = [make_dugout_roof()]

    exported = []
    for offset, (name, objects) in enumerate(groups.items()):
        total = sum(pf.tri_count(o) for o in objects)
        print(f"  {name:<20} {total:5d} tris  ({len(objects)} mesh)")
        for obj in objects:
            obj.location.x += offset * 6.0
        exported.extend(objects)

    path = os.path.join(pf.MODEL_DIR, "fortifications.glb")
    pf.export_glb(exported, path)


if __name__ == "__main__":
    main()

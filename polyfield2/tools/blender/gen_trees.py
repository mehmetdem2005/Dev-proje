"""Generate trees, bushes and grass tufts.

    blender -b --python gen_trees.py

Trunks and branches are real geometry (tapered, forked, leaning); foliage is
alpha-cut cards clustered at the branch ends. That combination is what reads
as a tree on a phone — a billboard alone looks like cardboard from the side,
and modelled leaves cost far too much.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

import pf_lib as pf


def _branch(bm, base, direction, length, radius_start, radius_end, sides=6):
    """Add one tapered limb; returns the tip position and its frame."""
    direction = Vector(direction).normalized()
    tip = Vector(base) + direction * length
    rotation = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()

    rings = []
    for level, radius in ((0.0, radius_start), (1.0, radius_end)):
        ring = []
        for index in range(sides):
            angle = (index / sides) * math.tau
            local = Vector((math.cos(angle) * radius, math.sin(angle) * radius, level * length))
            ring.append(bm.verts.new(Vector(base) + rotation @ local))
        rings.append(ring)
    for index in range(sides):
        nxt = (index + 1) % sides
        bm.faces.new((rings[0][index], rings[0][nxt], rings[1][nxt], rings[1][index]))
    return tip


def _grow(bm, base, direction, length, radius, depth, generator, leaves, sides=6):
    """Recursively grow a limb and record where foliage should hang."""
    end_radius = radius * generator.uniform(0.58, 0.72)
    tip = _branch(bm, base, direction, length, radius, end_radius, sides)

    if depth <= 1:
        # Foliage hangs off the outer two levels, not just the final tips —
        # tip-only clusters leave a bare, spidery crown.
        leaves.append((tip, Vector(direction).normalized(), max(end_radius, 0.02)))
    if depth <= 0 or end_radius < 0.035:
        return

    forks = 2 if depth > 1 else generator.integers(2, 4)
    for index in range(int(forks)):
        # Each child leans away from the parent and twists around it, which is
        # what stops a procedural tree from looking like a candelabra.
        lean = generator.uniform(0.42, 0.85)
        twist = (index / float(forks)) * math.tau + generator.uniform(-0.4, 0.4)
        axis = Vector((math.cos(twist), math.sin(twist), 0.0))
        child_dir = (Vector(direction).normalized() + axis * lean).normalized()
        child_dir.z += generator.uniform(-0.05, 0.18)
        _grow(bm, tip, child_dir.normalized(), length * generator.uniform(0.58, 0.76),
              end_radius, depth - 1, generator, leaves, max(4, sides - 1))


def make_tree(name, seed, height=7.0, trunk_radius=0.24, depth=3, leaf_scale=1.0):
    generator = np.random.default_rng(seed)

    bm = bmesh.new()
    leaves: list = []
    lean = Vector((generator.uniform(-0.10, 0.10), generator.uniform(-0.10, 0.10), 1.0))
    _grow(bm, Vector((0, 0, 0)), lean.normalized(), height * 0.42,
          trunk_radius, depth, generator, leaves, sides=8)

    # Root flare: push the lowest ring outwards so the trunk meets the ground.
    lowest = min(v.co.z for v in bm.verts)
    for vert in bm.verts:
        if vert.co.z < lowest + 0.05:
            vert.co.x *= 1.7
            vert.co.y *= 1.7
            vert.co.z -= 0.12
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    trunk = pf.bm_to_object(bm, f"{name}_trunk")
    pf.shade_smooth(trunk, angle_deg=48.0)
    pf.apply_modifiers(trunk)
    pf.triangulate(trunk)
    pf.box_project_uv(trunk, scale=1.1)
    pf.set_material(trunk, "bark")

    # --- foliage cards --------------------------------------------------------
    fm = bmesh.new()
    uv_layer = fm.loops.layers.uv.new("UVMap")
    cells = [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]

    for tip, direction, radius in leaves:
        cluster = int(generator.integers(6, 10))
        for _index in range(cluster):
            cell_u, cell_v = cells[int(generator.integers(0, 4))]
            span = (0.62 + radius * 3.0) * leaf_scale * generator.uniform(0.8, 1.25)

            # Cards face outward from the branch tip, tilted randomly so a
            # cluster never resolves into a flat plane from any one angle.
            offset = Vector((generator.uniform(-1, 1), generator.uniform(-1, 1),
                             generator.uniform(-0.6, 1.0))).normalized()
            centre = Vector(tip) + direction * span * 0.35 + offset * span * 0.45
            normal = (offset + direction * 0.4).normalized()
            basis = normal.to_track_quat("Z", "Y").to_matrix().to_4x4()
            spin = Matrix.Rotation(generator.uniform(0, math.tau), 4, "Z")
            basis = basis @ spin

            corners = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
            verts = []
            for cx, cy in corners:
                local = Vector((cx * span, cy * span, 0.0))
                verts.append(fm.verts.new(centre + basis @ local))
            face = fm.faces.new(verts)
            for loop, (cx, cy) in zip(face.loops, corners):
                loop[uv_layer].uv = (cell_u + (cx + 0.5) * 0.5, cell_v + (cy + 0.5) * 0.5)

    fm.normal_update()
    foliage = pf.bm_to_object(fm, f"{name}_leaves")
    pf.shade_smooth(foliage, angle_deg=180.0)
    pf.apply_modifiers(foliage)
    pf.triangulate(foliage)
    pf.set_material(foliage, "leaf")

    return [trunk, foliage]


def make_bush(name, seed, radius=0.9):
    """A foliage-only clump — cheap cover dressing with no trunk."""
    generator = np.random.default_rng(seed)
    fm = bmesh.new()
    uv_layer = fm.loops.layers.uv.new("UVMap")
    cells = [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]

    for _index in range(int(generator.integers(7, 11))):
        cell_u, cell_v = cells[int(generator.integers(0, 4))]
        span = radius * generator.uniform(0.75, 1.25)
        direction = Vector((generator.uniform(-1, 1), generator.uniform(-1, 1),
                            generator.uniform(0.1, 1.0))).normalized()
        centre = direction * radius * generator.uniform(0.15, 0.55)
        centre.z = abs(centre.z) + radius * 0.35
        basis = direction.to_track_quat("Z", "Y").to_matrix().to_4x4() \
            @ Matrix.Rotation(generator.uniform(0, math.tau), 4, "Z")

        corners = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        verts = [fm.verts.new(centre + basis @ Vector((cx * span, cy * span, 0.0)))
                 for cx, cy in corners]
        face = fm.faces.new(verts)
        for loop, (cx, cy) in zip(face.loops, corners):
            loop[uv_layer].uv = (cell_u + (cx + 0.5) * 0.5, cell_v + (cy + 0.5) * 0.5)

    fm.normal_update()
    bush = pf.bm_to_object(fm, name)
    pf.shade_smooth(bush, angle_deg=180.0)
    pf.apply_modifiers(bush)
    pf.triangulate(bush)
    pf.set_material(bush, "leaf")
    return bush


def make_grass_tuft(name, seed):
    """Three crossed cards — the cheapest thing that still breaks up bare ground."""
    generator = np.random.default_rng(seed)
    fm = bmesh.new()
    uv_layer = fm.loops.layers.uv.new("UVMap")

    for index in range(3):
        angle = index * math.pi / 3.0 + generator.uniform(-0.2, 0.2)
        width = generator.uniform(0.42, 0.58)
        height = generator.uniform(0.32, 0.48)
        ca, sa = math.cos(angle), math.sin(angle)
        corners = [(-0.5, 0.0), (0.5, 0.0), (0.5, 1.0), (-0.5, 1.0)]
        verts = []
        for cx, cy in corners:
            verts.append(fm.verts.new(Vector((cx * width * ca, cx * width * sa, cy * height))))
        face = fm.faces.new(verts)
        cell_u = 0.5 * (index % 2)
        for loop, (cx, cy) in zip(face.loops, corners):
            loop[uv_layer].uv = (cell_u + (cx + 0.5) * 0.5, 0.5 + cy * 0.48)

    fm.normal_update()
    tuft = pf.bm_to_object(fm, name)
    pf.shade_smooth(tuft, angle_deg=180.0)
    pf.apply_modifiers(tuft)
    pf.triangulate(tuft)
    pf.set_material(tuft, "leaf")
    return tuft


def main():
    pf.reset_scene()
    pf.report("Trees and vegetation")

    exported = []
    species = [
        # Shorter, thicker, fuller than the first pass. A 8.5 m trunk 22 cm
        # across carrying a 0.75-scale crown reads as a sapling at any distance
        # the player actually sees it from — the crown is what says "tree", and
        # it has to be wide enough to survive being 100 m away.
        ("tree_pine", 7101, 7.6, 0.30, 3, 1.15),
        ("tree_oak", 7203, 6.0, 0.38, 3, 1.55),
        ("tree_scrub", 7307, 3.8, 0.22, 2, 1.25),
    ]
    for index, (name, seed, height, radius, depth, leaf_scale) in enumerate(species):
        parts = make_tree(name, seed, height, radius, depth, leaf_scale)
        total = sum(pf.tri_count(part) for part in parts)
        print(f"  {name:<12} {total:5d} tris  (trunk {pf.tri_count(parts[0])}, "
              f"leaves {pf.tri_count(parts[1])})")
        for part in parts:
            part.location.x = index * 10.0
        exported += parts

    for index, (name, seed, radius) in enumerate([("bush_low", 7411, 0.85),
                                                  ("bush_tall", 7523, 1.25)]):
        bush = make_bush(name, seed, radius)
        bush.location = (index * 4.0, 12.0, 0.0)
        print(f"  {name:<12} {pf.tri_count(bush):5d} tris")
        exported.append(bush)

    tuft = make_grass_tuft("grass_tuft", 7601)
    tuft.location = (10.0, 12.0, 0.0)
    print(f"  {'grass_tuft':<12} {pf.tri_count(tuft):5d} tris")
    exported.append(tuft)

    path = os.path.join(pf.MODEL_DIR, "vegetation.glb")
    pf.export_glb(exported, path)


if __name__ == "__main__":
    main()

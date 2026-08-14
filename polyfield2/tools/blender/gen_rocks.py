"""Generate rock and cliff meshes.

    blender -b --python gen_rocks.py

Five boulder variants plus two cliff blocks, all flat-shaded and box-projected
so one tiling granite texture serves every size.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh
import numpy as np
from mathutils import Vector

import pf_lib as pf
from noise_shim import fbm_2d, value_noise_2d


def _displace(bm, seed, amount=0.28, frequency=1.6, angular=0.55):
    """Push vertices along their own direction by layered noise.

    Two frequencies: a low one that makes the boulder lopsided, and a high
    one quantised into steps, which is what gives the faceted, fractured look
    instead of a potato.
    """
    generator = np.random.default_rng(seed)
    offset = generator.uniform(-40.0, 40.0, 3)

    for vert in bm.verts:
        point = np.array(vert.co) + offset
        broad = fbm_2d(np.array([point[0] * 0.35]), np.array([point[1] * 0.35 + point[2] * 0.5]),
                       frequency=frequency, octaves=3, seed=seed)[0]
        fine = value_noise_2d(np.array([point[0] * frequency * 3.1 + point[2]]),
                              np.array([point[1] * frequency * 3.1 - point[2]]),
                              seed=seed + 5)[0]
        # Quantising the fine layer creates flat facets and hard edges.
        fine = math.floor(fine * 5.0) / 5.0
        scale = 1.0 + (broad - 0.5) * 2.0 * amount + (fine - 0.5) * amount * angular
        vert.co = Vector(vert.co) * scale


def make_rock(name, seed, subdivisions=2, squash=0.72, amount=0.3):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=0.5)
    _displace(bm, seed, amount=amount)

    generator = np.random.default_rng(seed + 99)
    stretch = Vector((generator.uniform(0.8, 1.35),
                      generator.uniform(0.8, 1.35),
                      squash * generator.uniform(0.85, 1.15)))
    bmesh.ops.scale(bm, vec=stretch, verts=bm.verts)

    # Flatten the underside so boulders sit on the ground instead of floating.
    lowest = min(v.co.z for v in bm.verts)
    cut = lowest + 0.16 * abs(lowest)
    for vert in bm.verts:
        if vert.co.z < cut:
            vert.co.z = cut

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = pf.bm_to_object(bm, name)

    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=1.6)
    pf.set_material(obj, "rock_granite")
    return obj


def make_cliff(name, seed, size=(4.0, 2.4, 3.4)):
    """A blocky cliff chunk — used to dress the outcrops and map rim."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=2, use_grid_fill=True)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)

    generator = np.random.default_rng(seed)
    for vert in bm.verts:
        # Vertical faces get pushed sideways only, keeping the top and bottom
        # planar so cliffs stack and meet the ground cleanly.
        jitter = generator.normal(0.0, 0.16, 3)
        vert.co.x += jitter[0] * size[0] * 0.5
        vert.co.y += jitter[1] * size[1] * 0.5
        if abs(vert.co.z) < size[2] * 0.49:
            vert.co.z += jitter[2] * size[2] * 0.3

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = pf.bm_to_object(bm, name)
    obj.location = (0, 0, size[2] * 0.5)
    pf.select_only(obj)
    import bpy
    bpy.ops.object.transform_apply(location=True)

    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=2.6)
    pf.set_material(obj, "cliff_strata")
    return obj


def main():
    pf.reset_scene()
    pf.report("Rocks and cliffs")

    exported = []
    for index in range(5):
        obj = make_rock(f"rock_{index:02d}", seed=4100 + index * 37,
                        subdivisions=3 if index < 3 else 2,
                        squash=(0.72, 0.55, 0.9, 0.65, 0.8)[index],
                        amount=(0.3, 0.34, 0.26, 0.38, 0.3)[index])
        print(f"  rock_{index:02d}: {pf.tri_count(obj)} tris")
        exported.append(obj)

    for index in range(2):
        obj = make_cliff(f"cliff_{index:02d}", seed=5200 + index * 61,
                         size=((5.0, 2.6, 4.2), (3.4, 3.0, 5.6))[index])
        print(f"  cliff_{index:02d}: {pf.tri_count(obj)} tris")
        exported.append(obj)

    # Lay them out in a row so the preview render shows them side by side.
    for index, obj in enumerate(exported):
        obj.location.x = index * 4.0

    path = os.path.join(pf.MODEL_DIR, "rocks.glb")
    pf.export_glb(exported, path)


if __name__ == "__main__":
    main()

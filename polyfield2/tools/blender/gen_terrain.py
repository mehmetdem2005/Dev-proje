"""Generate the Ridgeline terrain mesh.

    blender -b --python gen_terrain.py

Produces assets/models/terrain_ridgeline.glb: the heightfield split into
chunks, with a three-way splat weight baked into vertex colours
(R = rock, G = grass, B = gravel/dirt) that the terrain shader blends.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import pf_lib as pf
import layout
from noise_shim import fbm_2d

CHUNKS = 4                 # 4x4 grid of terrain chunks
UV_METRES_PER_TILE = 3.2   # metres per texture repeat on the ground


def splat_weights(xs, ys, height):
    """Per-vertex rock / grass / gravel weights, normalised to sum to 1."""
    step = xs[0, 1] - xs[0, 0]
    gy, gx = np.gradient(height, step)
    slope = np.sqrt(gx ** 2 + gy ** 2)

    # Steep faces are bare rock, and so are the outcrop caps.
    # The threshold is deliberately high: at 0.30 every rolling hillside came
    # out stone, and the map read as one grey moonscape with no nature in it.
    # Rock now means a face too steep to hold soil, not merely a slope.
    rock = np.clip((slope - 0.46) / 0.40, 0.0, 1.0) ** 0.8
    for cx, cy, _amount, radius in layout.OUTCROPS:
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / (radius * 0.9)
        rock = np.maximum(rock, np.clip(1.2 - distance ** 2, 0.0, 1.0))

    # Anything churned up — trenches, craters, spawn aprons — is bare gravel.
    gravel = np.zeros_like(height)
    for _name, points, _depth, width in layout.TRENCHES:
        distance = layout._polyline_distance(xs, ys, points)
        gravel = np.maximum(gravel, np.clip(1.0 - (distance - width) / 4.0, 0.0, 1.0))
    for cx, cy, radius, _depth in layout.CRATERS:
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / (radius * 1.35)
        gravel = np.maximum(gravel, np.clip(1.0 - distance ** 2, 0.0, 1.0))
    for cx, cy in layout.BASES.values():
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / (layout.BASE_FLAT_RADIUS * 1.1)
        gravel = np.maximum(gravel, np.clip(1.0 - distance ** 3, 0.0, 1.0))
    # Roads and the dry watercourse are worn down to bare gravel — that is what
    # makes them read as routes rather than as shallow dents in the ground.
    for _name, points, width in layout.ROADS:
        distance = layout._polyline_distance(xs, ys, points)
        gravel = np.maximum(gravel, np.clip(1.0 - (distance - width * 0.5) / 2.2, 0.0, 1.0))
    gully_points, gully_width, _depth = layout.GULLY
    gully_distance = layout._polyline_distance(xs, ys, gully_points)
    gravel = np.maximum(gravel,
        np.clip(1.0 - (gully_distance - gully_width * 0.5) / 4.0, 0.0, 1.0))

    # Everything that is neither bare stone nor churned ground is highland
    # meadow. Grass is the *default* cover here, not the leftover: soil sits on
    # anything gentle enough to hold it, and the dryness field only scrapes
    # patches of it back to gravel so the ridge is never a uniform lawn.
    remainder = np.clip(1.0 - rock - gravel, 0.0, 1.0)
    dryness = fbm_2d(xs, ys, frequency=0.018, octaves=4, seed=layout.SEED + 404)
    bare = np.clip(0.62 - dryness * 1.25, 0.0, 1.0)
    # Grass thins out as the ground tips over, well before it turns to rock.
    bare = np.maximum(bare, np.clip((slope - 0.26) / 0.30, 0.0, 1.0))

    grass = remainder * (1.0 - bare)
    gravel = gravel + remainder * bare

    total = np.maximum(rock + grass + gravel, 1e-6)
    return rock / total, grass / total, gravel / total


def build_chunk(name, xs, ys, height, weights, y0, y1, x0, x1):
    """Build one terrain chunk as a mesh with UVs and vertex colours."""
    sub_x = xs[y0:y1 + 1, x0:x1 + 1]
    sub_y = ys[y0:y1 + 1, x0:x1 + 1]
    sub_z = height[y0:y1 + 1, x0:x1 + 1]
    rows, cols = sub_z.shape

    verts = np.stack([sub_x.ravel(), sub_y.ravel(), sub_z.ravel()], axis=-1)

    # Quads, wound counter-clockwise seen from above so normals point up.
    row_index = np.arange(rows - 1)[:, None]
    col_index = np.arange(cols - 1)[None, :]
    top_left = (row_index * cols + col_index).ravel()
    faces = np.stack([top_left, top_left + 1, top_left + cols + 1, top_left + cols], axis=-1)

    uvs = np.stack([sub_x.ravel() / UV_METRES_PER_TILE,
                    sub_y.ravel() / UV_METRES_PER_TILE], axis=-1)
    loop_uvs = uvs[faces.ravel()]

    mesh = pf.mesh_from_arrays(name, verts, faces, loop_uvs)
    obj = pf.new_object(name, mesh)

    colour_layer = mesh.color_attributes.new(name="splat", type="BYTE_COLOR", domain="CORNER")
    rock, grass, gravel = (w[y0:y1 + 1, x0:x1 + 1].ravel() for w in weights)
    per_loop = np.stack([rock[faces.ravel()], grass[faces.ravel()],
                         gravel[faces.ravel()], np.ones(faces.size)], axis=-1)
    colour_layer.data.foreach_set("color", per_loop.astype(np.float32).ravel())

    return obj


def main():
    pf.reset_scene()
    pf.report("Terrain — Ridgeline")

    xs, ys, height = layout.build_terrain()
    weights = splat_weights(xs, ys, height)
    rows, cols = height.shape
    print(f"  heightfield {cols}x{rows}, {layout.MAP_SIZE:.0f} m, "
          f"z {height.min():.1f}..{height.max():.1f}")

    step_y = (rows - 1) // CHUNKS
    step_x = (cols - 1) // CHUNKS

    terrain_material = pf.make_terrain_material(uv_scale=1.0)
    objects = []
    for cy in range(CHUNKS):
        for cx in range(CHUNKS):
            name = f"terrain_{cx}_{cy}"
            obj = build_chunk(name, xs, ys, height, weights,
                              cy * step_y, (cy + 1) * step_y,
                              cx * step_x, (cx + 1) * step_x)
            pf.shade_smooth(obj, angle_deg=60.0)
            pf.apply_modifiers(obj)
            pf.triangulate(obj)
            obj.data.materials.clear()
            obj.data.materials.append(terrain_material)
            objects.append(obj)

    total = sum(pf.tri_count(o) for o in objects)
    print(f"  {len(objects)} chunks, {total} tris "
          f"({total / len(objects):.0f} per chunk)")

    path = os.path.join(pf.MODEL_DIR, "terrain_ridgeline.glb")
    pf.export_glb(objects, path, vertex_colour="splat")

    layout.export_json()


if __name__ == "__main__":
    main()

"""Generate the structures that give each capture zone an identity.

    blender -b --python gen_buildings.py

Every zone looked the same: a mast, some sandbags, a few crates. From inside
one you could not tell which you were holding. Three silhouettes fix that —
a squat concrete bunker, a timber watchtower, and a roofless stone ruin —
each recognisable at range and each offering different cover.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Euler, Vector

import pf_lib as pf
from gen_fortifications import _bevelled_box


def _ground(obj):
    lowest = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    obj.location.z -= lowest
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def make_bunker(name="bunker"):
    """Concrete emplacement: thick walls, a firing slit, a stepped entrance.

    The slit is made by leaving a gap between two wall courses rather than by
    a boolean — cheaper, and it keeps the mesh clean for collision.
    """
    parts = []
    width, depth, wall = 6.4, 4.8, 0.55

    # Lower and upper courses of the front wall, with the slit between them.
    for level, height in ((0.55, 1.10), (2.05, 0.80)):
        front = _bevelled_box(f"{name}_front_{level}", (width, wall, height), bevel=0.04)
        front.location = (0.0, -depth * 0.5, level)
        parts.append(front)

    # Slit jambs so the gap does not run the full width.
    for sign in (-1, 1):
        jamb = _bevelled_box(f"{name}_jamb_{sign}", (1.5, wall, 0.45), bevel=0.04)
        jamb.location = (sign * (width * 0.5 - 0.75), -depth * 0.5, 1.38)
        parts.append(jamb)

    for sign in (-1, 1):
        side = _bevelled_box(f"{name}_side_{sign}", (wall, depth, 2.45), bevel=0.04)
        side.location = (sign * (width * 0.5 - wall * 0.5), 0.0, 1.22)
        parts.append(side)

    # Rear wall with a doorway gap.
    for sign in (-1, 1):
        rear = _bevelled_box(f"{name}_rear_{sign}", (width * 0.5 - 0.7, wall, 2.45), bevel=0.04)
        rear.location = (sign * (width * 0.25 + 0.35), depth * 0.5, 1.22)
        parts.append(rear)
    lintel = _bevelled_box(f"{name}_lintel", (1.6, wall, 0.42), bevel=0.04)
    lintel.location = (0.0, depth * 0.5, 2.24)
    parts.append(lintel)

    roof = _bevelled_box(f"{name}_roof", (width + 0.7, depth + 0.7, 0.5), bevel=0.05)
    roof.location = (0.0, 0.0, 2.70)
    parts.append(roof)

    # Weathered spoil banked against the sides.
    for sign in (-1, 1):
        berm = _bevelled_box(f"{name}_berm_{sign}", (1.3, depth * 0.9, 1.0), bevel=0.30)
        berm.location = (sign * (width * 0.5 + 0.4), 0.0, 0.4)
        parts.append(berm)

    obj = pf.join_objects(parts, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=2.2)
    pf.set_material(obj, "concrete_bunker")
    return _ground(obj)


def make_watchtower(name="watchtower"):
    """Timber tower: four raked legs, cross bracing, a railed platform."""
    parts = []
    height, spread_low, spread_high = 6.6, 2.3, 1.5

    for sx in (-1, 1):
        for sy in (-1, 1):
            # A leg is a thin box rotated to lean inwards on both axes.
            leg = _bevelled_box(f"{name}_leg_{sx}_{sy}", (0.20, 0.20, height), bevel=0.02)
            leg.location = ((sx * (spread_low + spread_high) * 0.5),
                            (sy * (spread_low + spread_high) * 0.5),
                            height * 0.5)
            leg.rotation_euler = Euler((sy * 0.07, -sx * 0.07, 0.0))
            parts.append(leg)

    # Cross bracing at two levels, on all four faces.
    for level in (1.9, 4.1):
        for axis in range(2):
            for sign in (-1, 1):
                brace = _bevelled_box(f"{name}_brace_{level}_{axis}_{sign}",
                                      (0.14, 3.9, 0.14), bevel=0.02)
                brace.location = (
                    (sign * 1.95) if axis == 0 else 0.0,
                    0.0 if axis == 0 else (sign * 1.95),
                    level)
                brace.rotation_euler = Euler(
                    (0.0, 0.0, math.pi * 0.5) if axis == 1 else (0.0, 0.42, 0.0))
                parts.append(brace)

    platform = _bevelled_box(f"{name}_platform", (3.6, 3.6, 0.22), bevel=0.03)
    platform.location = (0.0, 0.0, height)
    parts.append(platform)

    for axis in range(2):
        for sign in (-1, 1):
            rail = _bevelled_box(f"{name}_rail_{axis}_{sign}", (3.6, 0.12, 0.14), bevel=0.02)
            rail.location = ((0.0, sign * 1.74, height + 0.95) if axis == 0
                             else (sign * 1.74, 0.0, height + 0.95))
            if axis == 1:
                rail.rotation_euler = Euler((0.0, 0.0, math.pi * 0.5))
            parts.append(rail)
            post = _bevelled_box(f"{name}_post_{axis}_{sign}", (0.13, 0.13, 1.0), bevel=0.02)
            post.location = ((sign * 1.7, sign * 1.7, height + 0.5))
            parts.append(post)

    roof = _bevelled_box(f"{name}_roof", (4.0, 4.0, 0.16), bevel=0.03)
    roof.location = (0.0, 0.0, height + 1.55)
    parts.append(roof)

    ladder_rail_gap = 0.5
    for sign in (-1, 1):
        rail = _bevelled_box(f"{name}_ladder_{sign}", (0.10, 0.10, height), bevel=0.02)
        rail.location = (sign * ladder_rail_gap, 2.1, height * 0.5)
        parts.append(rail)
    for index in range(9):
        rung = _bevelled_box(f"{name}_rung_{index}", (1.1, 0.07, 0.07), bevel=0.015)
        rung.location = (0.0, 2.1, 0.6 + index * 0.68)
        parts.append(rung)

    obj = pf.join_objects(parts, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=1.4)
    pf.set_material(obj, "wood_plank")
    return _ground(obj)


def make_ruin(name="ruin"):
    """Roofless stone shell: broken walls of uneven height, rubble at the feet.

    Uneven wall tops are what make a ruin read as ruined; a box with a hole in
    it just reads as an unfinished building.
    """
    parts = []
    width, depth, thickness = 8.0, 6.0, 0.5

    # Front wall, segmented so each piece can end at a different height.
    heights = [2.9, 1.4, 2.2, 0.8]
    segment = width / len(heights)
    for index, wall_height in enumerate(heights):
        piece = _bevelled_box(f"{name}_front_{index}", (segment, thickness, wall_height),
                              bevel=0.05)
        piece.location = ((index - (len(heights) - 1) * 0.5) * segment,
                          -depth * 0.5, wall_height * 0.5)
        parts.append(piece)

    # Left wall stands tallest; right wall is mostly gone.
    left = _bevelled_box(f"{name}_left", (thickness, depth, 3.4), bevel=0.05)
    left.location = (-width * 0.5, 0.0, 1.7)
    parts.append(left)
    for index, wall_height in enumerate([1.9, 0.7]):
        piece = _bevelled_box(f"{name}_right_{index}", (thickness, depth * 0.45, wall_height),
                              bevel=0.05)
        piece.location = (width * 0.5, (index - 0.5) * depth * 0.5, wall_height * 0.5)
        parts.append(piece)

    rear = _bevelled_box(f"{name}_rear", (width * 0.62, thickness, 2.4), bevel=0.05)
    rear.location = (-width * 0.16, depth * 0.5, 1.2)
    parts.append(rear)

    # Window openings in the tall wall: two lintels with a gap under each.
    for offset in (-1.4, 1.4):
        lintel = _bevelled_box(f"{name}_lintel_{offset}", (thickness, 1.3, 0.28), bevel=0.03)
        lintel.location = (-width * 0.5, offset, 2.35)
        parts.append(lintel)

    # Collapsed rubble along the open side.
    rubble_places = [(-2.0, 1.2, 0.55), (0.6, 2.4, 0.42), (2.8, 0.4, 0.62), (-3.2, -1.6, 0.38)]
    for index, (rx, ry, size) in enumerate(rubble_places):
        chunk = _bevelled_box(f"{name}_rubble_{index}", (size * 2.2, size * 1.8, size),
                              bevel=size * 0.28)
        chunk.location = (rx, ry, size * 0.5)
        chunk.rotation_euler = Euler((0.12 * index, 0.09 * index, 0.7 * index))
        parts.append(chunk)

    obj = pf.join_objects(parts, name)
    pf.select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.shade_flat(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=2.6)
    pf.set_material(obj, "stone_wall")
    return _ground(obj)


def main():
    pf.reset_scene()
    pf.report("Buildings")

    exported = []
    for index, builder in enumerate([make_bunker, make_watchtower, make_ruin]):
        obj = builder()
        print(f"  {obj.name:<12} {pf.tri_count(obj):5d} tris")
        obj.location.x = index * 14.0
        exported.append(obj)

    path = os.path.join(pf.MODEL_DIR, "buildings.glb")
    pf.export_glb(exported, path)


if __name__ == "__main__":
    main()

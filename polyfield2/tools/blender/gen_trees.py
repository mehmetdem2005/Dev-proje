"""Generate trees, bushes and grass tufts.

    blender -b --python gen_trees.py

Trunks and branches are real geometry; foliage is alpha-cut cards clustered on
the branches. That combination is what reads as a tree on a phone — a billboard
alone looks like cardboard from the side, and modelled leaves cost far too much.

The species are built by *different growth models*, not by feeding one model
different numbers. That was the flaw in the first pass: pine, oak and scrub all
came out of the same recursive fork, so they were one tree at three scales no
matter how the parameters were tuned. A conifer keeps a single straight leader
and hangs whorls of branches off it, narrowing towards the top (excurrent); a
broadleaf loses its leader at the first fork and spreads into competing
scaffolds (decurrent). Those two habits are most of what tells them apart at
a hundred metres, where the crown is four pixels tall.

Six species:

    tree_pine     tall conifer, open whorls, high crown
    tree_fir      dense conifer, skirted to the ground
    tree_oak      heavy broadleaf, low fork, wide spreading crown
    tree_birch    slender broadleaf, curved bole, light high crown
    tree_scrub    multi-stemmed shrub-tree
    tree_dead     bare snag, broken top, no foliage at all
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import pf_lib as pf

#: Atlas rows, mirroring tools/texgen/leaf_atlas.py ROWS. Both must agree or
#: species get the wrong foliage family.
ATLAS_GRID = 4
ATLAS_ROWS = {"broad": 0, "needle": 1, "scrub": 2, "grass": 3}


# --- geometry helpers -------------------------------------------------------

def _frame(direction):
    """An orthonormal basis with Z along `direction`."""
    return direction.normalized().to_track_quat("Z", "Y").to_matrix()


def _path(base, direction, length, segments, bend, generator):
    """A gently curving polyline: `bend` is the per-segment drift direction.

    Straight limbs are the giveaway of a procedural tree. Every limb here
    accumulates a small consistent drift plus jitter, so it leans and wanders
    the way a real one does under its own weight.
    """
    point = Vector(base)
    heading = Vector(direction).normalized()
    points = [point.copy()]
    step = length / segments

    for _index in range(segments):
        point = point + heading * step
        points.append(point.copy())
        heading = (heading + Vector(bend) / segments
                   + Vector((generator.uniform(-0.05, 0.05),
                             generator.uniform(-0.05, 0.05),
                             generator.uniform(-0.03, 0.03)))).normalized()
    return points


def _tube(bm, points, radius_start, radius_end, sides=6, taper=1.0):
    """Loft a tapered tube along a polyline, returning the tip and its heading.

    Rings are oriented by a parallel-transported frame rather than by each
    segment's own basis: recomputing the basis per segment makes the tube spin
    around its own axis at every bend, which shows up as a twisted, pinched
    trunk once the bark texture is on it.
    """
    count = len(points)
    heading = (points[1] - points[0]).normalized()
    frame = _frame(heading)

    rings = []
    for index, point in enumerate(points):
        if index > 0:
            new_heading = (points[index] - points[index - 1]).normalized()
            rotation = heading.rotation_difference(new_heading).to_matrix()
            frame = rotation @ frame
            heading = new_heading

        t = index / (count - 1)
        radius = radius_start + (radius_end - radius_start) * (t ** taper)
        ring = []
        for side in range(sides):
            angle = (side / sides) * math.tau
            local = Vector((math.cos(angle) * radius, math.sin(angle) * radius, 0.0))
            ring.append(bm.verts.new(point + frame @ local))
        rings.append(ring)

    for index in range(count - 1):
        lower, upper = rings[index], rings[index + 1]
        for side in range(sides):
            nxt = (side + 1) % sides
            bm.faces.new((lower[side], lower[nxt], upper[nxt], upper[side]))

    return points[-1], heading


def _flare(bm, amount=1.7, drop=0.12):
    """Push the lowest ring outwards so the trunk meets the ground."""
    lowest = min(vert.co.z for vert in bm.verts)
    for vert in bm.verts:
        if vert.co.z < lowest + 0.06:
            vert.co.x *= amount
            vert.co.y *= amount
            vert.co.z -= drop


def _finish_wood(bm, name, uv_scale=1.1):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = pf.bm_to_object(bm, name)
    pf.shade_smooth(obj, angle_deg=48.0)
    pf.apply_modifiers(obj)
    pf.triangulate(obj)
    pf.box_project_uv(obj, scale=uv_scale)
    pf.set_material(obj, "bark")
    return obj


# --- foliage ----------------------------------------------------------------

class Foliage:
    """Accumulates alpha-cut cards, then bakes them into one mesh."""

    def __init__(self, family):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.row = ATLAS_ROWS[family]
        self.count = 0

    def card(self, centre, normal, span, generator, roll=None):
        cell = 1.0 / ATLAS_GRID
        column = int(generator.integers(0, ATLAS_GRID))
        origin_u = column * cell
        origin_v = self.row * cell

        basis = _frame(Vector(normal)).to_4x4()
        spin = Matrix.Rotation(roll if roll is not None
                               else generator.uniform(0, math.tau), 4, "Z")
        basis = basis @ spin

        corners = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        verts = [self.bm.verts.new(Vector(centre) + basis @ Vector((cx * span, cy * span, 0.0)))
                 for cx, cy in corners]
        face = self.bm.faces.new(verts)
        for loop, (cx, cy) in zip(face.loops, corners):
            loop[self.uv].uv = (origin_u + (cx + 0.5) * cell, origin_v + (cy + 0.5) * cell)
        self.count += 1

    def cluster(self, centre, direction, span, howmany, generator, spread=0.45):
        """A ball of cards around a point, tilted every which way.

        Cards all sharing one normal collapse into a flat plane the moment the
        camera lines up with it, so each one is tilted off an independent random
        axis rather than off the branch direction.
        """
        direction = Vector(direction).normalized()
        for _index in range(howmany):
            offset = Vector((generator.uniform(-1, 1), generator.uniform(-1, 1),
                             generator.uniform(-0.6, 1.0))).normalized()
            point = Vector(centre) + direction * span * 0.3 + offset * span * spread
            self.card(point, (offset + direction * 0.4).normalized(),
                      span * generator.uniform(0.8, 1.25), generator)

    def bake(self, name):
        if self.count == 0:
            self.bm.free()
            return None
        self.bm.normal_update()
        obj = pf.bm_to_object(self.bm, name)
        pf.shade_smooth(obj, angle_deg=180.0)
        pf.apply_modifiers(obj)
        pf.triangulate(obj)
        pf.set_material(obj, "leaf")
        return obj


# --- species ----------------------------------------------------------------

def make_conifer(name, seed, height=8.0, trunk_radius=0.26, whorls=9,
                 reach=2.4, skirt=0.12, droop=0.30, cards=3, span=0.95):
    """Excurrent habit: one straight leader, whorls of branches, conical crown.

    `skirt` is the fraction of the trunk left bare at the bottom — a fir sweeps
    almost to the ground, a mature pine carries its crown high on a clean bole.
    """
    generator = np.random.default_rng(seed)
    bm = bmesh.new()
    leaves = Foliage("needle")

    # The leader: near vertical, barely wandering, tapering to a point.
    trunk = _path((0, 0, 0), (generator.uniform(-0.03, 0.03),
                              generator.uniform(-0.03, 0.03), 1.0),
                  height, 6, Vector((0.04, 0.03, 0.0)), generator)
    _tube(bm, trunk, trunk_radius, trunk_radius * 0.06, sides=7, taper=0.85)

    for level in range(whorls):
        t = level / float(whorls - 1)
        base_height = height * (skirt + (0.94 - skirt) * t)
        # Branch length falls away towards the top; that taper is the cone.
        length = reach * (1.0 - t) ** 0.75 * generator.uniform(0.85, 1.15) + 0.18
        if length < 0.25:
            continue

        arms = max(3, int(round(5 - t * 1.5)))
        phase = generator.uniform(0, math.tau)
        origin = Vector((0.0, 0.0, base_height))

        for arm in range(arms):
            angle = phase + (arm / arms) * math.tau + generator.uniform(-0.25, 0.25)
            # Branches sit level near the top and sag lower down the tree.
            rise = -droop * (1.0 - t) + generator.uniform(-0.06, 0.10)
            direction = Vector((math.cos(angle), math.sin(angle), rise)).normalized()

            points = _path(origin, direction, length, 2,
                           Vector((0.0, 0.0, -0.30)), generator)
            # Three sides. A branch tube is never read as a cylinder at any
            # distance a player sees one, and there are forty-odd per conifer.
            tip, heading = _tube(bm, points, trunk_radius * 0.30 * (1.0 - t * 0.5) + 0.012,
                                 0.012, sides=3)

            # Foliage rides the outer half of every branch, not just the tip.
            for step in range(cards):
                along = 0.45 + 0.55 * (step / max(cards - 1, 1))
                point = points[0].lerp(tip, along)
                leaves.cluster(point, heading, span * (0.55 + 0.45 * (1.0 - t)),
                               2, generator, spread=0.35)

    _flare(bm)
    return [_finish_wood(bm, f"{name}_trunk"), leaves.bake(f"{name}_leaves")]


def _limbs(bm, leaves, base, direction, length, radius, depth, generator,
           span, cards, spread_bias):
    """Recursive scaffold for a broadleaf crown."""
    points = _path(base, direction, length, 2,
                   Vector((0.0, 0.0, -0.12)) + Vector(direction).normalized() * 0.05,
                   generator)
    end_radius = radius * generator.uniform(0.52, 0.66)
    sides = 5 if depth > 1 else 3
    tip, heading = _tube(bm, points, radius, end_radius, sides=sides)

    if depth <= 1 or end_radius < 0.030:
        leaves.cluster(tip, heading, span, cards, generator)
        return

    # Outer limbs also carry foliage, or the crown is hollow in the middle.
    if depth == 2:
        leaves.cluster(points[0].lerp(tip, 0.7), heading, span * 0.8, max(cards - 2, 2),
                       generator)

    forks = int(generator.integers(2, 4))
    for index in range(forks):
        lean = generator.uniform(0.40, 0.88) * spread_bias
        twist = (index / float(forks)) * math.tau + generator.uniform(-0.45, 0.45)
        axis = Vector((math.cos(twist), math.sin(twist), 0.0))
        child = (Vector(heading).normalized() + axis * lean).normalized()
        child.z += generator.uniform(-0.02, 0.20)
        _limbs(bm, leaves, tip, child.normalized(), length * generator.uniform(0.58, 0.76),
               end_radius, depth - 1, generator, span * 0.92, cards, spread_bias)


def make_broadleaf(name, seed, height=6.5, trunk_radius=0.36, fork=0.40,
                   scaffolds=4, depth=3, spread_bias=1.0, span=1.15, cards=6,
                   bole_bend=0.10):
    """Decurrent habit: the leader is lost at the first fork and the crown
    spreads into competing scaffold limbs."""
    generator = np.random.default_rng(seed)
    bm = bmesh.new()
    leaves = Foliage("broad")

    bole_height = height * fork
    bole = _path((0, 0, 0), (generator.uniform(-0.05, 0.05),
                             generator.uniform(-0.05, 0.05), 1.0),
                 bole_height, 5,
                 Vector((bole_bend, bole_bend * 0.6, 0.0)), generator)
    tip, heading = _tube(bm, bole, trunk_radius, trunk_radius * 0.66, sides=7)

    phase = generator.uniform(0, math.tau)
    for index in range(scaffolds):
        angle = phase + (index / scaffolds) * math.tau + generator.uniform(-0.3, 0.3)
        lean = generator.uniform(0.55, 0.95) * spread_bias
        direction = (Vector(heading) + Vector((math.cos(angle), math.sin(angle), 0.0)) * lean)
        _limbs(bm, leaves, tip, direction.normalized(),
               (height - bole_height) * generator.uniform(0.52, 0.72),
               trunk_radius * generator.uniform(0.50, 0.66), depth, generator,
               span, cards, spread_bias)

    _flare(bm)
    return [_finish_wood(bm, f"{name}_trunk"), leaves.bake(f"{name}_leaves")]


def make_multistem(name, seed, height=3.6, stem_radius=0.13, stems=5,
                   span=0.85, cards=5):
    """Several stems from a common root — a shrub-tree, not a small tree."""
    generator = np.random.default_rng(seed)
    bm = bmesh.new()
    leaves = Foliage("scrub")

    phase = generator.uniform(0, math.tau)
    for index in range(stems):
        angle = phase + (index / stems) * math.tau + generator.uniform(-0.4, 0.4)
        lean = generator.uniform(0.20, 0.44)
        direction = Vector((math.cos(angle) * lean, math.sin(angle) * lean, 1.0))
        base = Vector((math.cos(angle) * 0.10, math.sin(angle) * 0.10, 0.0))
        _limbs(bm, leaves, base, direction.normalized(),
               height * generator.uniform(0.62, 0.94),
               stem_radius * generator.uniform(0.8, 1.2), 2, generator,
               span, cards, 1.0)

    _flare(bm, amount=1.35, drop=0.08)
    return [_finish_wood(bm, f"{name}_trunk", uv_scale=0.8), leaves.bake(f"{name}_leaves")]


def make_snag(name, seed, height=5.4, trunk_radius=0.30, stubs=5):
    """A dead standing trunk: broken top, a few snapped branch stubs, no leaves.

    Costs nothing in foliage and does more for a battlefield than another green
    tree — and because it has no cutout cards it is the cheapest thing in the
    set to draw.
    """
    generator = np.random.default_rng(seed)
    bm = bmesh.new()

    trunk = _path((0, 0, 0), (generator.uniform(-0.08, 0.08),
                              generator.uniform(-0.08, 0.08), 1.0),
                  height, 6, Vector((0.10, 0.07, 0.0)), generator)
    # A snapped top is a ragged stump, not a taper to a point.
    tip, heading = _tube(bm, trunk, trunk_radius, trunk_radius * 0.42, sides=7)
    for vert in bm.verts:
        if vert.co.z > height * 0.94:
            vert.co.z += generator.uniform(-0.35, 0.30)

    for index in range(stubs):
        t = generator.uniform(0.30, 0.88)
        angle = generator.uniform(0, math.tau)
        rise = generator.uniform(-0.35, 0.35)
        base = Vector((0.0, 0.0, height * t))
        direction = Vector((math.cos(angle), math.sin(angle), rise)).normalized()
        points = _path(base, direction, generator.uniform(0.5, 1.5), 2,
                       Vector((0.0, 0.0, -0.25)), generator)
        _tube(bm, points, trunk_radius * generator.uniform(0.22, 0.36), 0.02, sides=3)

    _flare(bm)
    return [_finish_wood(bm, f"{name}_trunk"), None]


def make_bush(name, seed, radius=0.9, family="scrub"):
    """A foliage-only clump — cheap cover dressing with no trunk."""
    generator = np.random.default_rng(seed)
    leaves = Foliage(family)

    for _index in range(int(generator.integers(7, 11))):
        span = radius * generator.uniform(0.75, 1.25)
        direction = Vector((generator.uniform(-1, 1), generator.uniform(-1, 1),
                            generator.uniform(0.1, 1.0))).normalized()
        centre = direction * radius * generator.uniform(0.15, 0.55)
        centre.z = abs(centre.z) + radius * 0.35
        leaves.card(centre, direction, span, generator)

    return leaves.bake(name)


def make_grass_tuft(name, seed):
    """Three crossed cards — the cheapest thing that still breaks up bare ground.

    Mapped so the blade roots land on the top edge of the atlas band and the
    tips on the bottom edge, because in this atlas v runs downwards.
    """
    generator = np.random.default_rng(seed)
    fm = bmesh.new()
    uv_layer = fm.loops.layers.uv.new("UVMap")
    cell = 1.0 / ATLAS_GRID
    origin_v = ATLAS_ROWS["grass"] * cell

    for index in range(3):
        angle = index * math.pi / 3.0 + generator.uniform(-0.2, 0.2)
        width = generator.uniform(0.42, 0.58)
        height = generator.uniform(0.32, 0.48)
        column = int(generator.integers(0, ATLAS_GRID))
        origin_u = column * cell

        ca, sa = math.cos(angle), math.sin(angle)
        corners = [(-0.5, 0.0), (0.5, 0.0), (0.5, 1.0), (-0.5, 1.0)]
        verts = [fm.verts.new(Vector((cx * width * ca, cx * width * sa, cy * height)))
                 for cx, cy in corners]
        face = fm.faces.new(verts)
        for loop, (cx, cy) in zip(face.loops, corners):
            loop[uv_layer].uv = (origin_u + (cx + 0.5) * cell, origin_v + cy * cell)

    fm.normal_update()
    tuft = pf.bm_to_object(fm, name)
    pf.shade_smooth(tuft, angle_deg=180.0)
    pf.apply_modifiers(tuft)
    pf.triangulate(tuft)
    pf.set_material(tuft, "leaf")
    return tuft


#: name -> (builder, kwargs). Order matters: level_builder.gd indexes species by
#: the same order the layout's `variant` field was generated against.
SPECIES = [
    ("tree_pine", make_conifer, dict(seed=7101, height=8.6, trunk_radius=0.27,
                                     whorls=9, reach=2.3, skirt=0.34, droop=0.26,
                                     cards=3, span=1.00)),
    ("tree_fir", make_conifer, dict(seed=7157, height=7.0, trunk_radius=0.24,
                                    whorls=11, reach=2.0, skirt=0.08, droop=0.40,
                                    cards=3, span=0.90)),
    ("tree_oak", make_broadleaf, dict(seed=7203, height=6.4, trunk_radius=0.40,
                                      fork=0.34, scaffolds=4, depth=3,
                                      spread_bias=1.25, span=1.30, cards=7,
                                      bole_bend=0.08)),
    ("tree_birch", make_broadleaf, dict(seed=7251, height=7.8, trunk_radius=0.20,
                                        fork=0.62, scaffolds=3, depth=3,
                                        spread_bias=0.72, span=0.95, cards=5,
                                        bole_bend=0.26)),
    ("tree_scrub", make_multistem, dict(seed=7307, height=3.6, stem_radius=0.12,
                                        stems=5, span=0.80, cards=5)),
    ("tree_dead", make_snag, dict(seed=7361, height=5.6, trunk_radius=0.29, stubs=6)),
]


def main():
    pf.reset_scene()
    pf.report("Trees and vegetation")

    exported = []
    for index, (name, builder, kwargs) in enumerate(SPECIES):
        parts = [part for part in builder(name, **kwargs) if part is not None]
        trunk_tris = pf.tri_count(parts[0])
        leaf_tris = pf.tri_count(parts[1]) if len(parts) > 1 else 0
        print(f"  {name:<12} {trunk_tris + leaf_tris:5d} tris  "
              f"(trunk {trunk_tris}, leaves {leaf_tris})")
        for part in parts:
            part.location.x = index * 10.0
        exported += parts

    for index, (name, seed, radius, family) in enumerate(
            [("bush_low", 7411, 0.85, "scrub"), ("bush_tall", 7523, 1.25, "broad")]):
        bush = make_bush(name, seed, radius, family)
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

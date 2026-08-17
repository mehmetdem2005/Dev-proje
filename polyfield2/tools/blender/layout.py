"""Single source of truth for the "Ridgeline" battlefield.

Pure Python, no bpy — the terrain generator carves from it, the prop scatter
places from it, and Godot reads the exported JSON to build the level. Keeping
one definition means a trench in the terrain mesh can never drift away from
the trench module standing in it.

World axes here are Blender's: X right, Y forward, Z up. The exporter converts
to Godot's Y-up on the way out; gameplay markers in the JSON are already
written in Godot coordinates (see `_to_godot`).
"""

import json
import math
import os

import numpy as np

MAP_SIZE = 192.0          # metres, square
GRID = 1.0                # terrain vertex spacing in metres
SEED = 20260814

# --------------------------------------------------------------------------
# Terrain shape
# --------------------------------------------------------------------------

# Gaussian landforms: (x, y, height, radius, sharpness)
LANDFORMS = [
    (-58.0, -34.0, 9.0, 40.0, 1.6),    # west shoulder above Ranger ground
    (-24.0,  26.0, 15.0, 30.0, 1.9),   # B — west knoll
    (  0.0,   0.0, 11.0, 34.0, 1.5),   # C — centre saddle
    ( 31.0, -26.0, 14.5, 29.0, 1.9),   # D — east knoll
    ( 56.0,  46.0, 8.0, 38.0, 1.6),    # east shoulder above Legion ground
    (-72.0,  62.0, 6.0, 26.0, 1.4),
    ( 70.0, -60.0, 6.5, 25.0, 1.4),
]

# Rock outcrops — sharper, smaller, they break sightlines along the ridge.
OUTCROPS = [
    (-40.0,   4.0, 5.5, 11.0),
    (-10.0,  30.0, 4.5,  9.0),
    ( 14.0,  10.0, 5.0, 10.0),
    ( 40.0, -10.0, 4.8,  9.5),
    (  6.0, -34.0, 5.2, 10.5),
    (-30.0, -18.0, 4.0,  8.0),
    ( 22.0,  40.0, 4.2,  8.5),
]

# Base areas get flattened so spawns are never on a slope.
# Kept clear of the boundary rim, which starts rising at 0.82 * half-size
# (~79 m). Bases at +/-78 sat directly on that slope and spawned players
# inside the hillside.
BASES = {
    "ranger": (-64.0, -64.0),
    "legion": (64.0, 64.0),
}
BASE_FLAT_RADIUS = 22.0


def _ridge_offset(x):
    """The ridge line meanders instead of running dead straight."""
    return 9.0 * np.sin(x / 46.0) + 4.0 * np.sin(x / 17.0 + 1.2)


def height_field(size=MAP_SIZE, grid=GRID, seed=SEED):
    """Return (xs, ys, heights) for the base terrain before trench carving."""
    from noise_shim import fbm_2d, ridged_2d

    steps = int(size / grid) + 1
    axis = np.linspace(-size * 0.5, size * 0.5, steps)
    xs, ys = np.meshgrid(axis, axis, indexing="xy")

    # Broad landform first — smooth gaussians alone give a billiard table with
    # bumps on it, so the base layer is noise and the gaussians only steer it.
    height = fbm_2d(xs, ys, frequency=0.0075, octaves=5, seed=seed) * 10.0

    # Main ridge running roughly west to east.
    ridge_distance = ys - _ridge_offset(xs)
    height += 12.0 * np.exp(-(ridge_distance / 36.0) ** 2)

    for cx, cy, amount, radius, sharpness in LANDFORMS:
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / radius
        height += amount * np.exp(-(distance ** sharpness))

    # Rocky character: ridged noise squared gives crests and gullies rather
    # than dunes. This is what makes the ground read as highland rock.
    crags = ridged_2d(xs, ys, frequency=0.026, octaves=4, seed=seed + 3)
    height += (crags ** 2.2) * 6.0

    # Outcrops are steep and tall enough to break a sightline and be climbed
    # behind — a 4 m bump does neither.
    for cx, cy, amount, radius in OUTCROPS:
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / radius
        height += amount * 1.55 * np.exp(-(distance ** 2.2))

    height += fbm_2d(xs, ys, frequency=0.085, octaves=3, seed=seed + 7) * 1.5

    # Flatten the bases into shallow hollows rather than raised plates.
    for cx, cy in BASES.values():
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        blend = np.clip((distance - BASE_FLAT_RADIUS) / 12.0, 0.0, 1.0)
        local = float(np.median(height[distance < BASE_FLAT_RADIUS * 1.4])) - 1.5
        height = height * blend + local * (1.0 - blend)

    # Boundary mountains.
    #
    # These were smooth grey lumps: one soft noise term times a smooth ramp,
    # which produces dunes, not mountains. Real ranges have a jagged crest
    # line, faces steeper than their base, and side spurs running off them.
    # Three terms do that:
    #   * a ridged multifractal at two scales for the crest and its spurs,
    #   * an exponent on the ramp so the face steepens as it climbs,
    #   * a per-peak modulation so the crest height varies along its length.
    edge = np.maximum(np.abs(xs), np.abs(ys)) / (size * 0.5)
    rim = np.clip((edge - 0.78) / 0.22, 0.0, 1.0)

    crest = ridged_2d(xs, ys, frequency=0.021, octaves=5, seed=seed + 11) ** 1.6
    spurs = ridged_2d(xs, ys, frequency=0.055, octaves=4, seed=seed + 17) ** 2.0
    peaks = 0.55 + 0.9 * fbm_2d(xs, ys, frequency=0.010, octaves=3, seed=seed + 23)

    # rim**2.4 keeps the foot gentle and the upper face steep.
    height += (rim ** 2.4) * peaks * (crest * 26.0 + spurs * 9.0)
    # A hard shoulder right at the border stops anyone walking out of the map.
    height += np.clip((edge - 0.94) / 0.06, 0.0, 1.0) ** 2 * 22.0

    return xs, ys, height


# --------------------------------------------------------------------------
# Trench network
# --------------------------------------------------------------------------

# Each entry: name, polyline points, depth, floor width.
TRENCHES = [
    ("ranger_forward", [(-88, -46), (-62, -40), (-40, -34), (-18, -32), (4, -36)], 2.7, 2.0),
    ("legion_forward", [(88, 40), (64, 36), (42, 30), (20, 30), (-2, 34)], 2.7, 2.0),
    ("centre_ring_w", [(-20, 6), (-13, 14), (-2, 17), (9, 13)], 2.5, 1.9),
    ("centre_ring_e", [(9, 13), (16, 4), (12, -7), (0, -11), (-12, -6), (-20, 6)], 2.5, 1.9),
    ("comm_west", [(-40, -34), (-36, -18), (-30, -4), (-20, 6)], 2.3, 1.7),
    ("comm_east", [(42, 30), (34, 20), (22, 12), (9, 13)], 2.3, 1.7),
    ("knoll_b", [(-38, 26), (-28, 33), (-16, 32), (-8, 25)], 2.4, 1.8),
    ("knoll_d", [(18, -30), (28, -35), (40, -32), (47, -24)], 2.4, 1.8),
]

PARAPET_HEIGHT = 0.55
PARAPET_WIDTH = 2.4
WALL_SLOPE = 0.9          # metres of horizontal run for the trench wall


def _polyline_distance(xs, ys, points):
    """Shortest distance from every grid cell to a polyline."""
    best = np.full(xs.shape, 1e9)
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        dx, dy = x1 - x0, y1 - y0
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-9:
            continue
        t = ((xs - x0) * dx + (ys - y0) * dy) / length_sq
        t = np.clip(t, 0.0, 1.0)
        px, py = x0 + t * dx, y0 + t * dy
        best = np.minimum(best, np.sqrt((xs - px) ** 2 + (ys - py) ** 2))
    return best


def carve_trenches(xs, ys, height):
    """Cut the trench channels and raise their parapets.

    The terrain only provides the channel and the spoil lip; the revetted
    walls, firing step and duckboards are separate modules placed along the
    same polylines, which is both cheaper and far better looking than trying
    to resolve a vertical wall in a 1 m heightfield.
    """
    carved = height.copy()
    for _name, points, depth, floor_width in TRENCHES:
        distance = _polyline_distance(xs, ys, points)
        half = floor_width * 0.5

        # Parapet first, so the channel then cuts through it.
        lip = np.clip((distance - half) / PARAPET_WIDTH, 0.0, 1.0)
        lip_shape = np.sin(np.clip(lip, 0.0, 1.0) * math.pi) ** 0.7
        carved += lip_shape * PARAPET_HEIGHT * (distance < half + PARAPET_WIDTH)

        # Channel: flat floor, then a steep wall out to the surface.
        wall = np.clip((distance - half) / WALL_SLOPE, 0.0, 1.0)
        profile = 1.0 - wall ** 0.55
        carved -= profile * depth
    return carved


# Worn vehicle tracks linking the zones. Roads do two things for a map: they
# tell a player where to go without a marker, and they give the eye somewhere
# to travel. Carved shallow and flattened rather than trenched.
ROADS = [
    ("main_axis", [(-72, -70), (-56, -48), (-40, -30), (-22, -12), (-4, 2), (14, 12),
                   (34, 26), (52, 44), (68, 62)], 5.0),
    ("west_spur", [(-56, -48), (-52, -24), (-42, 0), (-30, 22), (-24, 30)], 3.6),
    ("east_spur", [(14, 12), (26, -2), (32, -18), (33, -28)], 3.6),
    ("ridge_track", [(-24, 30), (-6, 26), (10, 18), (26, 12)], 3.2),
]

# A dry watercourse. It cuts across the main axis, so it is a natural covered
# route as well as a terrain feature that is not another gaussian hill.
GULLY = ([(-88, 20), (-62, 14), (-38, 4), (-16, -6), (6, -16), (28, -30), (52, -46),
          (74, -58)], 7.0, 2.6)


CRATERS = [
    (-46.0, -12.0, 6.5, 1.6), (12.0, 22.0, 5.0, 1.2), (34.0, 2.0, 7.0, 1.8),
    (-8.0, -46.0, 5.5, 1.4), (56.0, 12.0, 6.0, 1.5), (-62.0, 18.0, 5.2, 1.3),
]


def carve_craters(xs, ys, height):
    carved = height.copy()
    for cx, cy, radius, depth in CRATERS:
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / radius
        bowl = np.clip(1.0 - distance ** 2, 0.0, 1.0)
        rim = np.clip(1.0 - (distance - 1.0) ** 2 * 6.0, 0.0, 1.0) * (distance > 1.0)
        carved += rim * depth * 0.35 - bowl * depth
    return carved


def carve_roads(xs, ys, height):
    """Flatten a track along each road, with a shallow cut and soft verges."""
    carved = height.copy()
    for _name, points, width in ROADS:
        distance = _polyline_distance(xs, ys, points)
        half = width * 0.5
        blend = np.clip(1.0 - (distance - half) / 3.5, 0.0, 1.0)
        if blend.max() <= 0.0:
            continue
        # Ease the road towards a locally smoothed version of the terrain
        # rather than to a fixed height, so it follows the hills instead of
        # cutting a shelf through them.
        smoothed = height.copy()
        for _pass in range(3):
            smoothed = (smoothed
                        + np.roll(smoothed, 1, 0) + np.roll(smoothed, -1, 0)
                        + np.roll(smoothed, 1, 1) + np.roll(smoothed, -1, 1)) / 5.0
        carved = carved * (1.0 - blend * 0.85) + smoothed * (blend * 0.85)
        carved -= np.clip(1.0 - distance / half, 0.0, 1.0) * 0.22
    return carved


def carve_gully(xs, ys, height):
    """Cut the dry watercourse: wide, soft-sided, deeper than a road."""
    points, width, depth = GULLY
    distance = _polyline_distance(xs, ys, points)
    half = width * 0.5
    profile = np.clip(1.0 - (distance - half) / 6.0, 0.0, 1.0) ** 1.4
    banks = np.clip(1.0 - np.abs(distance - half - 5.0) / 4.0, 0.0, 1.0)
    return height - profile * depth + banks * 0.45


def flatten_zones(xs, ys, height, strength=0.8):
    """Level the ground under each capture zone.

    A capture point on a 25% slope is a coin toss rather than a fight. The
    surrounding crags stay — only the platform the flag stands on is eased
    towards its own local median.
    """
    eased = height.copy()
    for _name, cx, cy, radius, _owner in ZONES:
        distance = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        inner = distance < radius * 0.85
        if not inner.any():
            continue
        target = float(np.median(height[inner]))
        blend = np.clip((distance - radius * 0.6) / (radius * 0.9), 0.0, 1.0)
        weight = (1.0 - blend) * strength
        eased = eased * (1.0 - weight) + target * weight
    return eased


def build_terrain(size=MAP_SIZE, grid=GRID, seed=SEED):
    xs, ys, height = height_field(size, grid, seed)
    height = carve_gully(xs, ys, height)
    height = carve_roads(xs, ys, height)
    height = flatten_zones(xs, ys, height)
    height = carve_trenches(xs, ys, height)
    height = carve_craters(xs, ys, height)
    return xs, ys, height


def sample_height(xs, ys, height, x, y):
    """Bilinear sample of the finished terrain — used to seat props."""
    axis = xs[0]
    step = axis[1] - axis[0]
    fx = np.clip((x - axis[0]) / step, 0, xs.shape[1] - 1.001)
    fy = np.clip((y - axis[0]) / step, 0, xs.shape[0] - 1.001)
    x0, y0 = int(fx), int(fy)
    tx, ty = fx - x0, fy - y0
    h00 = height[y0, x0]
    h10 = height[y0, x0 + 1]
    h01 = height[y0 + 1, x0]
    h11 = height[y0 + 1, x0 + 1]
    return (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty


# --------------------------------------------------------------------------
# Capture zones, spawns, and prop placement
# --------------------------------------------------------------------------

ZONES = [
    ("A", -55.0, -45.0, 11.0, "ranger"),
    ("B", -24.0,  27.0, 11.0, "neutral"),
    ("C",   0.0,   1.0, 12.0, "neutral"),
    ("D",  31.0, -26.0, 11.0, "neutral"),
    ("E",  55.0,  47.0, 11.0, "legion"),
]

#: zone id -> building kind. Every capture point needs its own silhouette or
#: they are indistinguishable once you are inside one.
ZONE_BUILDINGS = {
    "A": "bunker",
    "B": "watchtower",
    "C": "ruin",
    "D": "bunker",
    "E": "watchtower",
}


SPAWNS = {
    "ranger": [(-70 + i % 4 * 4.0, -70 + i // 4 * 4.0) for i in range(16)],
    "legion": [(70 - i % 4 * 4.0, 70 - i // 4 * 4.0) for i in range(16)],
}


def sandbag_emplacements():
    """Sandbag positions: rings around each capture zone plus trench firing bays."""
    placements = []
    for name, cx, cy, radius, _owner in ZONES:
        count = 7 if name == "C" else 5
        for index in range(count):
            angle = (index / count) * math.tau + (0.4 if name in "BD" else 0.0)
            distance = radius * 0.78
            x = cx + math.cos(angle) * distance
            y = cy + math.sin(angle) * distance
            placements.append({
                "kind": "sandbag_wall",
                "x": x, "y": y,
                "yaw": angle + math.pi * 0.5,
                "zone": name,
            })
    for _name, points, _depth, _width in TRENCHES:
        for index in range(1, len(points) - 1):
            x, y = points[index]
            nx = points[index + 1][0] - points[index - 1][0]
            ny = points[index + 1][1] - points[index - 1][1]
            yaw = math.atan2(ny, nx)
            placements.append({
                "kind": "sandbag_stack", "x": x, "y": y, "yaw": yaw, "zone": ""
            })
    return placements


def rock_scatter(xs, ys, height, count=190, seed=SEED):
    """Scatter boulders, avoiding trenches, zones and spawn areas."""
    generator = np.random.default_rng(seed + 31)
    trench_points = [np.asarray(points, dtype=float) for _n, points, _d, _w in TRENCHES]

    placements = []
    attempts = 0
    while len(placements) < count and attempts < count * 60:
        attempts += 1
        x = generator.uniform(-MAP_SIZE * 0.46, MAP_SIZE * 0.46)
        y = generator.uniform(-MAP_SIZE * 0.46, MAP_SIZE * 0.46)

        too_close = False
        for points in trench_points:
            grid_x = np.array([[x]])
            grid_y = np.array([[y]])
            if _polyline_distance(grid_x, grid_y, points.tolist())[0, 0] < 4.5:
                too_close = True
                break
        if too_close:
            continue
        if any(math.hypot(x - bx, y - by) < BASE_FLAT_RADIUS + 4 for bx, by in BASES.values()):
            continue
        if any(math.hypot(x - zx, y - zy) < 6.0 for _n, zx, zy, _r, _o in ZONES):
            continue

        # Boulders cluster on the outcrops, which is where cover should be.
        near_outcrop = min(math.hypot(x - ox, y - oy) for ox, oy, _a, _r in OUTCROPS)
        if near_outcrop > 16.0 and generator.random() > 0.35:
            continue

        variant = int(generator.integers(0, 5))
        scale = float(generator.uniform(0.7, 2.3))
        if near_outcrop < 12.0:
            scale *= 1.25
        placements.append({
            "kind": "rock", "variant": variant,
            "x": float(x), "y": float(y),
            "z": float(sample_height(xs, ys, height, x, y)) - 0.35 * scale,
            "yaw": float(generator.uniform(0, math.tau)),
            "pitch": float(generator.uniform(-0.14, 0.14)),
            "scale": scale,
        })
    return placements


def vegetation_scatter(xs, ys, height, seed=SEED):
    """Scatter trees, bushes and grass.

    Trees avoid the trenches, the capture zones and the spawn aprons: a tree
    growing out of a firing bay reads as a bug, and one standing on a flag
    blocks the fight the zone exists to create. They cluster on the lower,
    gentler ground where trees would actually take hold.
    """
    from noise_shim import fbm_2d

    generator = np.random.default_rng(seed + 613)
    trench_points = [points for _n, points, _d, _w in TRENCHES]
    step = xs[0, 1] - xs[0, 0]
    gy, gx = np.gradient(height, step)
    slope_field = np.sqrt(gx ** 2 + gy ** 2)

    def slope_at(x, y):
        axis = xs[0]
        ix = int(np.clip((x - axis[0]) / step, 0, xs.shape[1] - 1))
        iy = int(np.clip((y - axis[0]) / step, 0, xs.shape[0] - 1))
        return float(slope_field[iy, ix])

    placements = []
    targets = {"tree": 260, "bush": 300, "grass": 900}
    counts = {"tree": 0, "bush": 0, "grass": 0}

    attempts = 0
    while sum(counts.values()) < sum(targets.values()) and attempts < 60000:
        attempts += 1
        kind = ("tree" if counts["tree"] < targets["tree"]
                else "bush" if counts["bush"] < targets["bush"] else "grass")

        x = generator.uniform(-MAP_SIZE * 0.47, MAP_SIZE * 0.47)
        y = generator.uniform(-MAP_SIZE * 0.47, MAP_SIZE * 0.47)

        clearance = {"tree": 6.0, "bush": 3.0, "grass": 1.6}[kind]
        blocked = False
        for points in trench_points:
            if _polyline_distance(np.array([[x]]), np.array([[y]]), points)[0, 0] < clearance:
                blocked = True
                break
        if blocked:
            continue
        if any(math.hypot(x - zx, y - zy) < (10.0 if kind == "tree" else 4.0)
               for _n, zx, zy, _r, _o in ZONES):
            continue
        if any(math.hypot(x - bx, y - by) < BASE_FLAT_RADIUS * (1.0 if kind == "tree" else 0.7)
               for bx, by in BASES.values()):
            continue

        slope = slope_at(x, y)
        if kind == "tree" and slope > 0.55:
            continue
        if kind != "grass" and slope > 0.95:
            continue

        # Woodland grows in stands, not on a uniform grid.
        density = fbm_2d(np.array([x]), np.array([y]), frequency=0.017, octaves=3,
                         seed=seed + 811)[0]
        threshold = {"tree": 0.52, "bush": 0.44, "grass": 0.32}[kind]
        if density < threshold and generator.random() > 0.18:
            continue

        variant = int(generator.integers(0, 3 if kind == "tree" else 2))
        scale = float(generator.uniform(0.75, 1.35) if kind == "tree"
                      else generator.uniform(0.7, 1.4))
        placements.append({
            "kind": kind, "variant": variant,
            "x": float(x), "y": float(y),
            "z": float(sample_height(xs, ys, height, x, y)) - 0.08,
            "yaw": float(generator.uniform(0, math.tau)),
            "scale": scale,
        })
        counts[kind] += 1

    return placements, counts


def prop_scatter(xs, ys, height, seed=SEED):
    """Crates, barrels and antennae — objective dressing, not random litter."""
    generator = np.random.default_rng(seed + 77)
    placements = []
    for name, cx, cy, radius, _owner in ZONES:
        for index in range(4):
            angle = generator.uniform(0, math.tau)
            distance = generator.uniform(2.0, radius * 0.6)
            x, y = cx + math.cos(angle) * distance, cy + math.sin(angle) * distance
            kind = ["crate", "crate", "barrel", "ammo_box"][index]
            placements.append({
                "kind": kind, "x": float(x), "y": float(y),
                "z": float(sample_height(xs, ys, height, x, y)),
                "yaw": float(generator.uniform(0, math.tau)), "zone": name,
            })
        placements.append({
            "kind": "capture_mast", "x": float(cx), "y": float(cy),
            "z": float(sample_height(xs, ys, height, cx, cy)),
            "yaw": 0.0, "zone": name,
        })
        building = ZONE_BUILDINGS.get(name)
        if building is not None:
            angle = generator.uniform(0, math.tau)
            bx = cx + math.cos(angle) * radius * 0.62
            by = cy + math.sin(angle) * radius * 0.62
            placements.append({
                "kind": building, "x": float(bx), "y": float(by),
                "z": float(sample_height(xs, ys, height, bx, by)) - 0.15,
                "yaw": float(generator.uniform(0, math.tau)), "zone": name,
            })
    return placements


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def _to_godot(x, y, z):
    """Blender (X right, Y forward, Z up) -> Godot (X right, Y up, Z back)."""
    return [round(float(x), 3), round(float(z), 3), round(float(-y), 3)]


def export_json(path=None):
    from noise_shim import fbm_2d  # noqa: F401  (import check before heavy work)

    xs, ys, height = build_terrain()

    vegetation, veg_counts = vegetation_scatter(xs, ys, height)

    trench_modules = []
    for name, points, depth, width in TRENCHES:
        for index in range(len(points) - 1):
            (x0, y0), (x1, y1) = points[index], points[index + 1]
            length = math.hypot(x1 - x0, y1 - y0)
            yaw = math.atan2(y1 - y0, x1 - x0)
            steps = max(1, int(round(length / 4.0)))
            for step in range(steps):
                t = (step + 0.5) / steps
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                trench_modules.append({
                    "kind": "trench_straight",
                    "line": name,
                    "position": _to_godot(x, y, sample_height(xs, ys, height, x, y) + depth),
                    "yaw": round(-yaw, 4),
                    "length": round(length / steps, 3),
                })

    data = {
        "map": "ridgeline",
        "size": MAP_SIZE,
        "grid": GRID,
        "seed": SEED,
        "coordinate_note": "positions are Godot-space (Y up, Z = -Blender Y)",
        "zones": [
            {
                "id": name, "radius": radius, "owner": owner,
                "position": _to_godot(x, y, sample_height(xs, ys, height, x, y)),
            }
            for name, x, y, radius, owner in ZONES
        ],
        "spawns": {
            team: [_to_godot(x, y, sample_height(xs, ys, height, x, y) + 0.1)
                   for x, y in points]
            for team, points in SPAWNS.items()
        },
        "trench_modules": trench_modules,
        "sandbags": [
            {
                "kind": item["kind"],
                "position": _to_godot(item["x"], item["y"],
                                      sample_height(xs, ys, height, item["x"], item["y"])),
                "yaw": round(-item["yaw"], 4),
                "zone": item["zone"],
            }
            for item in sandbag_emplacements()
        ],
        "rocks": [
            {
                "variant": item["variant"],
                "position": _to_godot(item["x"], item["y"], item["z"]),
                "yaw": round(-item["yaw"], 4),
                "pitch": round(item["pitch"], 4),
                "scale": round(item["scale"], 3),
            }
            for item in rock_scatter(xs, ys, height)
        ],
        "vegetation": [
            {
                "kind": item["kind"], "variant": item["variant"],
                "position": _to_godot(item["x"], item["y"], item["z"]),
                "yaw": round(-item["yaw"], 4),
                "scale": round(item["scale"], 3),
            }
            for item in vegetation
        ],
        "props": [
            {
                "kind": item["kind"],
                "position": _to_godot(item["x"], item["y"], item["z"]),
                "yaw": round(-item["yaw"], 4),
                "zone": item["zone"],
            }
            for item in prop_scatter(xs, ys, height)
        ],
    }

    path = path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "map",
        "layout.json")
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(data, handle, indent=1)

    print(f"  layout: {len(data['zones'])} zones, {len(trench_modules)} trench modules, "
          f"{len(data['sandbags'])} sandbag sets, {len(data['rocks'])} rocks, "
          f"{len(data['props'])} props")
    print(f"  vegetation: {veg_counts['tree']} trees, {veg_counts['bush']} bushes, "
          f"{veg_counts['grass']} grass tufts")
    print(f"  terrain height range {height.min():.1f} .. {height.max():.1f} m")
    return data

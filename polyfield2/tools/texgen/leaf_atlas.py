"""Generate the foliage card atlas.

    blender -b --python leaf_atlas.py

This one map stays procedural rather than downloaded: cutout foliage needs a
clean alpha channel laid out to a known grid, and the CC0 texture libraries
this project pulls from ship tiling surfaces, not alpha-masked leaf atlases.
Bark, ground and everything else still comes from ambientCG.

Output is a 4x4 grid, one *family* per row, because a conifer that samples a
broadleaf sprig reads as a broadleaf no matter how its branches are arranged.
The tree generator picks its row by species:

    row 0   broadleaf sprigs    oak, birch
    row 1   needle sprays       pine, fir
    row 2   dry scrub twigs     scrub, bushes
    row 3   grass blades        tufts

    leaf_albedo.png  RGBA, alpha is the cutout mask
    leaf_orm.png     R = AO, G = roughness, B = metallic

UV note: v = 0 is the *top* of the image here, matching Godot's convention, so
image row block r corresponds to the v range [r/4, (r+1)/4]. The tree generator
relies on that mapping; changing one without the other silently swaps foliage
families between species.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import noiselib as nl
from pngio import write_png

OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "textures")

GRID = 4

#: family name -> row index in the atlas. The tree generator imports the same
#: mapping by value; both must agree or species get the wrong foliage.
ROWS = {"broad": 0, "needle": 1, "scrub": 2, "grass": 3}


def _grid(size):
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    return x / size, y / size


def _blob(x, y, cx, cy, angle, length, width):
    """Signed coverage of one rotated ellipse, 1 at the centre and 0 outside."""
    ca, sa = np.cos(angle), np.sin(angle)
    dx, dy = x - cx, y - cy
    u = dx * ca + dy * sa
    v = -dx * sa + dy * ca
    return np.clip(1.0 - ((u / width) ** 2 + (v / length) ** 2), 0.0, 1.0), v


def _stem(x, y, thickness=90.0, wobble=0.06, top=0.95, bottom=0.05):
    line = np.clip(1.0 - np.abs(x - (0.5 + np.sin(y * 2.4) * wobble)) * thickness, 0.0, 1.0)
    return line * ((y > bottom) & (y < top)).astype(np.float64)


def _broadleaf(size, seed, count=13, length=0.16, width=0.055, spread=0.11):
    """Alternating oval leaves along a gently curving stem."""
    generator = np.random.default_rng(seed)
    x, y = _grid(size)
    mask = np.zeros((size, size))
    shade = np.zeros((size, size))

    for index in range(count):
        t = (index + 0.5) / count
        side = 1.0 if index % 2 == 0 else -1.0
        cx = 0.5 + np.sin(t * 2.4) * 0.06 + side * spread * (0.35 + 0.65 * t) \
            * generator.uniform(0.7, 1.0)
        cy = 0.08 + t * 0.84
        angle = side * generator.uniform(0.5, 1.1) + generator.uniform(-0.15, 0.15)

        leaf, v = _blob(x, y, cx, cy, angle,
                        length * generator.uniform(0.8, 1.15),
                        width * generator.uniform(0.8, 1.15))
        hit = leaf > 0.02
        mask = np.maximum(mask, hit.astype(np.float64))
        # Lighter towards the leaf tip, darker along the midrib.
        shade = np.where(hit, np.clip(0.45 + leaf * 0.5 - np.abs(v) * 3.0, 0.0, 1.0), shade)

    stem = _stem(x, y)
    mask = np.maximum(mask, (stem > 0.15).astype(np.float64))
    shade = np.where(stem > 0.15, 0.30, shade)
    return mask, shade


def _needle(size, seed, pairs=34, length=0.115, width=0.0075, rake=0.62):
    """A flat needle spray: many fine needles raked forward off a woody shoot.

    Needles are drawn as very narrow ellipses rather than as lines so they keep
    a soft tip when the atlas is mipped down — a hard-edged line turns into a
    dotted stipple two mip levels in, which is what makes cheap conifers
    sparkle when the camera moves.
    """
    generator = np.random.default_rng(seed)
    x, y = _grid(size)
    mask = np.zeros((size, size))
    shade = np.zeros((size, size))

    for index in range(pairs):
        t = (index + 0.5) / pairs
        # The spray narrows towards the tip of the shoot.
        scale = 0.45 + 0.55 * (1.0 - t) ** 0.65
        for side in (-1.0, 1.0):
            angle = side * (rake + generator.uniform(-0.16, 0.16))
            reach = length * scale * generator.uniform(0.82, 1.18)
            cx = 0.5 + side * reach * 0.52
            cy = 0.06 + t * 0.88 - reach * 0.30

            needle, v = _blob(x, y, cx, cy, angle, reach, width * generator.uniform(0.8, 1.3))
            hit = needle > 0.015
            mask = np.maximum(mask, hit.astype(np.float64))
            shade = np.where(hit, np.clip(0.40 + needle * 0.55, 0.0, 1.0), shade)

    shoot = _stem(x, y, thickness=150.0, wobble=0.02, top=0.93)
    mask = np.maximum(mask, (shoot > 0.2).astype(np.float64))
    shade = np.where(shoot > 0.2, 0.26, shade)
    return mask, shade


def _scrub(size, seed, count=54, leaf=0.026):
    """Small round leaves on forked twigs — dry highland scrub, not a sapling."""
    generator = np.random.default_rng(size + seed)
    x, y = _grid(size)
    mask = np.zeros((size, size))
    shade = np.zeros((size, size))

    # Three twigs fanning from the base, leaves clustered along them.
    for twig in range(3):
        lean = (twig - 1) * 0.30 + generator.uniform(-0.06, 0.06)
        for index in range(count // 3):
            t = (index + 0.7) / (count / 3.0)
            cx = 0.5 + lean * t * 0.9 + generator.uniform(-0.05, 0.05)
            cy = 0.10 + t * 0.78
            radius = leaf * generator.uniform(0.65, 1.25) * (1.15 - 0.4 * t)

            blob, v = _blob(x, y, cx, cy, generator.uniform(0, 3.14), radius, radius * 0.85)
            hit = blob > 0.02
            mask = np.maximum(mask, hit.astype(np.float64))
            shade = np.where(hit, np.clip(0.42 + blob * 0.5, 0.0, 1.0), shade)

        twig_line = np.clip(
            1.0 - np.abs(x - (0.5 + lean * np.clip((y - 0.1) / 0.78, 0, 1) * 0.9)) * 190.0,
            0.0, 1.0) * ((y > 0.06) & (y < 0.90)).astype(np.float64)
        mask = np.maximum(mask, (twig_line > 0.2).astype(np.float64))
        shade = np.where(twig_line > 0.2, 0.24, shade)

    return mask, shade


def _grass(size, seed, blades=9):
    """Tapered blades fanning from the bottom edge."""
    generator = np.random.default_rng(seed + 991)
    x, y = _grid(size)
    mask = np.zeros((size, size))
    shade = np.zeros((size, size))

    for index in range(blades):
        base = 0.5 + (index - (blades - 1) * 0.5) * generator.uniform(0.045, 0.085)
        lean = generator.uniform(-0.30, 0.30)
        top = generator.uniform(0.55, 0.98)
        thickness = generator.uniform(0.014, 0.024)

        # Blade bows over as it rises; width tapers to nothing at the tip.
        height = np.clip(y / max(top, 1e-3), 0.0, 1.0)
        centre = base + lean * height ** 1.7
        half = thickness * (1.0 - height) ** 0.7
        blade = (np.abs(x - centre) < np.maximum(half, 1e-4)) & (y < top) & (y > 0.01)

        mask = np.maximum(mask, blade.astype(np.float64))
        shade = np.where(blade, np.clip(0.35 + height * 0.6, 0.0, 1.0), shade)

    return mask, shade


#: family -> (builder, per-cell seed offsets). Four variants per row so a stand
#: of one species still varies card to card.
FAMILIES = {
    "broad": (_broadleaf, [11, 23, 37, 53]),
    "needle": (_needle, [67, 79, 91, 103]),
    "scrub": (_scrub, [113, 127, 139, 151]),
    "grass": (_grass, [163, 177, 191, 203]),
}

#: family -> (deep tone, lit tone, dry tone). Conifers are darker and bluer,
#: scrub is nearly straw. Colouring every family the same olive is the other
#: half of why the first pass read as one plant repeated.
PALETTE = {
    "broad": ((0.16, 0.24, 0.11), (0.40, 0.47, 0.20), (0.52, 0.47, 0.22)),
    "needle": ((0.09, 0.17, 0.12), (0.24, 0.35, 0.22), (0.33, 0.38, 0.24)),
    "scrub": ((0.20, 0.21, 0.11), (0.45, 0.44, 0.23), (0.58, 0.52, 0.30)),
    "grass": ((0.19, 0.25, 0.10), (0.46, 0.51, 0.22), (0.62, 0.57, 0.28)),
}


def build(size=1024):
    cell = size // GRID
    albedo = np.zeros((size, size, 4))
    orm = np.zeros((size, size, 3))

    for family, row in ROWS.items():
        builder, seeds = FAMILIES[family]
        dark, light, dry = (np.array(c) for c in PALETTE[family])

        for column, seed in enumerate(seeds):
            mask, shade = builder(cell, seed)
            veins = nl.fbm(cell, 26, 4, seed + 5)
            tone = nl.fbm(cell, 4, 3, seed + 9)

            colour = dark[None, None, :] + (light - dark)[None, None, :] * shade[..., None]
            colour = colour * (1.0 - tone[..., None] * 0.35) \
                + dry[None, None, :] * (tone[..., None] * 0.35)
            colour = np.clip(colour * (0.85 + veins[..., None] * 0.3), 0.0, 1.0)

            top = row * cell
            left = column * cell
            albedo[top:top + cell, left:left + cell, :3] = colour
            albedo[top:top + cell, left:left + cell, 3] = mask

            # Foliage is matte, and darker towards the base of a cluster.
            orm[top:top + cell, left:left + cell, 0] = np.clip(0.55 + shade * 0.45, 0.0, 1.0)
            orm[top:top + cell, left:left + cell, 1] = np.clip(0.80 + veins * 0.15, 0.0, 1.0)

    os.makedirs(OUT_DIR, exist_ok=True)
    write_png(os.path.join(OUT_DIR, "leaf_albedo.png"), albedo, srgb=True)
    write_png(os.path.join(OUT_DIR, "leaf_orm.png"), orm, srgb=False)

    print(f"  leaf atlas {size}px, {GRID}x{GRID} cells")
    for family, row in ROWS.items():
        band = albedo[row * cell:(row + 1) * cell, :, 3]
        print(f"    {family:<7} row {row}  alpha coverage {float((band > 0.5).mean()) * 100:5.1f}%")


if __name__ == "__main__":
    build()

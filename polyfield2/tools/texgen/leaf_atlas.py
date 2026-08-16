"""Generate the foliage card atlas.

    blender -b --python leaf_atlas.py

This one map stays procedural rather than downloaded: cutout foliage needs a
clean alpha channel laid out to a known grid, and the CC0 texture libraries
this project pulls from ship tiling surfaces, not alpha-masked leaf atlases.
Bark, ground and everything else still comes from ambientCG.

Output is a 2x2 grid of leaf clusters:
    leaf_albedo.png  RGBA, alpha is the cutout mask
    leaf_orm.png     R = AO, G = roughness, B = metallic
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import noiselib as nl
from pngio import write_png

OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "textures")


def _leaf_mask(size, seed, count, length, width, spread):
    """Scatter ellipse leaves along a stem, returning (mask, shade)."""
    generator = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    x /= size
    y /= size

    mask = np.zeros((size, size))
    shade = np.zeros((size, size))

    for index in range(count):
        t = (index + 0.5) / count
        # Leaves alternate either side of a stem that curves gently.
        side = 1.0 if index % 2 == 0 else -1.0
        stem_x = 0.5 + np.sin(t * 2.4) * 0.06
        cx = stem_x + side * spread * (0.35 + 0.65 * t) * generator.uniform(0.7, 1.0)
        cy = 0.08 + t * 0.84

        angle = side * generator.uniform(0.5, 1.1) + generator.uniform(-0.15, 0.15)
        ca, sa = np.cos(angle), np.sin(angle)
        dx, dy = x - cx, y - cy
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca

        radius = (u / (width * generator.uniform(0.8, 1.15))) ** 2 \
            + (v / (length * generator.uniform(0.8, 1.15))) ** 2
        leaf = np.clip(1.0 - radius, 0.0, 1.0)
        mask = np.maximum(mask, (leaf > 0.02).astype(np.float64))
        # Nearer the tip is lighter; the midrib is darker.
        shade = np.where(leaf > 0.02,
                         np.clip(0.45 + leaf * 0.5 - np.abs(v) * 3.0, 0.0, 1.0),
                         shade)

    # Stem
    stem = np.clip(1.0 - np.abs(x - (0.5 + np.sin(y * 2.4) * 0.06)) * 90.0, 0.0, 1.0)
    stem *= ((y > 0.05) & (y < 0.95)).astype(np.float64)
    mask = np.maximum(mask, (stem > 0.15).astype(np.float64))
    shade = np.where(stem > 0.15, 0.30, shade)

    return mask, shade


def build(size=512):
    cell = size // 2
    albedo = np.zeros((size, size, 4))
    orm = np.zeros((size, size, 3))

    variants = [
        (11, 13, 0.16, 0.055, 0.10),
        (23, 17, 0.13, 0.045, 0.13),
        (37, 11, 0.19, 0.062, 0.08),
        (53, 15, 0.15, 0.050, 0.115),
    ]

    for index, (seed, count, length, width, spread) in enumerate(variants):
        mask, shade = _leaf_mask(cell, seed, count, length, width, spread)
        veins = nl.fbm(cell, 26, 4, seed + 5)
        tone = nl.fbm(cell, 4, 3, seed + 9)

        # Highland foliage: dusty olive, not a lush garden green.
        dark = np.array([0.16, 0.24, 0.11])
        light = np.array([0.40, 0.47, 0.20])
        dry = np.array([0.52, 0.47, 0.22])
        colour = dark[None, None, :] + (light - dark)[None, None, :] * shade[..., None]
        colour = colour * (1.0 - tone[..., None] * 0.35) \
            + dry[None, None, :] * (tone[..., None] * 0.35)
        colour = np.clip(colour * (0.85 + veins[..., None] * 0.3), 0.0, 1.0)

        row = (index // 2) * cell
        col = (index % 2) * cell
        albedo[row:row + cell, col:col + cell, :3] = colour
        albedo[row:row + cell, col:col + cell, 3] = mask

        # Leaves are matte and self-shadowed towards the base of the cluster.
        ao = np.clip(0.55 + shade * 0.45, 0.0, 1.0)
        roughness = np.clip(0.80 + veins * 0.15, 0.0, 1.0)
        orm[row:row + cell, col:col + cell, 0] = ao
        orm[row:row + cell, col:col + cell, 1] = roughness

    os.makedirs(OUT_DIR, exist_ok=True)
    write_png(os.path.join(OUT_DIR, "leaf_albedo.png"), albedo, srgb=True)
    write_png(os.path.join(OUT_DIR, "leaf_orm.png"), orm, srgb=False)
    coverage = float((albedo[:, :, 3] > 0.5).mean())
    print(f"  leaf atlas {size}px, 4 clusters, alpha coverage {coverage * 100:.1f}%")


if __name__ == "__main__":
    build()

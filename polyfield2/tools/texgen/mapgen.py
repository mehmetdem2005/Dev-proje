"""Derive PBR map channels from a height field, and pack them for mobile."""

import numpy as np

from noiselib import blur, normalise


def height_to_normal(height: np.ndarray, strength: float = 1.0,
                     green_up: bool = True) -> np.ndarray:
    """Tangent-space normal map from a height field, encoded to [0, 1] RGB.

    `green_up=True` produces an OpenGL-style map (green channel points up),
    which is what Godot's BaseMaterial3D expects. The convention is verified
    against a real render by tools/verify/normal_convention.gd — do not flip
    this default without re-running that check.
    """
    # Sobel gradients with wrap-around so tiling stays seamless.
    def roll(a, dy, dx):
        return np.roll(np.roll(a, dy, axis=0), dx, axis=1)

    gx = (
        (roll(height, -1, -1) + 2.0 * roll(height, 0, -1) + roll(height, 1, -1))
        - (roll(height, -1, 1) + 2.0 * roll(height, 0, 1) + roll(height, 1, 1))
    )
    gy = (
        (roll(height, -1, -1) + 2.0 * roll(height, -1, 0) + roll(height, -1, 1))
        - (roll(height, 1, -1) + 2.0 * roll(height, 1, 0) + roll(height, 1, 1))
    )

    scale = strength * height.shape[0] / 256.0
    nx = -gx * scale
    ny = -gy * scale
    nz = np.ones_like(height)

    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length

    if not green_up:
        ny = -ny

    return np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5], axis=-1)


def height_to_ao(height: np.ndarray, radii=(2, 5, 11, 23), strength: float = 1.0,
                 floor: float = 0.35) -> np.ndarray:
    """Cheap multi-scale cavity/ambient-occlusion approximation.

    A texel is occluded when it sits below its own neighbourhood average.
    Summing several radii approximates occlusion at different scales, which
    reads far better than a single blur difference.
    """
    occlusion = np.zeros_like(height)
    for radius in radii:
        occlusion += np.clip(blur(height, radius) - height, 0.0, None)
    occlusion = normalise(occlusion) * strength
    return np.clip(1.0 - occlusion, floor, 1.0)


def height_to_curvature(height: np.ndarray, radius: int = 3) -> np.ndarray:
    """Signed curvature in [-1, 1]: positive on ridges, negative in cracks."""
    return np.clip((height - blur(height, radius)) * 8.0, -1.0, 1.0)


def pack_orm(ao: np.ndarray, roughness: np.ndarray, metallic: np.ndarray) -> np.ndarray:
    """Pack AO/Roughness/Metallic into one RGB texture.

    This is the layout Godot's ORMMaterial3D reads: R=AO, G=roughness,
    B=metallic. One sampler instead of three is a real win on mobile.
    """
    return np.stack([ao, roughness, metallic], axis=-1)


def tint(mask: np.ndarray, colour_a, colour_b) -> np.ndarray:
    """Blend two RGB colours by a [0, 1] mask."""
    a = np.asarray(colour_a, dtype=np.float64).reshape(1, 1, 3)
    b = np.asarray(colour_b, dtype=np.float64).reshape(1, 1, 3)
    m = mask[..., None]
    return a * (1.0 - m) + b * m


def srgb_from_hex(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return np.array([int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def overlay(base: np.ndarray, detail: np.ndarray, amount: float = 1.0) -> np.ndarray:
    """Photoshop-style overlay blend of a grayscale detail onto RGB."""
    d = detail[..., None]
    blended = np.where(base < 0.5, 2.0 * base * d, 1.0 - 2.0 * (1.0 - base) * (1.0 - d))
    return np.clip(base * (1.0 - amount) + blended * amount, 0.0, 1.0)


def contrast(a: np.ndarray, amount: float, pivot: float = 0.5) -> np.ndarray:
    return np.clip((a - pivot) * amount + pivot, 0.0, 1.0)


def remap(a: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return lo + normalise(a) * (hi - lo)

"""World-space value noise for terrain.

The texture pipeline's noise is tileable on a [0,1] square; terrain needs
noise evaluated at arbitrary world coordinates instead, so it gets its own
small hashed-lattice implementation. No dependency on the texgen package.
"""

import numpy as np

_MASK = np.int64(0x7FFFFFFFFFFF)


def _hash01(ix, iy, seed):
    """Deterministic [0, 1) value per integer lattice point."""
    h = (ix.astype(np.int64) * np.int64(374761393)
         + iy.astype(np.int64) * np.int64(668265263)
         + np.int64(seed) * np.int64(1442695041))
    h &= _MASK
    h = (h ^ (h >> np.int64(13))) * np.int64(1274126177)
    h &= _MASK
    h = h ^ (h >> np.int64(16))
    return (h & np.int64(0xFFFFFF)).astype(np.float64) / float(0x1000000)


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def value_noise_2d(xs, ys, seed=0):
    x0 = np.floor(xs)
    y0 = np.floor(ys)
    fx = _fade(xs - x0)
    fy = _fade(ys - y0)
    ix = x0.astype(np.int64)
    iy = y0.astype(np.int64)

    c00 = _hash01(ix, iy, seed)
    c10 = _hash01(ix + 1, iy, seed)
    c01 = _hash01(ix, iy + 1, seed)
    c11 = _hash01(ix + 1, iy + 1, seed)

    top = c00 + (c10 - c00) * fx
    bottom = c01 + (c11 - c01) * fx
    return top + (bottom - top) * fy


def fbm_2d(xs, ys, frequency=0.02, octaves=4, seed=0, gain=0.5, lacunarity=2.0):
    """Fractal value noise in [0, 1] evaluated at world coordinates."""
    total = np.zeros_like(np.asarray(xs, dtype=np.float64))
    amplitude, weight, current = 1.0, 0.0, frequency
    for octave in range(octaves):
        total += value_noise_2d(xs * current, ys * current, seed + octave * 131) * amplitude
        weight += amplitude
        amplitude *= gain
        current *= lacunarity
    return total / weight


def ridged_2d(xs, ys, frequency=0.02, octaves=4, seed=0):
    """Ridged variant — sharp crests, used for rock outcrop silhouettes."""
    total = np.zeros_like(np.asarray(xs, dtype=np.float64))
    amplitude, weight, current = 1.0, 0.0, frequency
    for octave in range(octaves):
        n = value_noise_2d(xs * current, ys * current, seed + octave * 197)
        total += (1.0 - np.abs(n * 2.0 - 1.0)) * amplitude
        weight += amplitude
        amplitude *= 0.5
        current *= 2.0
    return total / weight

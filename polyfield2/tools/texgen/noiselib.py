"""Tileable procedural noise primitives.

Everything here wraps seamlessly at the texture border: lattice indices are
taken modulo the grid size and Worley distances are measured with wrap-around.
That matters because every material we generate is used on tiled geometry.
"""

import numpy as np


def _smoothstep(t: np.ndarray) -> np.ndarray:
    # Quintic fade — C2 continuous, avoids the visible creases of the cubic one.
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _uv(size: int) -> tuple:
    axis = np.arange(size, dtype=np.float64) / float(size)
    return np.meshgrid(axis, axis, indexing="xy")


def value_noise(size: int, grid: int, seed: int) -> np.ndarray:
    """Tileable value noise in [0, 1] on a `grid` x `grid` lattice."""
    rng = np.random.default_rng(seed)
    lattice = rng.random((grid, grid))

    u, v = _uv(size)
    x, y = u * grid, v * grid
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = _smoothstep(x - x0), _smoothstep(y - y0)

    x0m, y0m = x0 % grid, y0 % grid
    x1m, y1m = (x0 + 1) % grid, (y0 + 1) % grid

    c00 = lattice[y0m, x0m]
    c10 = lattice[y0m, x1m]
    c01 = lattice[y1m, x0m]
    c11 = lattice[y1m, x1m]

    top = c00 + (c10 - c00) * fx
    bottom = c01 + (c11 - c01) * fx
    return top + (bottom - top) * fy


def fbm(size: int, grid: int, octaves: int, seed: int, gain: float = 0.5,
        lacunarity: int = 2) -> np.ndarray:
    """Fractal sum of value noise, normalised to [0, 1]."""
    total = np.zeros((size, size), dtype=np.float64)
    amplitude, weight, current = 1.0, 0.0, grid
    for octave in range(octaves):
        total += value_noise(size, max(1, current), seed + octave * 977) * amplitude
        weight += amplitude
        amplitude *= gain
        current *= lacunarity
    return total / weight


def ridged(size: int, grid: int, octaves: int, seed: int) -> np.ndarray:
    """Ridged multifractal — sharp creases, good for rock and cliff strata."""
    total = np.zeros((size, size), dtype=np.float64)
    amplitude, weight, current = 1.0, 0.0, grid
    for octave in range(octaves):
        n = value_noise(size, max(1, current), seed + octave * 613)
        total += (1.0 - np.abs(n * 2.0 - 1.0)) * amplitude
        weight += amplitude
        amplitude *= 0.5
        current *= 2
    return normalise(total / weight)


def _worley_f1f2(size: int, cells: int, seed: int):
    """Return the two nearest feature-point distances, in cell units.

    Only the 3x3 cell neighbourhood is searched, which is exact for one
    jittered point per cell and turns an O(pixels x points) scan into a
    fixed nine-candidate one. Wrap-around comes for free from doing the
    arithmetic in absolute cell coordinates on a torus of period `cells`.
    """
    rng = np.random.default_rng(seed)
    jitter = rng.random((cells, cells, 2))

    u, v = _uv(size)
    px, py = u * cells, v * cells
    cx0 = np.floor(px).astype(np.int64)
    cy0 = np.floor(py).astype(np.int64)

    f1 = np.full((size, size), 1e9)
    f2 = np.full((size, size), 1e9)

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cx, cy = cx0 + dx, cy0 + dy
            jx = jitter[cy % cells, cx % cells, 0]
            jy = jitter[cy % cells, cx % cells, 1]
            dist = np.sqrt((cx + jx - px) ** 2 + (cy + jy - py) ** 2)
            closer = dist < f1
            f2 = np.where(closer, f1, np.minimum(f2, dist))
            f1 = np.where(closer, dist, f1)

    return f1, f2


def worley(size: int, cells: int, seed: int, feature: int = 0) -> np.ndarray:
    """Tileable Worley/cellular noise, normalised to [0, 1].

    `feature` 0 is the distance to the nearest point, 1 the second nearest.
    """
    f1, f2 = _worley_f1f2(size, cells, seed)
    return normalise(f1 if feature == 0 else f2)


def worley_edges(size: int, cells: int, seed: int, sharpness: float = 6.0) -> np.ndarray:
    """Thin cell-border network: 1 on the crack, 0 inside the cell.

    F2 - F1 approaches zero exactly on the boundary between two cells, which
    is what makes this read as fractures in stone rather than as blobs.
    """
    f1, f2 = _worley_f1f2(size, cells, seed)
    return np.clip(1.0 - (f2 - f1) * sharpness, 0.0, 1.0)


def normalise(a: np.ndarray) -> np.ndarray:
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-9:
        return np.zeros_like(a)
    return (a - lo) / (hi - lo)


def blur(a: np.ndarray, radius: int) -> np.ndarray:
    """Separable box blur with wrap-around edges."""
    if radius <= 0:
        return a
    out = a
    for axis in (0, 1):
        acc = np.zeros_like(out)
        for offset in range(-radius, radius + 1):
            acc += np.roll(out, offset, axis=axis)
        out = acc / (2 * radius + 1)
    return out


def stripes(size: int, count: int, angle_deg: float, jitter: float = 0.0,
            seed: int = 0) -> np.ndarray:
    """Tileable directional stripe field, used for planks and strata.

    `count` must be an integer number of repeats so the pattern still wraps.
    """
    u, v = _uv(size)
    angle = np.radians(angle_deg)
    # Integer frequency components keep the pattern seamless at any angle
    # that maps to whole repeats on both axes.
    fx = round(count * np.cos(angle))
    fy = round(count * np.sin(angle))
    phase = (u * fx + v * fy) * 2.0 * np.pi
    field = 0.5 + 0.5 * np.sin(phase)
    if jitter > 0.0:
        field = np.clip(field + (value_noise(size, 16, seed) - 0.5) * 2.0 * jitter, 0.0, 1.0)
    return field


def bricks(size: int, rows: int, cols: int, mortar: float = 0.06,
           offset: float = 0.5, seed: int = 0):
    """Tileable running-bond brick mask.

    Returns (mask, ids) where mask is 1 inside a brick and 0 in the mortar,
    and ids is a per-brick random value in [0, 1] for colour variation.
    """
    u, v = _uv(size)
    row = np.floor(v * rows)
    shifted = u + (row % 2) * (offset / cols)
    col = np.floor(shifted * cols)

    fu = (shifted * cols) % 1.0
    fv = (v * rows) % 1.0
    half = mortar * 0.5
    mask = ((fu > half) & (fu < 1.0 - half) & (fv > half) & (fv < 1.0 - half))

    rng = np.random.default_rng(seed)
    table = rng.random((rows + 1, cols + 1))
    ids = table[row.astype(np.int64) % rows, col.astype(np.int64) % cols]
    return mask.astype(np.float64), ids


def weave(size: int, threads: int, seed: int = 0) -> np.ndarray:
    """Over-under woven cloth height field — the base for burlap sandbags."""
    u, v = _uv(size)
    warp = 0.5 + 0.5 * np.sin(u * threads * 2.0 * np.pi)
    weft = 0.5 + 0.5 * np.sin(v * threads * 2.0 * np.pi)
    over = ((np.floor(u * threads) + np.floor(v * threads)) % 2).astype(bool)
    height = np.where(over, warp, weft)
    fuzz = value_noise(size, threads * 2, seed) * 0.25
    return normalise(height * 0.8 + fuzz)

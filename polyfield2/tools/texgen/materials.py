"""Material definitions.

Each generator returns a dict with a `height` field plus `albedo`, `roughness`,
`metallic` and `ao`. build_textures.py turns those into the PNG map set.

Every material is authored to tile seamlessly and to stay inside the palette
laid out in docs/polyfield2/01-sanat-yonetimi.md.
"""

import numpy as np

import noiselib as nl
import mapgen as mg

HEX = mg.srgb_from_hex


def _mix(a, b, mask):
    """Blend RGB `a` -> `b` by a [0, 1] mask."""
    return a * (1.0 - mask[..., None]) + b * mask[..., None]


def _rgb(colour, size):
    return np.broadcast_to(np.asarray(colour).reshape(1, 1, 3), (size, size, 3)).copy()


# --------------------------------------------------------------------------
# Terrain and nature
# --------------------------------------------------------------------------

def rock_granite(size, seed=11):
    """Weathered highland granite — the signature surface of the whole map.

    Built from a fracture network rather than blobs: F2-F1 cell borders give
    thin cracks, and a high-frequency speckle supplies the mica/quartz grain
    that makes stone read as stone up close.
    """
    blocks = nl.worley(size, 9, seed, feature=0)
    big_cracks = nl.worley_edges(size, 9, seed, sharpness=7.0)
    fine_cracks = nl.worley_edges(size, 23, seed + 1, sharpness=11.0)
    speckle = nl.value_noise(size, 190, seed + 2)
    grain = nl.fbm(size, 18, 5, seed + 3)

    height = nl.normalise(
        blocks * 0.42 + grain * 0.28 + speckle * 0.12
        - big_cracks * 0.55 - fine_cracks * 0.22
    )
    height = mg.contrast(height, 1.25)

    crack_mask = np.clip(big_cracks * 0.9 + fine_cracks * 0.55, 0.0, 1.0)
    mica = np.clip((0.34 - speckle) * 6.0, 0.0, 1.0)
    quartz = np.clip((speckle - 0.74) * 6.0, 0.0, 1.0)
    lichen = np.clip(nl.fbm(size, 5, 4, seed + 7) * 2.0 - 0.95, 0.0, 1.0) ** 2.0

    base = _mix(_rgb(HEX("6E6E6B"), size), _rgb(HEX("9A9A94"), size), grain)
    base = _mix(base, _rgb(HEX("3E3D3A"), size), mica * 0.8)
    base = _mix(base, _rgb(HEX("C4C2BA"), size), quartz * 0.7)
    base = _mix(base, _rgb(HEX("46443F"), size), crack_mask * 0.9)
    base = _mix(base, _rgb(HEX("6F7A52"), size), lichen * 0.6)
    albedo = mg.contrast(base, 1.15)

    roughness = np.clip(0.7 + grain * 0.18 + crack_mask * 0.1 - quartz * 0.15, 0.4, 0.98)
    ao = mg.height_to_ao(height, strength=1.1, floor=0.3)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


def cliff_strata(size, seed=23):
    """Layered sedimentary cliff face — reads as height even at a distance.

    The bands are warped by low-frequency noise before being cut into
    discrete beds, so no two strata have the same thickness. Even ruled
    stripes look like corduroy on a cliff; the irregularity is the point.
    """
    layer_count = 11
    u, v = np.meshgrid(np.linspace(0.0, 1.0, size, endpoint=False),
                       np.linspace(0.0, 1.0, size, endpoint=False), indexing="xy")

    warp = (nl.fbm(size, 5, 4, seed) - 0.5) * 2.2
    t = v * layer_count + warp
    bed = np.floor(t).astype(np.int64) % layer_count
    within = t - np.floor(t)

    rng = np.random.default_rng(seed + 100)
    hardness = rng.random(layer_count)          # resistant beds jut out
    tone = rng.random(layer_count)

    bed_hardness = hardness[bed]
    # Ledge profile: each bed recedes upward, resistant beds recede less.
    shelf = (1.0 - within) ** (0.4 + bed_hardness * 1.4)

    erosion = nl.ridged(size, 6, 5, seed + 3)
    runnels = nl.stripes(size, 40, 90.0, jitter=0.7, seed=seed + 4)
    detail = nl.fbm(size, 28, 4, seed + 5)
    spall = nl.worley_edges(size, 13, seed + 6, sharpness=6.0)

    # The beds must dominate: erosion and spalling only decorate them,
    # otherwise the fracture network eats the layering entirely.
    bedding = np.clip(1.0 - np.abs(within - 0.5) * 5.0, 0.0, 1.0)   # dark recess line
    height = nl.normalise(
        shelf * (0.55 + bed_hardness * 0.45) + erosion * 0.12
        + runnels * 0.06 + detail * 0.08 - spall * 0.10 - bedding * 0.3
    )

    bed_tone = tone[bed]
    base = _mix(_rgb(HEX("60564A"), size), _rgb(HEX("B0A692"), size), bed_tone)
    base = _mix(base, _rgb(HEX("8A7C63"), size), bed_hardness * 0.4)
    base = _mix(base, _rgb(HEX("3A342C"), size), bedding * 0.7)
    base = _mix(base, _rgb(HEX("4C443A"), size),
                np.clip(1.0 - height * 1.9, 0.0, 1.0) * 0.5)
    base = _mix(base, _rgb(HEX("3F3830"), size), spall * 0.25)
    base = mg.overlay(base, detail, 0.22)
    albedo = mg.contrast(base, 1.12)

    roughness = np.clip(0.68 + detail * 0.22 + spall * 0.08, 0.45, 0.98)
    ao = mg.height_to_ao(height, radii=(3, 7, 15, 31), strength=1.15, floor=0.25)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


def ground_rocky(size, seed=31):
    """Gravel and scree over packed dirt — the walkable ground of the ridge."""
    # Two stone scales, each revealed only where a low-frequency coverage mask
    # allows. Uniform cellular noise across the whole sheet reads as scales,
    # not as scree — the patchiness is what sells it as loose ground.
    coverage = nl.fbm(size, 4, 4, seed + 9)
    coarse_patch = np.clip((coverage - 0.52) * 5.0, 0.0, 1.0)
    fine_patch = np.clip((0.55 - coverage) * 5.0, 0.0, 1.0)

    coarse = 1.0 - nl.worley(size, 18, seed, feature=0)
    coarse_gaps = nl.worley_edges(size, 18, seed, sharpness=8.0)
    fine = 1.0 - nl.worley(size, 44, seed + 1, feature=0)
    fine_gaps = nl.worley_edges(size, 44, seed + 1, sharpness=12.0)
    dirt = nl.fbm(size, 7, 6, seed + 2)
    silt = nl.value_noise(size, 160, seed + 5)

    stones = coarse ** 1.5 * coarse_patch + fine ** 1.8 * fine_patch * 0.7
    gaps = coarse_gaps * coarse_patch + fine_gaps * fine_patch

    height = nl.normalise(stones * 0.55 + dirt * 0.32 + silt * 0.08 - gaps * 0.3)

    stone_mask = np.clip(stones * 2.2 - 0.35, 0.0, 1.0) * (1.0 - gaps * 0.8)
    tone = nl.value_noise(size, 22, seed + 11)
    base = _mix(_rgb(HEX("5E5341"), size), _rgb(HEX("8A7B5C"), size), dirt)
    base = _mix(base, _rgb(HEX("5A5044"), size), gaps * 0.30)
    base = _mix(base, _mix(_rgb(HEX("7D7970"), size), _rgb(HEX("A29E93"), size), tone),
                stone_mask * 0.85)
    base = mg.overlay(base, silt, 0.16)
    albedo = mg.contrast(base, 1.02)

    roughness = np.clip(0.88 - stone_mask * 0.14, 0.6, 0.99)
    ao = mg.height_to_ao(height, strength=1.0, floor=0.38)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


def grass_highland(size, seed=41):
    """Sparse dry highland grass, tinted so it never fights the team colours."""
    # A single stripe field makes grass read as corduroy. Three fields at
    # different angles, each revealed by its own low-frequency mask, break
    # the global direction so tufts point different ways across the sheet.
    directions = ((110, 0.0), (74, 1.0), (92, 2.0))
    blades = np.zeros((size, size))
    weight = np.zeros((size, size))
    for index, (angle, offset) in enumerate(directions):
        field = nl.stripes(size, 120, angle, jitter=0.5, seed=seed + index * 31)
        mask = np.clip(nl.fbm(size, 5, 3, seed + 200 + index * 17) * 1.8 - 0.35 + offset * 0.0,
                       0.0, 1.0)
        blades += field * mask
        weight += mask
    blades = blades / np.maximum(weight, 1e-6)

    clumps = 1.0 - nl.worley(size, 16, seed + 3, feature=0)
    patchiness = nl.fbm(size, 6, 5, seed + 1)
    fine = nl.value_noise(size, 150, seed + 2)

    height = nl.normalise(blades * 0.3 + clumps ** 1.5 * 0.35 + patchiness * 0.25 + fine * 0.1)

    cover = np.clip(clumps * 1.2 + patchiness * 0.7 - 0.45, 0.0, 1.0)
    dryness = np.clip(patchiness * 1.5 - 0.2, 0.0, 1.0)
    clump_tone = nl.value_noise(size, 16, seed + 12)

    base = _mix(_rgb(HEX("4F6B3C"), size), _rgb(HEX("8B8B4E"), size), dryness)
    # Per-clump tone shift stops the field reading as one flat wash of green.
    base = _mix(base, _rgb(HEX("3E5730"), size), np.clip(1.0 - clump_tone * 1.8, 0.0, 1.0) * 0.5)
    base = _mix(base, _rgb(HEX("A39A5A"), size), np.clip(clump_tone * 1.6 - 0.8, 0.0, 1.0) * 0.5)
    # Individual blades: lit edge and shadowed side, both at full strength so
    # the strand structure survives into the albedo rather than only the normal.
    base = _mix(base, _rgb(HEX("B4AE6C"), size), np.clip((blades - 0.55) * 2.6, 0.0, 1.0) * 0.55)
    base = _mix(base, _rgb(HEX("2F4526"), size), np.clip((0.45 - blades) * 2.6, 0.0, 1.0) * 0.5)
    # Bare highland soil shows through wherever the cover mask thins out.
    base = _mix(base, _rgb(HEX("6B5F49"), size), np.clip(1.0 - cover * 2.2, 0.0, 1.0) * 0.75)
    albedo = mg.contrast(base, 1.1)

    roughness = np.clip(0.9 - blades * 0.06, 0.7, 0.99)
    ao = mg.height_to_ao(height, radii=(2, 4, 9), strength=0.85, floor=0.45)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


def soil_trench(size, seed=53):
    """Dark packed earth — trench walls, dugouts, crater interiors."""
    packed = nl.fbm(size, 5, 6, seed)
    tool = nl.stripes(size, 22, 70.0, jitter=0.5, seed=seed + 1)
    stones = 1.0 - nl.worley(size, 34, seed + 2, feature=0)

    height = nl.normalise(packed * 0.5 + tool * 0.2 + stones ** 2.0 * 0.3)

    stone_mask = np.clip((stones - 0.55) * 3.5, 0.0, 1.0)
    wet = np.clip(1.0 - packed * 1.8, 0.0, 1.0)
    base = _mix(_rgb(HEX("4A3C2C"), size), _rgb(HEX("6B5843"), size), packed)
    base = _mix(base, _rgb(HEX("8C8C88"), size), stone_mask * 0.6)
    base = _mix(base, _rgb(HEX("332A20"), size), wet * 0.5)
    albedo = mg.overlay(base, tool, 0.2)

    roughness = np.clip(0.88 - wet * 0.25, 0.55, 0.98)
    ao = mg.height_to_ao(height, strength=1.05, floor=0.3)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


# --------------------------------------------------------------------------
# Fortification materials
# --------------------------------------------------------------------------

def sandbag_burlap(size, seed=61):
    """Coarse burlap with a stitched seam and dirt wear at the base."""
    cloth = nl.weave(size, 34, seed)
    slump = nl.fbm(size, 4, 4, seed + 1)
    fibres = nl.stripes(size, 150, 8.0, jitter=0.6, seed=seed + 2)

    height = nl.normalise(cloth * 0.55 + slump * 0.3 + fibres * 0.15)

    dirt = np.clip(nl.fbm(size, 5, 5, seed + 4) * 1.6 - 0.35, 0.0, 1.0)
    base = _mix(_rgb(HEX("A08A5E"), size), _rgb(HEX("BFA974"), size), cloth)
    base = _mix(base, _rgb(HEX("5C4F3A"), size), dirt * 0.65)
    albedo = mg.overlay(base, fibres, 0.28)

    roughness = np.clip(0.92 - cloth * 0.06, 0.75, 0.99)
    ao = mg.height_to_ao(height, radii=(2, 5, 11), strength=1.0, floor=0.4)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


def wood_plank(size, seed=71):
    """Rough sawn revetment planks for trench walls and duckboards."""
    mask, ids = nl.bricks(size, 6, 1, mortar=0.05, offset=0.0, seed=seed)
    grain = nl.stripes(size, 130, 0.0, jitter=0.55, seed=seed + 1)
    knots = nl.worley(size, 7, seed + 2, feature=0)
    wear = nl.fbm(size, 9, 5, seed + 3)

    height = nl.normalise(mask * 0.45 + grain * 0.3 + (1.0 - knots) ** 3 * 0.1 + wear * 0.15)

    plank_tone = ids * 0.35 + 0.35
    base = _mix(_rgb(HEX("6E4F32"), size), _rgb(HEX("C8A374"), size), plank_tone)
    base = _mix(base, _rgb(HEX("3A2A1B"), size), (1.0 - mask) * 0.9)
    base = _mix(base, _rgb(HEX("4A3826"), size), np.clip(1.0 - knots * 2.5, 0.0, 1.0) * 0.7)
    albedo = mg.overlay(base, grain, 0.35)

    roughness = np.clip(0.82 + grain * 0.14, 0.6, 0.99)
    ao = mg.height_to_ao(height, strength=1.0, floor=0.35)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


def metal_corrugated(size, seed=83):
    """Corrugated steel sheeting with rust bloom — dugout roofs and shelters."""
    corrugation = nl.stripes(size, 16, 0.0)
    dents = nl.fbm(size, 10, 4, seed)
    scratches = nl.stripes(size, 200, 12.0, jitter=0.8, seed=seed + 1)

    height = nl.normalise(corrugation * 0.7 + dents * 0.22 + scratches * 0.08)

    rust = np.clip(nl.fbm(size, 6, 6, seed + 3) * 1.9 - 0.55, 0.0, 1.0)
    rust = rust ** 1.4
    base = _mix(_rgb(HEX("6E7377"), size), _rgb(HEX("9AA0A4"), size), corrugation)
    base = _mix(base, _rgb(HEX("7A4A34"), size), rust)
    albedo = mg.overlay(base, scratches, 0.18)

    metallic = np.clip(0.9 - rust * 0.85, 0.0, 1.0)
    roughness = np.clip(0.42 + rust * 0.45 + scratches * 0.06, 0.25, 0.95)
    ao = mg.height_to_ao(height, radii=(2, 5, 11), strength=0.8, floor=0.5)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=metallic, ao=ao)


def concrete_bunker(size, seed=97):
    """Board-formed concrete: form seams, tie-rod holes, pitting, rust streaks.

    Plain noise on grey reads as nothing at all. The recognisable features of
    poured concrete are the horizontal shutter seams and the tie-rod holes,
    so those are modelled explicitly and everything else decorates them.
    """
    u, v = np.meshgrid(np.linspace(0.0, 1.0, size, endpoint=False),
                       np.linspace(0.0, 1.0, size, endpoint=False), indexing="xy")

    # Shutter boards: 6 horizontal lifts, each with a recessed seam.
    board_rows = 6
    within = (v * board_rows) % 1.0
    seam = np.clip(1.0 - np.abs(within - 0.5) * 24.0, 0.0, 1.0)
    lift_id = np.floor(v * board_rows).astype(np.int64) % board_rows
    rng = np.random.default_rng(seed + 21)
    lift_tone = rng.random(board_rows)[lift_id]

    # Tie-rod holes on a staggered grid, only where the mask says so.
    hole_cols, hole_rows = 4, 6
    hu = (u * hole_cols) % 1.0
    hv = (v * hole_rows) % 1.0
    hole_d = np.sqrt((hu - 0.5) ** 2 + (hv - 0.5) ** 2)
    holes = np.clip(1.0 - hole_d * 14.0, 0.0, 1.0) ** 0.6
    keep = (rng.random((hole_rows, hole_cols))
            [np.floor(v * hole_rows).astype(np.int64) % hole_rows,
             np.floor(u * hole_cols).astype(np.int64) % hole_cols] > 0.35)
    holes = holes * keep

    pits = nl.worley_edges(size, 40, seed + 1, sharpness=14.0)
    blow = 1.0 - nl.worley(size, 26, seed + 4, feature=0)
    blowholes = np.clip((blow - 0.72) * 6.0, 0.0, 1.0)
    aggregate = nl.fbm(size, 22, 5, seed + 2)

    height = nl.normalise(
        aggregate * 0.35 + lift_tone * 0.08 - seam * 0.4 - holes * 0.55
        - pits * 0.12 - blowholes * 0.25
    )

    # Rust bleed runs downward from each tie-rod hole.
    bleed = np.clip(holes, 0.0, 1.0)
    for shift in range(1, 26):
        bleed = np.maximum(bleed, np.roll(holes, shift, axis=0) * (1.0 - shift / 26.0) * 0.8)
    bleed = bleed * np.clip(nl.fbm(size, 30, 3, seed + 8) * 1.4, 0.0, 1.0)

    stain = np.clip(nl.fbm(size, 4, 5, seed + 6) * 1.8 - 0.55, 0.0, 1.0)
    base = _mix(_rgb(HEX("9E9C94"), size), _rgb(HEX("B9B6AC"), size), aggregate)
    base = _mix(base, _rgb(HEX("ACA99F"), size), lift_tone * 0.4)
    base = _mix(base, _rgb(HEX("6E6B63"), size), stain * 0.6)
    base = _mix(base, _rgb(HEX("605D56"), size), seam * 0.65)
    base = _mix(base, _rgb(HEX("3E3B36"), size), holes * 0.85)
    base = _mix(base, _rgb(HEX("7A5238"), size), bleed * 0.5)
    base = _mix(base, _rgb(HEX("83807A"), size), blowholes * 0.5)
    base = mg.overlay(base, aggregate, 0.2)
    albedo = mg.contrast(base, 1.06)

    roughness = np.clip(0.8 + aggregate * 0.15 - stain * 0.1 + blowholes * 0.08, 0.55, 0.98)
    ao = mg.height_to_ao(height, strength=1.0, floor=0.38)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


def crate_wood(size, seed=103):
    """Supply crate boards with a painted band for readability at range."""
    mask, ids = nl.bricks(size, 5, 1, mortar=0.04, offset=0.0, seed=seed)
    grain = nl.stripes(size, 110, 0.0, jitter=0.5, seed=seed + 1)
    wear = nl.fbm(size, 12, 4, seed + 2)

    height = nl.normalise(mask * 0.5 + grain * 0.35 + wear * 0.15)

    u = np.linspace(0.0, 1.0, size, endpoint=False)[None, :].repeat(size, 0)
    band = ((u > 0.18) & (u < 0.30)).astype(np.float64)
    band = np.clip(band - wear * 0.5, 0.0, 1.0)

    base = _mix(_rgb(HEX("8A6A44"), size), _rgb(HEX("C8A374"), size), ids * 0.5 + 0.3)
    base = _mix(base, _rgb(HEX("35281A"), size), (1.0 - mask) * 0.85)
    base = _mix(base, _rgb(HEX("C9A227"), size), band * 0.85)
    albedo = mg.overlay(base, grain, 0.3)

    roughness = np.clip(0.84 + grain * 0.1, 0.6, 0.98)
    ao = mg.height_to_ao(height, strength=1.0, floor=0.38)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=np.zeros((size, size)), ao=ao)


# --------------------------------------------------------------------------
# Character and weapon materials
# --------------------------------------------------------------------------

def _uniform(size, seed, cloth_a, cloth_b, accent, webbing):
    """Shared uniform builder — only the palette differs between factions.

    UV layout expected by the character mesh (see gen_character.py):
      U 0.00-0.50  torso and arms (cloth)
      U 0.50-0.75  legs (cloth, darker)
      U 0.75-1.00  webbing, boots, helmet (accent + leather)
    """
    twill = nl.stripes(size, 180, 45.0, jitter=0.35, seed=seed)
    fold = nl.fbm(size, 8, 5, seed + 1)
    wear = nl.fbm(size, 14, 4, seed + 2)

    height = nl.normalise(twill * 0.35 + fold * 0.45 + wear * 0.2)

    u = np.linspace(0.0, 1.0, size, endpoint=False)[None, :].repeat(size, 0)
    legs = ((u >= 0.50) & (u < 0.75)).astype(np.float64)
    gear = (u >= 0.75).astype(np.float64)

    base = _mix(_rgb(cloth_a, size), _rgb(cloth_b, size), fold)
    base = _mix(base, _rgb(cloth_a, size) * 0.78, legs)
    base = _mix(base, _rgb(webbing, size), gear)

    # Accent stripe reads as the faction marker at silhouette distance.
    v = np.linspace(0.0, 1.0, size, endpoint=False)[:, None].repeat(size, 1)
    stripe = (((v > 0.06) & (v < 0.12)) & (u < 0.50)).astype(np.float64)
    base = _mix(base, _rgb(accent, size), stripe * 0.9)

    dirt = np.clip(wear * 1.7 - 0.6, 0.0, 1.0)
    base = _mix(base, _rgb(HEX("3E3529"), size), dirt * 0.45)
    albedo = mg.overlay(base, twill, 0.22)

    roughness = np.clip(0.88 - gear * 0.2 + twill * 0.06, 0.4, 0.98)
    metallic = gear * np.clip(nl.value_noise(size, 40, seed + 8) * 0.35, 0.0, 0.35)
    ao = mg.height_to_ao(height, radii=(2, 5, 11), strength=0.9, floor=0.45)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=metallic, ao=ao)


def uniform_ranger(size, seed=127):
    """Faction A — Ridge Rangers. Olive drab, amber accent."""
    return _uniform(size, seed, HEX("5C6B4A"), HEX("6E7C58"), HEX("C9A227"), HEX("4A3D2E"))


def uniform_legion(size, seed=131):
    """Faction B — Iron Legion. Field grey, deep red accent."""
    return _uniform(size, seed, HEX("4A4F4A"), HEX("5A5F58"), HEX("8C2F2F"), HEX("32302B"))


def gunmetal(size, seed=149):
    """Weapon atlas: parkerised steel, worn bluing, wood furniture, polymer.

    UV bands: 0.00-0.45 steel | 0.45-0.70 wood | 0.70-0.88 polymer | 0.88-1.0 brass
    """
    # Machining marks are a whisper on gunmetal, not a corrugation — at any
    # real amplitude they turn the receiver into roofing sheet.
    machining = nl.stripes(size, 240, 0.0, jitter=0.75, seed=seed)
    micro = nl.fbm(size, 36, 5, seed + 1)
    edge_wear = nl.fbm(size, 11, 5, seed + 2)
    grain = nl.stripes(size, 90, 3.0, jitter=0.5, seed=seed + 3)
    dings = nl.worley_edges(size, 30, seed + 5, sharpness=18.0)

    height = nl.normalise(machining * 0.08 + micro * 0.62 + edge_wear * 0.22
                          - dings * 0.08)

    u = np.linspace(0.0, 1.0, size, endpoint=False)[None, :].repeat(size, 0)
    wood = ((u >= 0.45) & (u < 0.70)).astype(np.float64)
    polymer = ((u >= 0.70) & (u < 0.88)).astype(np.float64)
    brass = (u >= 0.88).astype(np.float64)
    steel = 1.0 - np.clip(wood + polymer + brass, 0.0, 1.0)

    wear = np.clip(edge_wear * 1.8 - 0.7, 0.0, 1.0)
    base = _rgb(HEX("3A3D40"), size)
    base = _mix(base, _rgb(HEX("8E9296"), size), steel * wear * 0.8)
    base = _mix(base, _mix(_rgb(HEX("5A3E24"), size), _rgb(HEX("8A6238"), size), grain), wood)
    base = _mix(base, _rgb(HEX("26282A"), size), polymer)
    base = _mix(base, _rgb(HEX("B08D3A"), size), brass)
    albedo = mg.overlay(base, machining, 0.2)

    metallic = np.clip(steel * 0.95 + brass * 0.95 + wood * 0.02 + polymer * 0.02, 0.0, 1.0)
    roughness = np.clip(
        steel * (0.38 - wear * 0.16) + wood * 0.62 + polymer * 0.55 + brass * 0.3
        + micro * 0.08,
        0.12, 0.9,
    )
    ao = mg.height_to_ao(height, radii=(2, 4, 9), strength=0.7, floor=0.55)
    return dict(height=height, albedo=albedo, roughness=roughness,
                metallic=metallic, ao=ao)


REGISTRY = {
    "rock_granite": rock_granite,
    "cliff_strata": cliff_strata,
    "ground_rocky": ground_rocky,
    "grass_highland": grass_highland,
    "soil_trench": soil_trench,
    "sandbag_burlap": sandbag_burlap,
    "wood_plank": wood_plank,
    "metal_corrugated": metal_corrugated,
    "concrete_bunker": concrete_bunker,
    "crate_wood": crate_wood,
    "uniform_ranger": uniform_ranger,
    "uniform_legion": uniform_legion,
    "gunmetal": gunmetal,
}

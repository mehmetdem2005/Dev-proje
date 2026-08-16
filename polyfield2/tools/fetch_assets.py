"""Download CC0 PBR texture sets and repack them for this project.

    blender -b --python fetch_assets.py -- [--size 1K] [--only name,name]

Sources are CC0 (public domain) only — ambientCG. Each set arrives as separate
Color / NormalGL / Roughness / AmbientOcclusion / Metalness maps and is repacked
into the layout the game already uses:

    <name>_albedo.png   sRGB colour
    <name>_normal.png   tangent-space normal, OpenGL convention
    <name>_orm.png      R = AO, G = roughness, B = metallic

Keeping the output names identical to the procedural generator's means nothing
downstream changes: MaterialLibrary still binds by material name.

Runs under Blender's Python because that is the interpreter here with both
numpy and an image decoder (JPEG in, PNG out).
"""

import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "texgen"))

import bpy
import numpy as np

from pngio import write_png

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "game", "assets", "textures")
CACHE_DIR = os.path.join(ROOT, "tools", ".asset-cache")

API = "https://ambientcg.com/get?file={file}"

#: project material name -> ambientCG asset id. Every entry is CC0.
SETS = {
    "rock_granite": "Rock030",
    "cliff_strata": "Rock023",
    "ground_rocky": "Gravel022",
    "grass_highland": "Grass004",
    "soil_trench": "Ground054",
    "sandbag_burlap": "Fabric064",
    "wood_plank": "Planks020",
    "metal_corrugated": "MetalPlates006",
    "concrete_bunker": "Concrete034",
    "crate_wood": "Wood067",
    "uniform_cloth": "Fabric054",
    "skin": "Fabric031",
    "gear_leather": "Leather011",
    "gunmetal": "Metal032",
    "bark": "Bark012",
    "sand_dry": "Ground033",
    "moss_rock": "Rock035",
}

#: fallbacks tried in order when the first choice 404s
ALTERNATES = {
    "cliff_strata": ["Rock020", "Rock029", "Cliff002"],
    "ground_rocky": ["Gravel023", "Ground037", "Gravel021"],
    "grass_highland": ["Grass003", "Grass001", "Ground038"],
    "soil_trench": ["Ground052", "Ground037", "Ground048"],
    "sandbag_burlap": ["Fabric054", "Fabric020", "Fabric006"],
    "wood_plank": ["Planks011", "Wood051", "Planks017"],
    "metal_corrugated": ["MetalPlates003", "Metal031", "MetalPlates013"],
    "concrete_bunker": ["Concrete033", "Concrete016", "Concrete031"],
    "crate_wood": ["Wood062", "Wood048", "Planks014"],
    "uniform_cloth": ["Fabric020", "Fabric046", "Fabric008"],
    "skin": ["Fabric045", "Fabric008", "Fabric020"],
    "gear_leather": ["Leather008", "Leather005", "Fabric020"],
    "gunmetal": ["Metal029", "Metal038", "MetalPlates002"],
    "bark": ["Bark006", "Bark009", "Bark001"],
    "sand_dry": ["Ground027", "Sand004", "Ground031"],
    "moss_rock": ["Rock028", "Moss002", "Rock022"],
}


def _download(url, path, timeout=300):
    request = urllib.request.Request(url, headers={"User-Agent": "polyfield2-assetfetch"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        data = response.read()
    if len(data) < 4096:
        raise RuntimeError(f"suspiciously small payload ({len(data)} bytes)")
    with open(path, "wb") as handle:
        handle.write(data)
    return len(data)


def fetch_set(asset_id, size="1K"):
    """Download and unpack one ambientCG set; returns the extraction directory."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = f"{asset_id}_{size}-JPG"
    zip_path = os.path.join(CACHE_DIR, f"{name}.zip")
    out_dir = os.path.join(CACHE_DIR, name)

    if os.path.isdir(out_dir) and os.listdir(out_dir):
        return out_dir

    if not os.path.exists(zip_path):
        _download(API.format(file=f"{name}.zip"), zip_path)

    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            if member.lower().endswith((".jpg", ".png")):
                archive.extract(member, out_dir)
    return out_dir


def _load_image(path):
    """Load an image as a float array in [0, 1], RGB, top-down."""
    image = bpy.data.images.load(path, check_existing=False)
    width, height = image.size
    pixels = np.empty(width * height * image.channels, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, image.channels)[::-1]
    bpy.data.images.remove(image)
    return pixels[:, :, :3] if pixels.shape[2] >= 3 else np.repeat(pixels, 3, axis=2)


def _find(directory, *suffixes):
    for root, _dirs, files in os.walk(directory):
        for candidate in sorted(files):
            lowered = candidate.lower()
            for suffix in suffixes:
                if lowered.endswith(suffix.lower()):
                    return os.path.join(root, candidate)
    return None


def _srgb_to_linear(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _resize_to(a, size):
    """Nearest-neighbour resize to a square `size`.

    Sets are not guaranteed to ship every map at the same resolution — some
    have a half-size AO or roughness — and stacking mismatched arrays is a
    hard failure rather than a visible one, so normalise here.
    """
    if a.shape[0] == size and a.shape[1] == size:
        return a
    rows = (np.arange(size) * (a.shape[0] / size)).astype(np.int64).clip(0, a.shape[0] - 1)
    cols = (np.arange(size) * (a.shape[1] / size)).astype(np.int64).clip(0, a.shape[1] - 1)
    return a[rows][:, cols]


def repack(name, directory, tint=None, desaturate=False):
    """Turn an ambientCG set into albedo / normal / orm PNGs.

    `tint` multiplies the colour in linear light. `desaturate` strips the
    source hue first, which is what makes tinting reliable: multiplying a red
    canvas by olive gives brown, not olive. Stripping to luminance and then
    applying the palette colour lands on the intended hue every time.
    """
    colour_path = _find(directory, "_Color.jpg", "_Color.png")
    if colour_path is None:
        raise RuntimeError(f"{name}: no Color map in {directory}")

    albedo = _load_image(colour_path)
    if desaturate:
        luma = (albedo[:, :, 0] * 0.2126 + albedo[:, :, 1] * 0.7152
                + albedo[:, :, 2] * 0.0722)
        # Keep a little of the original chroma so the weave does not go flat.
        albedo = albedo * 0.15 + np.repeat(luma[:, :, None], 3, axis=2) * 0.85
    if tint is not None:
        # Multiply in linear light, then return to display space: tinting an
        # sRGB-encoded buffer directly darkens midtones incorrectly.
        linear = _srgb_to_linear(albedo) * np.asarray(tint).reshape(1, 1, 3)
        albedo = np.clip(linear, 0.0, 1.0) ** (1.0 / 2.4) * 1.055 - 0.055
        albedo = np.clip(albedo, 0.0, 1.0)

    size = albedo.shape[0]

    # NormalGL is the OpenGL-convention map, which is what Godot expects.
    normal_path = _find(directory, "_NormalGL.jpg", "_NormalGL.png",
                        "_Normal.jpg", "_Normal.png")
    normal = _resize_to(_load_image(normal_path), size) if normal_path else np.tile(
        np.array([0.5, 0.5, 1.0], dtype=np.float32), (size, size, 1))

    rough_path = _find(directory, "_Roughness.jpg", "_Roughness.png")
    roughness = (_resize_to(_load_image(rough_path), size)[:, :, 0] if rough_path
                 else np.full((size, size), 0.85))

    ao_path = _find(directory, "_AmbientOcclusion.jpg", "_AmbientOcclusion.png")
    ao = (_resize_to(_load_image(ao_path), size)[:, :, 0] if ao_path
          else np.ones((size, size)))

    metal_path = _find(directory, "_Metalness.jpg", "_Metalness.png")
    metallic = (_resize_to(_load_image(metal_path), size)[:, :, 0] if metal_path
                else np.zeros((size, size)))

    orm = np.stack([ao, roughness, metallic], axis=-1)

    os.makedirs(OUT_DIR, exist_ok=True)
    write_png(os.path.join(OUT_DIR, f"{name}_albedo.png"), albedo, srgb=True)
    write_png(os.path.join(OUT_DIR, f"{name}_normal.png"), normal, srgb=False)
    write_png(os.path.join(OUT_DIR, f"{name}_orm.png"), orm, srgb=False)
    return {
        "size": int(size),
        "maps": ["albedo", "normal", "orm"],
        "had_normal": normal_path is not None,
        "had_roughness": rough_path is not None,
        "had_ao": ao_path is not None,
        "had_metalness": metal_path is not None,
    }


#: Materials whose source hue is wrong for us: desaturated, then tinted to the
#: palette in docs/polyfield2/01-sanat-yonetimi.md.
TINTS = {
    "uniform_ranger": ("uniform_cloth", (0.52, 0.60, 0.40)),
    "uniform_legion": ("uniform_cloth", (0.44, 0.47, 0.44)),
    "sandbag_burlap": ("sandbag_burlap", (0.78, 0.66, 0.44)),
    "skin": ("skin", (0.86, 0.66, 0.50)),
    "gear_leather": ("gear_leather", (0.42, 0.32, 0.22)),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = argv[argv.index("--size") + 1] if "--size" in argv else "1K"
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None

    wanted = {k: v for k, v in SETS.items() if only is None or k in only}
    report, credits = {}, []

    for name, asset_id in wanted.items():
        candidates = [asset_id] + ALTERNATES.get(name, [])
        directory, used = None, None
        for candidate in candidates:
            try:
                directory = fetch_set(candidate, size)
                used = candidate
                break
            except Exception as error:                      # noqa: BLE001
                print(f"  {name}: {candidate} unavailable ({error})")
        if directory is None:
            print(f"  {name}: SKIPPED — no source available")
            continue

        try:
            info = repack(name, directory)
        except Exception as error:                          # noqa: BLE001
            print(f"  {name}: repack failed ({error})")
            continue

        info["source"] = used
        report[name] = info
        credits.append((name, used))
        print(f"  {name:<18} <- ambientCG {used:<16} {info['size']}px "
              f"{'N' if info['had_normal'] else '-'}"
              f"{'R' if info['had_roughness'] else '-'}"
              f"{'A' if info['had_ao'] else '-'}"
              f"{'M' if info['had_metalness'] else '-'}")

    # Faction uniforms are the same fabric tinted two ways.
    for name, (base, tint) in TINTS.items():
        source = SETS.get(base)
        if source is None or base not in report:
            continue
        directory = fetch_set(report[base]["source"], size)
        info = repack(name, directory, tint=tint, desaturate=True)
        info["source"] = report[base]["source"]
        info["tint"] = list(tint)
        report[name] = info
        credits.append((name, info["source"]))
        print(f"  {name:<18} <- ambientCG {info['source']:<16} tinted {tint}")

    with open(os.path.join(OUT_DIR, "SOURCES.json"), "w") as handle:
        json.dump({"license": "CC0 1.0", "provider": "ambientCG",
                   "materials": report}, handle, indent=1)

    lines = ["# Texture sources", "",
             "All downloaded texture sets are **CC0 1.0 (public domain)** from",
             "[ambientCG](https://ambientcg.com/). No attribution is legally required;",
             "it is recorded here anyway so the provenance of every file is traceable.",
             "", "| Material | ambientCG asset |", "| --- | --- |"]
    for name, source in sorted(credits):
        lines.append(f"| `{name}` | [{source}](https://ambientcg.com/view?id={source}) |")
    lines += ["", "Regenerate with `blender -b --python tools/fetch_assets.py`.",
              "Downloads are cached in `tools/.asset-cache/` (gitignored)."]
    with open(os.path.join(OUT_DIR, "SOURCES.md"), "w") as handle:
        handle.write("\n".join(lines) + "\n")

    print(f"\n{len(report)} material sets -> {OUT_DIR}")


if __name__ == "__main__":
    main()

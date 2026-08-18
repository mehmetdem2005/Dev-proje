"""Download CC0 ground textures and repack them into Terrain3D's format.

    blender -b --python tools/fetch_textures.py -- [--size 512] [--count 32]

Terrain3D does not take loose PBR maps. It samples exactly two texture arrays
and reads four channels out of each:

    <name>_alb_ht.png    RGB = albedo (sRGB),  A = height
    <name>_nrm_rg.png    RGB = normal (OpenGL), A = roughness

The alpha channels are not padding. `albedo.a` is the height used to blend one
material over another — that is what makes gravel sit in the cracks of rock
rather than cross-fading into it — and it also feeds ambient occlusion.
`normal.a` is roughness, modulated per-texture by `roughness` on the asset.
Getting either wrong looks like a lighting bug, not a texture bug.

Everything is square, the same size, and power-of-two, because they go into a
texture array: one odd size and the array fails to build.

Sources are CC0 (public domain) from ambientCG. Nothing here is generated.
"""

import json
import os
import sys
import urllib.request
import zipfile

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "textures")
CACHE_DIR = os.path.join(HERE, ".texture-cache")
API = "https://ambientcg.com/get?file={file}"

#: (project name, ambientCG id, category). Ordered roughly ground -> rock, so
#: the ids that land in the array read in a sensible order in the editor.
#: More are listed than requested; whatever 404s is skipped and the next is
#: used, so the pack still fills up if a source is retired.
CANDIDATES = [
    # --- grass and meadow ---
    ("grass_meadow",      "Grass004", "grass"),
    ("grass_dry",         "Grass003", "grass"),
    ("grass_tufted",      "Grass001", "grass"),
    ("grass_patchy",      "Grass002", "grass"),
    # --- soil, dirt, mud ---
    ("dirt_dry",          "Ground047", "soil"),
    ("dirt_packed",       "Ground037", "soil"),
    ("dirt_forest",       "Ground003", "soil"),
    ("soil_dark",         "Ground054", "soil"),
    ("soil_cracked",      "Ground033", "soil"),
    ("mud_wet",           "Ground048", "soil"),
    ("mud_tracks",        "Ground052", "soil"),
    ("leaf_litter",       "Ground042", "soil"),
    # --- sand and scree ---
    ("sand_fine",         "Ground027", "sand"),
    ("sand_dunes",        "Sand004",   "sand"),
    ("sand_coarse",       "Sand002",   "sand"),
    ("gravel_grey",       "Gravel022", "gravel"),
    ("gravel_pale",       "Gravel023", "gravel"),
    ("gravel_river",      "Gravel021", "gravel"),
    ("scree_slope",       "Ground038", "gravel"),
    # --- rock and cliff ---
    ("rock_granite",      "Rock030", "rock"),
    ("rock_strata",       "Rock023", "rock"),
    ("rock_mossy",        "Rock035", "rock"),
    ("rock_cracked",      "Rock029", "rock"),
    ("rock_boulder",      "Rock020", "rock"),
    ("rock_weathered",    "Rock022", "rock"),
    ("rock_dark",         "Rock028", "rock"),
    ("cliff_layered",     "Rock026", "rock"),
    ("cliff_sharp",       "Rock025", "rock"),
    ("rock_slate",        "Rock031", "rock"),
    ("rock_pebbles",      "Rock024", "rock"),
    # --- alpine ---
    ("snow_fresh",        "Snow006", "snow"),
    ("snow_packed",       "Snow004", "snow"),
    ("snow_rocky",        "Snow010", "snow"),
    # --- spares, used only if something above 404s ---
    ("ground_rough",      "Ground068", "soil"),
    ("ground_stony",      "Ground078", "soil"),
    ("rock_face",         "Rock017", "rock"),
]


def _download(url, path, timeout=300, attempts=4):
    """Fetch with backoff. ambientCG resets the connection often enough that a
    single-shot download silently drops textures out of the pack."""
    import time
    last = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "terrain3d-mobile"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            if len(data) < 4096:
                raise RuntimeError(f"suspiciously small payload ({len(data)} bytes)")
            with open(path, "wb") as handle:
                handle.write(data)
            return
        except urllib.error.HTTPError:
            raise                                    # 404 will not fix itself
        except Exception as error:                   # noqa: BLE001
            last = error
            time.sleep(2 ** attempt)
    raise last


def fetch_set(asset_id, resolution="1K"):
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = f"{asset_id}_{resolution}-JPG"
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


def _load(path):
    image = bpy.data.images.load(path, check_existing=False)
    width, height = image.size
    pixels = np.empty(width * height * image.channels, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, image.channels)[::-1]
    bpy.data.images.remove(image)
    return pixels


def _find(directory, *suffixes):
    for root, _dirs, files in os.walk(directory):
        for candidate in sorted(files):
            for suffix in suffixes:
                if candidate.lower().endswith(suffix.lower()):
                    return os.path.join(root, candidate)
    return None


def _resize(a, size):
    """Box-filter down to `size`. Nearest sampling aliases badly on gravel and
    leaves a sparkling mess once mipmaps are built on top of it."""
    if a.shape[0] == size and a.shape[1] == size:
        return a
    rows, cols = a.shape[0], a.shape[1]
    if rows % size == 0 and cols % size == 0 and rows > size:
        fy, fx = rows // size, cols // size
        shaped = a[: size * fy, : size * fx]
        if a.ndim == 2:
            return shaped.reshape(size, fy, size, fx).mean(axis=(1, 3))
        return shaped.reshape(size, fy, size, fx, a.shape[2]).mean(axis=(1, 3))
    ri = (np.arange(size) * (rows / size)).astype(np.int64).clip(0, rows - 1)
    ci = (np.arange(size) * (cols / size)).astype(np.int64).clip(0, cols - 1)
    return a[ri][:, ci]


def _channel(directory, size, *suffixes, default=0.5):
    path = _find(directory, *suffixes)
    if path is None:
        return np.full((size, size), default, dtype=np.float32), False
    data = _load(path)
    if data.ndim == 3:
        data = data[:, :, 0]
    return _resize(data, size).astype(np.float32), True


def repack(name, directory, size, write_png):
    """Two RGBA PNGs in the layout Terrain3D samples."""
    colour_path = _find(directory, "_Color.jpg", "_Color.png")
    if colour_path is None:
        raise RuntimeError("no Color map")

    albedo = _resize(_load(colour_path)[:, :, :3], size)

    # Height drives Terrain3D's height-blending. Displacement is the right
    # source; without it a flat 0.5 makes blending degrade to a plain lerp
    # rather than breaking outright.
    height, had_height = _channel(directory, size, "_Displacement.jpg",
                                  "_Displacement.png", default=0.5)
    normal_path = _find(directory, "_NormalGL.jpg", "_NormalGL.png")
    if normal_path is not None:
        normal = _resize(_load(normal_path)[:, :, :3], size)
        had_normal = True
    else:
        normal = np.tile(np.array([0.5, 0.5, 1.0], dtype=np.float32), (size, size, 1))
        had_normal = False
    roughness, had_rough = _channel(directory, size, "_Roughness.jpg",
                                    "_Roughness.png", default=0.85)

    albedo_ht = np.concatenate([albedo, height[:, :, None]], axis=2)
    normal_rg = np.concatenate([normal, roughness[:, :, None]], axis=2)

    write_png(os.path.join(OUT_DIR, f"{name}_alb_ht.png"), albedo_ht, srgb=True)
    write_png(os.path.join(OUT_DIR, f"{name}_nrm_rg.png"), normal_rg, srgb=False)

    return {"height": had_height, "normal": had_normal, "roughness": had_rough}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 512
    wanted = int(argv[argv.index("--count") + 1]) if "--count" in argv else 32

    sys.path.insert(0, os.path.join(ROOT, "..", "polyfield2", "tools", "texgen"))
    from pngio import write_png

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"=== Terrain3D textures: up to {wanted} sets at {size}px ===")

    manifest = []
    for name, asset_id, category in CANDIDATES:
        if len(manifest) >= wanted:
            break
        try:
            directory = fetch_set(asset_id)
        except Exception as error:                          # noqa: BLE001
            print(f"  {name:<18} skip — {asset_id} unavailable ({error})")
            continue
        try:
            info = repack(name, directory, size, write_png)
        except Exception as error:                          # noqa: BLE001
            print(f"  {name:<18} skip — repack failed ({error})")
            continue

        manifest.append({"id": len(manifest), "name": name, "source": asset_id,
                         "category": category, **info})
        flags = "".join([
            "H" if info["height"] else "-",
            "N" if info["normal"] else "-",
            "R" if info["roughness"] else "-"])
        print(f"  [{len(manifest) - 1:2d}] {name:<18} <- ambientCG {asset_id:<12} {flags}")

    with open(os.path.join(OUT_DIR, "SOURCES.json"), "w") as handle:
        json.dump({"license": "CC0 1.0", "provider": "ambientCG",
                   "size": size, "textures": manifest}, handle, indent=1)

    lines = ["# Texture sources", "",
             "All CC0 1.0 (public domain) from [ambientCG](https://ambientcg.com/).",
             "Repacked into Terrain3D's channel layout by `tools/fetch_textures.py`:",
             "", "    <name>_alb_ht.png   RGB albedo, A height",
             "    <name>_nrm_rg.png   RGB normal (OpenGL), A roughness", "",
             f"{len(manifest)} textures at {size}x{size}.", "",
             "| id | name | category | ambientCG |", "| --- | --- | --- | --- |"]
    for entry in manifest:
        lines.append("| %d | `%s` | %s | [%s](https://ambientcg.com/view?id=%s) |" % (
            entry["id"], entry["name"], entry["category"], entry["source"],
            entry["source"]))
    with open(os.path.join(OUT_DIR, "SOURCES.md"), "w") as handle:
        handle.write("\n".join(lines) + "\n")

    print(f"\n{len(manifest)} textures -> {OUT_DIR}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Force the terrain textures to import mobile-friendly.

    python3 tools/fix_imports.py && godot --headless --import

Godot's default texture import is Lossless with no mipmaps. For 32 terrain
textures that is the difference between a terrain that runs on a phone and one
that does not:

  * compress/mode=2 (VRAM Compressed) -> ETC2/ASTC on Android. Lossless means
    32 x 512x512 RGBA8 x 2 arrays = 64 MB of VRAM for the ground alone.
  * mipmaps/generate=true -> without them every distant pixel samples the full
    resolution image, which thrashes the texture cache and shimmers as the
    camera moves. Terrain3D samples with textureGrad and expects mips.
  * compress/normal_map=2 (Disabled) -> "Detect" can pick a normal-map codec
    that throws the alpha channel away, and the alpha of *_nrm_rg.png is the
    roughness. Losing it silently makes the whole terrain uniformly shiny.

Re-run after adding textures; it is idempotent.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTURE_DIR = os.path.join(ROOT, "textures")

WANTED = {
    "compress/mode": "2",
    "mipmaps/generate": "true",
    "compress/normal_map": "2",
    "compress/channel_pack": "0",
}


def patch(path):
    with open(path) as handle:
        lines = handle.read().splitlines()

    changed = False
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in WANTED:
            seen.add(key)
            replacement = f"{key}={WANTED[key]}"
            if line != replacement:
                changed = True
                line = replacement
        out.append(line)

    # A param Godot did not write yet still has to be added, or it keeps the
    # default on the next import.
    missing = [k for k in WANTED if k not in seen]
    if missing and "[params]" in out:
        index = out.index("[params]") + 1
        for key in missing:
            out.insert(index, f"{key}={WANTED[key]}")
        changed = True

    if changed:
        with open(path, "w") as handle:
            handle.write("\n".join(out) + "\n")
    return changed


def main():
    if not os.path.isdir(TEXTURE_DIR):
        print(f"no texture directory at {TEXTURE_DIR}", file=sys.stderr)
        return 1
    files = sorted(f for f in os.listdir(TEXTURE_DIR) if f.endswith(".png.import"))
    if not files:
        print("no .import files yet — run `godot --headless --import` first")
        return 1

    patched = sum(patch(os.path.join(TEXTURE_DIR, name)) for name in files)
    print(f"{patched} of {len(files)} import files updated "
          f"(VRAM compression, mipmaps, alpha-safe normals)")
    print("now run: godot --headless --import")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

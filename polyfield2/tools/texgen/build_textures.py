"""Generate the full PBR texture set.

    python3 build_textures.py [--size 512] [--out DIR] [--only name,name]

Writes, per material:
    <name>_albedo.png    sRGB colour
    <name>_normal.png    tangent-space normal, OpenGL convention (green up)
    <name>_orm.png       R=AO, G=roughness, B=metallic  (ORMMaterial3D layout)
    <name>_height.png    grayscale height, kept for future parallax/detail work

The ORM pack is deliberate: on the Mobile renderer one sampler beats three.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import mapgen as mg
from materials import REGISTRY
from pngio import write_png

DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "textures"
)

# Normal strength per material family — flat surfaces need less push than rock.
NORMAL_STRENGTH = {
    "rock_granite": 2.4,
    "cliff_strata": 2.8,
    "ground_rocky": 2.0,
    "grass_highland": 1.2,
    "soil_trench": 1.8,
    "sandbag_burlap": 1.6,
    "wood_plank": 1.4,
    "metal_corrugated": 2.2,
    "concrete_bunker": 1.3,
    "crate_wood": 1.4,
    "uniform_ranger": 1.0,
    "uniform_legion": 1.0,
    "gunmetal": 0.9,
}


def build_one(name, generator, size, out_dir):
    started = time.time()
    data = generator(size)

    height = np.clip(data["height"], 0.0, 1.0)
    albedo = np.clip(data["albedo"], 0.0, 1.0)
    roughness = np.clip(np.broadcast_to(data["roughness"], (size, size)), 0.0, 1.0)
    metallic = np.clip(np.broadcast_to(data["metallic"], (size, size)), 0.0, 1.0)
    ao = np.clip(np.broadcast_to(data["ao"], (size, size)), 0.0, 1.0)

    normal = mg.height_to_normal(height, strength=NORMAL_STRENGTH.get(name, 1.5),
                                 green_up=True)
    orm = mg.pack_orm(ao, roughness, metallic)

    write_png(os.path.join(out_dir, f"{name}_albedo.png"), albedo, srgb=True)
    write_png(os.path.join(out_dir, f"{name}_normal.png"), normal, srgb=False)
    write_png(os.path.join(out_dir, f"{name}_orm.png"), orm, srgb=False)
    write_png(os.path.join(out_dir, f"{name}_height.png"), height, srgb=False)

    return {
        "name": name,
        "size": size,
        "seconds": round(time.time() - started, 2),
        "roughness_range": [round(float(roughness.min()), 3), round(float(roughness.max()), 3)],
        "metallic_mean": round(float(metallic.mean()), 3),
        "ao_min": round(float(ao.min()), 3),
        "maps": ["albedo", "normal", "orm", "height"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    wanted = [n.strip() for n in args.only.split(",") if n.strip()] or list(REGISTRY)
    unknown = [n for n in wanted if n not in REGISTRY]
    if unknown:
        parser.error(f"unknown material(s): {', '.join(unknown)}")

    report = []
    for name in wanted:
        info = build_one(name, REGISTRY[name], args.size, out_dir)
        report.append(info)
        print(f"  {name:<20} {info['seconds']:>6.2f}s  "
              f"rough {info['roughness_range'][0]:.2f}-{info['roughness_range'][1]:.2f}  "
              f"metal {info['metallic_mean']:.2f}")

    manifest = os.path.join(out_dir, "textures.json")
    with open(manifest, "w") as handle:
        json.dump({"size": args.size, "convention": "normal=OpenGL green-up, orm=R:AO G:rough B:metal",
                   "materials": report}, handle, indent=2)

    total_files = sum(len(m["maps"]) for m in report)
    print(f"\n{len(report)} materials, {total_files} PNG maps -> {out_dir}")


if __name__ == "__main__":
    main()

"""Generate the weapon set.

    blender -b --python gen_weapons.py

Five weapons, each split into steel / wood / polymer groups that are UV'd into
the matching band of the shared gunmetal atlas. Origin is at the grip so the
model drops straight onto the rig's WeaponSocket bone; the muzzle position is
written to weapons.json for spawning tracers and flash.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Euler, Vector

import pf_lib as pf
from gen_fortifications import _bevelled_box

# Bands in gunmetal_albedo.png (see tools/texgen/materials.py).
BANDS = {
    "steel": (0.02, 0.43),
    "wood": (0.47, 0.68),
    "polymer": (0.72, 0.86),
    "brass": (0.90, 0.99),
}

# Weapons point along +Y (forward). Godot gets -Z forward after the Y-up flip.


def _part(group, name, size, location, rotation=(0, 0, 0), bevel=0.006):
    obj = _bevelled_box(name, size, bevel=bevel)
    obj.location = Vector(location)
    obj.rotation_euler = Euler(rotation)
    group.append(obj)
    return obj


def _tube(group, name, radius, length, location, rotation=(math.pi / 2, 0, 0), sides=8):
    obj = pf.make_cylinder(name, radius=radius, depth=length, segments=sides)
    obj.rotation_euler = Euler(rotation)
    obj.location = Vector(location)
    group.append(obj)
    return obj


def _finish(groups, name):
    """UV each material group into its atlas band, then join into one mesh."""
    meshes = []
    for band, parts in groups.items():
        if not parts:
            continue
        merged = pf.join_objects(parts, f"{name}_{band}")
        pf.select_only(merged)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        pf.box_project_uv(merged, scale=0.25)
        lo, hi = BANDS[band]
        pf.atlas_uv(merged, lo, hi)
        meshes.append(merged)

    weapon = pf.join_objects(meshes, name)
    pf.shade_flat(weapon)
    pf.triangulate(weapon)
    pf.set_material(weapon, "gunmetal")
    return weapon


def make_rifle(name="wpn_rifle"):
    """Bolt-action service rifle — long barrel, wooden furniture, iron sights."""
    steel, wood, polymer = [], [], []
    _part(steel, f"{name}_receiver", (0.048, 0.30, 0.070), (0.0, 0.10, 0.0))
    _tube(steel, f"{name}_barrel", 0.014, 0.62, (0.0, 0.56, 0.012))
    _tube(steel, f"{name}_muzzle", 0.019, 0.05, (0.0, 0.86, 0.012))
    _part(steel, f"{name}_bolt", (0.026, 0.11, 0.026), (0.032, 0.14, 0.030))
    _part(steel, f"{name}_bolt_handle", (0.075, 0.020, 0.020), (0.068, 0.11, 0.028),
          rotation=(0.0, 0.0, 0.0))
    _part(steel, f"{name}_rear_sight", (0.030, 0.035, 0.028), (0.0, 0.27, 0.052))
    _part(steel, f"{name}_front_sight", (0.014, 0.022, 0.034), (0.0, 0.82, 0.040))
    _part(steel, f"{name}_trigger_guard", (0.030, 0.085, 0.030), (0.0, -0.03, -0.045))
    _part(steel, f"{name}_trigger", (0.010, 0.020, 0.034), (0.0, -0.035, -0.038))

    _part(wood, f"{name}_stock", (0.056, 0.34, 0.105), (0.0, -0.24, -0.028))
    _part(wood, f"{name}_comb", (0.050, 0.20, 0.055), (0.0, -0.14, 0.028))
    _part(wood, f"{name}_butt", (0.058, 0.045, 0.135), (0.0, -0.40, -0.045))
    _part(wood, f"{name}_handguard", (0.052, 0.40, 0.055), (0.0, 0.44, -0.012))

    _part(polymer, f"{name}_magazine", (0.038, 0.075, 0.055), (0.0, 0.02, -0.058))
    return _finish({"steel": steel, "wood": wood, "polymer": polymer}, name), (0.0, 0.89, 0.012)


def make_smg(name="wpn_smg"):
    """Blowback submachine gun — stubby, folding stock, side magazine well."""
    steel, wood, polymer = [], [], []
    _part(steel, f"{name}_receiver", (0.052, 0.34, 0.062), (0.0, 0.08, 0.0))
    _tube(steel, f"{name}_barrel", 0.013, 0.24, (0.0, 0.36, 0.0))
    _tube(steel, f"{name}_shroud", 0.026, 0.20, (0.0, 0.33, 0.0))
    _part(steel, f"{name}_bolt_handle", (0.060, 0.018, 0.018), (0.052, 0.16, 0.020))
    _part(steel, f"{name}_rear_sight", (0.024, 0.024, 0.024), (0.0, 0.20, 0.044))
    _part(steel, f"{name}_front_sight", (0.012, 0.018, 0.030), (0.0, 0.46, 0.030))
    _part(steel, f"{name}_trigger_guard", (0.028, 0.075, 0.028), (0.0, -0.05, -0.042))
    for index, offset in enumerate((-0.20, -0.28)):
        _part(steel, f"{name}_stock_rod_{index}", (0.016, 0.24, 0.016), (0.0, offset, -0.01),
              rotation=(0.16, 0.0, 0.0))
    _part(steel, f"{name}_stock_plate", (0.090, 0.020, 0.060), (0.0, -0.40, -0.058))

    _part(polymer, f"{name}_grip", (0.036, 0.050, 0.115), (0.0, -0.055, -0.085),
          rotation=(0.28, 0.0, 0.0))
    _part(polymer, f"{name}_magazine", (0.030, 0.062, 0.185), (0.0, 0.06, -0.125),
          rotation=(-0.06, 0.0, 0.0))
    _part(wood, f"{name}_foregrip", (0.040, 0.090, 0.048), (0.0, 0.26, -0.042))
    return _finish({"steel": steel, "wood": wood, "polymer": polymer}, name), (0.0, 0.49, 0.0)


def make_lmg(name="wpn_lmg"):
    """Belt-fed light machine gun — heavy barrel, bipod, top-mounted drum."""
    steel, wood, polymer = [], [], []
    _part(steel, f"{name}_receiver", (0.070, 0.40, 0.090), (0.0, 0.12, 0.0))
    _tube(steel, f"{name}_barrel", 0.019, 0.58, (0.0, 0.60, 0.008), sides=10)
    for index in range(4):
        _tube(steel, f"{name}_fin_{index}", 0.030, 0.020,
              (0.0, 0.42 + index * 0.075, 0.008), sides=10)
    _tube(steel, f"{name}_flash", 0.030, 0.075, (0.0, 0.90, 0.008), sides=8)
    _part(steel, f"{name}_feed_cover", (0.066, 0.20, 0.032), (0.0, 0.14, 0.058))
    _part(steel, f"{name}_rear_sight", (0.026, 0.028, 0.030), (0.0, 0.03, 0.086))
    _part(steel, f"{name}_front_sight", (0.014, 0.020, 0.036), (0.0, 0.84, 0.044))
    _part(steel, f"{name}_trigger_guard", (0.032, 0.080, 0.030), (0.0, -0.06, -0.056))
    for sign in (-1, 1):
        _part(steel, f"{name}_bipod_{sign}", (0.014, 0.014, 0.30),
              (sign * 0.055, 0.62, -0.16), rotation=(0.0, sign * 0.30, 0.0))
    _part(steel, f"{name}_bipod_mount", (0.070, 0.050, 0.030), (0.0, 0.62, -0.030))

    _part(wood, f"{name}_stock", (0.060, 0.30, 0.110), (0.0, -0.22, -0.030))
    _part(wood, f"{name}_butt", (0.062, 0.040, 0.140), (0.0, -0.37, -0.048))
    _part(polymer, f"{name}_grip", (0.038, 0.052, 0.120), (0.0, -0.075, -0.095),
          rotation=(0.26, 0.0, 0.0))
    _part(polymer, f"{name}_drum", (0.090, 0.110, 0.110), (0.0, 0.16, -0.100))
    return _finish({"steel": steel, "wood": wood, "polymer": polymer}, name), (0.0, 0.94, 0.008)


def make_pistol(name="wpn_pistol"):
    """Service sidearm — slide, frame, boxy magazine."""
    steel, wood, polymer = [], [], []
    _part(steel, f"{name}_slide", (0.030, 0.185, 0.048), (0.0, 0.045, 0.020))
    _part(steel, f"{name}_frame", (0.028, 0.150, 0.030), (0.0, 0.030, -0.012))
    _tube(steel, f"{name}_barrel", 0.008, 0.030, (0.0, 0.145, 0.020))
    _part(steel, f"{name}_rear_sight", (0.018, 0.012, 0.012), (0.0, -0.035, 0.048))
    _part(steel, f"{name}_front_sight", (0.008, 0.010, 0.012), (0.0, 0.125, 0.048))
    _part(steel, f"{name}_trigger_guard", (0.022, 0.050, 0.024), (0.0, -0.010, -0.040))
    _part(steel, f"{name}_hammer", (0.012, 0.018, 0.026), (0.0, -0.070, 0.026))

    _part(wood, f"{name}_grip", (0.032, 0.048, 0.115), (0.0, -0.058, -0.078),
          rotation=(0.22, 0.0, 0.0))
    _part(polymer, f"{name}_magazine", (0.020, 0.034, 0.020), (0.0, -0.052, -0.132),
          rotation=(0.22, 0.0, 0.0))
    return _finish({"steel": steel, "wood": wood, "polymer": polymer}, name), (0.0, 0.162, 0.020)


def make_launcher(name="wpn_launcher"):
    """Shoulder-fired anti-vehicle launcher — open tube, grip, blast shield."""
    steel, wood, polymer = [], [], []
    _tube(steel, f"{name}_tube", 0.045, 1.10, (0.0, 0.28, 0.0), sides=10)
    _tube(steel, f"{name}_muzzle_ring", 0.056, 0.045, (0.0, 0.81, 0.0), sides=10)
    _tube(steel, f"{name}_breech_ring", 0.056, 0.045, (0.0, -0.25, 0.0), sides=10)
    _part(steel, f"{name}_shield", (0.180, 0.020, 0.150), (0.0, 0.30, 0.075))
    _part(steel, f"{name}_sight", (0.020, 0.070, 0.055), (0.045, 0.24, 0.070))
    _part(steel, f"{name}_warhead_ring", (0.070, 0.030, 0.070), (0.0, 0.72, 0.0))
    _tube(steel, f"{name}_warhead", 0.062, 0.16, (0.0, 0.90, 0.0), sides=10)
    _tube(steel, f"{name}_warhead_tip", 0.030, 0.10, (0.0, 1.02, 0.0), sides=8)

    _part(polymer, f"{name}_grip", (0.038, 0.055, 0.130), (0.0, 0.02, -0.105),
          rotation=(0.22, 0.0, 0.0))
    _part(polymer, f"{name}_foregrip", (0.034, 0.050, 0.105), (0.0, 0.40, -0.090),
          rotation=(0.16, 0.0, 0.0))
    _part(wood, f"{name}_rest", (0.070, 0.140, 0.045), (0.0, -0.12, -0.055))
    return _finish({"steel": steel, "wood": wood, "polymer": polymer}, name), (0.0, 1.08, 0.0)


def main():
    pf.reset_scene()
    pf.report("Weapons")

    builders = [make_rifle, make_smg, make_lmg, make_pistol, make_launcher]
    exported, manifest = [], {}

    for index, builder in enumerate(builders):
        obj, muzzle = builder()
        manifest[obj.name] = {
            # Godot space: X right, Y up, Z back.
            "muzzle": [round(muzzle[0], 4), round(muzzle[2], 4), round(-muzzle[1], 4)],
            "tris": pf.tri_count(obj),
        }
        print(f"  {obj.name:<14} {pf.tri_count(obj):4d} tris   muzzle {muzzle}")
        obj.location.x = index * 0.7
        exported.append(obj)

    path = os.path.join(pf.MODEL_DIR, "weapons.glb")
    pf.export_glb(exported, path)

    manifest_path = os.path.join(pf.MAP_DIR, "weapons.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as handle:
        json.dump(manifest, handle, indent=1)
    print(f"  manifest -> {os.path.relpath(manifest_path, pf.ROOT)}")


if __name__ == "__main__":
    main()

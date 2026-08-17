# Polyfield 2 — Ridgeline

Godot 4.6.3 (Mobile renderer) first-person skirmish prototype.

**Geometry** — terrain, rocks, fortifications, props, weapons, trees and the
rigged soldier — is modelled in Blender from scripts in this repository.
**Surface textures** are downloaded CC0 PBR sets from
[ambientCG](https://ambientcg.com/) and repacked by `tools/fetch_assets.py`;
see `game/assets/textures/SOURCES.md` for the per-material provenance. The one
texture still generated here is the alpha-cut foliage atlas, because the CC0
libraries ship tiling surfaces rather than masked leaf cards.

```
polyfield2/
  tools/
    texgen/          procedural PBR texture generator (numpy, no dependencies)
    blender/         mesh, rig and animation generators (Blender 4.5 headless)
    build_all.sh     rebuild everything, then re-import the Godot project
  game/              the Godot 4.6.3 project
    assets/          generated output — textures, models, map layout
    scripts/         GDScript
    shaders/         terrain splat shader
    scenes/          main, player, soldier
```

## Building

```bash
tools/build_all.sh                 # everything
tools/build_all.sh --size 1024     # higher-resolution textures
tools/build_all.sh --skip-textures # meshes only
```

Requires Blender 4.5+ (`BLENDER=`) and Godot 4.6.3 (`GODOT=`). Every generator
is seeded, so a rebuild reproduces the same assets.

## What gets generated

### Textures — `tools/fetch_assets.py`

Nineteen CC0 material sets, each repacked into three maps:

| Map | Contents | Colour space |
| --- | --- | --- |
| `<name>_albedo.png` | base colour | sRGB |
| `<name>_normal.png` | tangent-space normal, OpenGL convention (green up) | linear |
| `<name>_orm.png` | R = AO, G = roughness, B = metallic | linear |

The ORM pack is not a convenience: `ORMMaterial3D` reads all three channels
from one sampler, which on the Mobile renderer is worth more than any amount
of separate map authoring.

Sets whose source hue is wrong for the game (uniforms, sandbags, skin, leather)
are desaturated to luminance and then tinted to the palette. Multiplying a red
canvas by olive gives brown; stripping the hue first lands on the intended
colour every time.

`tools/texgen/` still holds the original procedural generator and the noise
library. It is no longer the source of the shipped ground textures, but it
builds the foliage atlas and remains the fallback if a download source ever
goes away.

### Map — `tools/blender/layout.py`

One module defines the battlefield: landforms, trench polylines, craters,
capture zones, spawns and prop scatter. The terrain generator carves from it
and Godot reads the exported `layout.json` to place everything. A trench module
cannot drift away from the channel cut for it, because both come from the same
numbers.

"Ridgeline" is 192 × 192 m of rocky highland: a meandering ridge, seven rock
outcrops, five capture zones (A–E), eight trench lines with parapets and
craters, and a rocky boundary rim. About 77% of the playable area is walkable
below 35°, and each capture zone is levelled to under 13° median slope.

### Meshes

| Asset | Detail | Triangles |
| --- | --- | --- |
| `terrain_ridgeline.glb` | 193×193 heightfield, 16 chunks, splat mask in vertex colours | 73 728 |
| `rocks.glb` | 5 boulders + 2 cliff blocks | 80–320 each |
| `fortifications.glb` | revetted trench bay, sandbag wall/stack, hedgehog, dugout roof | 76–1 108 |
| `props.glb` | crate, barrel, ammo box, capture mast + banner | 102–308 |
| `weapons.glb` | rifle, SMG, LMG, pistol, launcher | 380–736 |
| `soldier_ranger.glb` / `soldier_legion.glb` | rigged, skinned, 11 clips | 1 024 |

Textures are deliberately **not** embedded in the GLBs. All thirteen sets are
shared, so embedding would copy megabytes of PNG into every file; the GLBs
carry material *names* and `MaterialLibrary` binds the real materials at load.

### Rig and animation

24 bones (including a `WeaponSocket` under the right hand), skinned by explicit
bone-segment distance rather than Blender's heat weighting — heat diffusion
needs watertight connected geometry and fails on a figure assembled from
separate limb prisms.

Eleven clips: `idle`, `walk`, `run`, `crouch_idle`, `crouch_walk`, `aim`,
`fire`, `reload`, `hit`, `death`, `jump`.

## The game

- **Mobile renderer**, verified at runtime (`Vulkan — Forward Mobile`).
- **Territory Control**: five zones on one tug-of-war bar per point, so a
  contested zone simply stops moving and a half-taken zone pays nobody.
- **Touch HUD** built in code: left-thumb virtual stick, right-thumb look,
  fire / aim / crouch / jump / sprint / reload. Multi-touch is tracked per
  finger index, so moving and looking at once works.
- **Five weapons** with per-weapon fire interval, spread, recoil spring,
  magazine and reload.
- **AI soldiers** walking between zones, driving the exported animation set
  from actual movement state.

Level build cost at startup: ~200 ms for 16 terrain chunks, 190 rocks, 114
trench bays, 47 sandbag sets, 25 props and 5 zones. Repeated geometry is drawn
through `MultiMeshInstance3D`, which keeps the whole scene at ~154 draw calls.

## APK

```bash
export ANDROID_SDK_ROOT=/path/to/android-sdk
export GODOT_ANDROID_KEYSTORE=/path/to/debug.keystore
tools/export_apk.sh              # debug, installable by sideload
tools/export_apk.sh --release    # smaller, still debug-signed here
```

The script preflights the three things that actually go wrong — missing export
templates, missing Android build-tools, missing keystore — and prints the
exact command to fix each, then verifies the signature and manifest of what it
produced.

Uses Godot's prebuilt Android template rather than a Gradle build, so the only
Android toolchain pieces needed are `apksigner` and `zipalign` from
build-tools; no Gradle, no NDK.

| | |
| --- | --- |
| Package | `com.mehmetdem.polyfield2` |
| Label | Polyfield 2 |
| Version | 0.1.0 (code 1) |
| ABI | arm64-v8a only |
| Target SDK | 36 |
| Renderer | Vulkan, Forward Mobile |
| Size | ~45 MB debug, ~43 MB release |
| Permissions | VIBRATE, WAKE_LOCK — no network, no storage |

**The keystore is a debug key.** It is fine for sideloading and testing and is
not usable as a Play Store upload key; generate a real one before publishing.
`build/` is gitignored — a 45 MB binary does not belong in the repository.

## Verification

Two harnesses, both headless:

```bash
# render any GLB from several angles
blender -b --python tools/blender/preview.py -- <file.glb> out.png --mode grid --clay

# render the running game
xvfb-run -a godot --resolution 1280x720 -- --shot out.png --shot-frame 150
```

The in-game one also prints frame stats (objects, primitives, draw calls) so a
change that quietly doubles the draw calls is visible immediately.

## Known gaps

- **Sound is synthesised, not recorded.** No CC0 game-audio library proved
  reachable without an API key, so `tools/texgen/gen_sounds.py` builds the
  bank from noise transients, resonant bodies and decay tails. Replacing it
  with recorded audio needs only new WAVs of the same names.

- Soldier proportions read correctly but the legs are still slightly long
  against the torso; a proportion pass would improve the silhouette.
- No LOD chain is authored for the meshes — Godot's automatic mesh LOD is
  doing the work. Hand-authored LODs are the next real performance win.
- Bots steer with whisker rays and separation, not a navmesh. They avoid what
  is directly ahead but will not path around a large obstacle.

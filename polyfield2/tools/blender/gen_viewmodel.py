"""Generate the first-person viewmodel: arms plus a working weapon.

    blender -b --python gen_viewmodel.py

The first build showed a static weapon mesh floating in front of the camera
with no arms and no motion — nothing moved when you fired, nothing moved when
you reloaded. This builds the thing properly:

  * two arms (sleeve, forearm, hand with fingers) actually gripping the weapon,
  * the weapon split into moving parts — charging handle/bolt, magazine,
    trigger, safety — each on its own bone,
  * animation clips that drive those parts: the bolt cycles on every shot, the
    magazine leaves the well and a fresh one goes in on reload.

Viewmodel space is camera space: origin at the eye, +Y forward in Blender,
which the exporter flips to -Z forward for Godot.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

import pf_lib as pf
from gen_fortifications import _bevelled_box

FPS = 30

# Where the weapon sits relative to the eye when hip-carried.
WEAPON_ORIGIN = Vector((0.105, 0.30, -0.115))


# --------------------------------------------------------------------------
# Skeleton
# --------------------------------------------------------------------------

def _skeleton():
    """name, parent, head, tail — all in viewmodel (camera) space."""
    weapon = WEAPON_ORIGIN
    return [
        ("VM_Root", None, (0.0, 0.0, 0.0), (0.0, 0.08, 0.0)),
        ("Weapon", "VM_Root", tuple(weapon), tuple(weapon + Vector((0, 0.16, 0)))),
        # Moving parts, each a child of the weapon so they ride with it.
        ("Bolt", "Weapon", tuple(weapon + Vector((0.028, 0.10, 0.030))),
                           tuple(weapon + Vector((0.028, 0.18, 0.030)))),
        ("Magazine", "Weapon", tuple(weapon + Vector((0.0, 0.03, -0.055))),
                               tuple(weapon + Vector((0.0, 0.03, -0.175)))),
        ("Trigger", "Weapon", tuple(weapon + Vector((0.0, -0.01, -0.045))),
                              tuple(weapon + Vector((0.0, -0.01, -0.075)))),
        ("Charging", "Weapon", tuple(weapon + Vector((0.052, 0.12, 0.032))),
                               tuple(weapon + Vector((0.092, 0.12, 0.032)))),
        # Right arm: comes in low from the right, hand on the grip.
        ("ArmR_Upper", "VM_Root", (0.20, -0.20, -0.28), (0.16, -0.02, -0.24)),
        ("ArmR_Fore", "ArmR_Upper", (0.16, -0.02, -0.24), (0.115, 0.16, -0.185)),
        ("ArmR_Hand", "ArmR_Fore", (0.115, 0.16, -0.185), (0.105, 0.25, -0.165)),
        # Left arm: reaches across to the handguard.
        ("ArmL_Upper", "VM_Root", (-0.19, -0.19, -0.30), (-0.10, 0.02, -0.24)),
        ("ArmL_Fore", "ArmL_Upper", (-0.10, 0.02, -0.24), (0.03, 0.30, -0.175)),
        ("ArmL_Hand", "ArmL_Fore", (0.03, 0.30, -0.175), (0.08, 0.40, -0.155)),
    ]


def build_armature(name="viewmodel_rig"):
    data = bpy.data.armatures.new(name)
    armature = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(armature)
    pf.select_only(armature)
    bpy.ops.object.mode_set(mode="EDIT")

    created = {}
    for bone_name, parent, head, tail in _skeleton():
        bone = data.edit_bones.new(bone_name)
        bone.head = Vector(head)
        bone.tail = Vector(tail)
        bone.use_deform = bone_name != "VM_Root"
        if parent:
            bone.parent = created[parent]
            bone.use_connect = False
        created[bone_name] = bone

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


# --------------------------------------------------------------------------
# Weapon geometry
# --------------------------------------------------------------------------

def _tube(name, radius, length, location, rotation=(math.pi / 2, 0, 0), sides=10):
    obj = pf.make_cylinder(name, radius=radius, depth=length, segments=sides)
    obj.rotation_euler = Euler(rotation)
    obj.location = Vector(location)
    return obj


def build_weapon():
    """Return dict of part-group -> list of objects, in weapon-local space."""
    o = WEAPON_ORIGIN
    steel, wood, polymer = [], [], []

    def part(group, name, size, offset, rotation=(0, 0, 0), bevel=0.004):
        obj = _bevelled_box(name, size, bevel=bevel)
        obj.location = o + Vector(offset)
        obj.rotation_euler = Euler(rotation)
        group.append(obj)
        return obj

    # Receiver, the spine of the weapon.
    part(steel, "vm_receiver", (0.052, 0.30, 0.062), (0.0, 0.06, 0.0))
    part(steel, "vm_upper", (0.048, 0.26, 0.030), (0.0, 0.08, 0.040))
    part(steel, "vm_ejection", (0.006, 0.070, 0.028), (0.027, 0.115, 0.030))

    # Barrel and gas system.
    steel.append(_tube("vm_barrel", 0.0115, 0.34, o + Vector((0.0, 0.36, 0.012))))
    steel.append(_tube("vm_gasblock", 0.020, 0.045, o + Vector((0.0, 0.40, 0.030))))
    steel.append(_tube("vm_muzzle", 0.017, 0.055, o + Vector((0.0, 0.545, 0.012))))
    for index in range(3):
        part(steel, f"vm_muzzle_port_{index}", (0.036, 0.006, 0.020),
             (0.0, 0.535 + index * 0.014, 0.012))

    # Sights: a real rear aperture and a protected front post.
    part(steel, "vm_rear_base", (0.030, 0.040, 0.016), (0.0, 0.175, 0.058))
    part(steel, "vm_rear_wing_l", (0.006, 0.030, 0.030), (-0.014, 0.175, 0.072))
    part(steel, "vm_rear_wing_r", (0.006, 0.030, 0.030), (0.014, 0.175, 0.072))
    part(steel, "vm_front_post", (0.005, 0.006, 0.030), (0.0, 0.455, 0.056))
    part(steel, "vm_front_wing_l", (0.005, 0.024, 0.034), (-0.017, 0.455, 0.058))
    part(steel, "vm_front_wing_r", (0.005, 0.024, 0.034), (0.017, 0.455, 0.058))

    # Trigger group and guard.
    part(steel, "vm_guard_front", (0.008, 0.008, 0.036), (0.0, 0.005, -0.052))
    part(steel, "vm_guard_bottom", (0.010, 0.062, 0.008), (0.0, -0.026, -0.068))
    part(steel, "vm_guard_rear", (0.008, 0.008, 0.036), (0.0, -0.057, -0.052))
    part(steel, "vm_safety", (0.030, 0.012, 0.012), (0.024, -0.045, -0.012))

    # Handguard and stock.
    part(wood, "vm_handguard", (0.052, 0.20, 0.050), (0.0, 0.30, 0.004))
    for index in range(5):
        part(wood, f"vm_vent_{index}", (0.056, 0.008, 0.016), (0.0, 0.235 + index * 0.030, 0.020))
    part(wood, "vm_stock", (0.048, 0.20, 0.070), (0.0, -0.14, -0.020))
    part(wood, "vm_comb", (0.042, 0.14, 0.032), (0.0, -0.11, 0.022))
    part(polymer, "vm_buttplate", (0.052, 0.014, 0.090), (0.0, -0.245, -0.028))
    part(polymer, "vm_grip", (0.036, 0.048, 0.100), (0.0, -0.060, -0.090),
         rotation=(0.30, 0.0, 0.0))
    part(polymer, "vm_grip_strap", (0.038, 0.014, 0.070), (0.0, -0.082, -0.086),
         rotation=(0.30, 0.0, 0.0))

    return {"steel": steel, "wood": wood, "polymer": polymer}


def build_moving_parts():
    """Parts bound to their own bones so animation can drive them."""
    o = WEAPON_ORIGIN
    parts = {}

    bolt = _bevelled_box("vm_bolt", (0.040, 0.090, 0.026), bevel=0.004)
    bolt.location = o + Vector((0.0, 0.115, 0.030))
    parts["Bolt"] = [bolt]

    handle = _bevelled_box("vm_charging", (0.046, 0.016, 0.014), bevel=0.003)
    handle.location = o + Vector((0.046, 0.120, 0.032))
    knob = _bevelled_box("vm_charging_knob", (0.018, 0.020, 0.020), bevel=0.005)
    knob.location = o + Vector((0.070, 0.120, 0.032))
    parts["Charging"] = [handle, knob]

    magazine = _bevelled_box("vm_magazine", (0.030, 0.058, 0.130), bevel=0.006)
    magazine.location = o + Vector((0.0, 0.020, -0.110))
    magazine.rotation_euler = Euler((-0.10, 0.0, 0.0))
    floor_plate = _bevelled_box("vm_mag_floor", (0.034, 0.062, 0.010), bevel=0.003)
    floor_plate.location = o + Vector((0.0, 0.028, -0.176))
    parts["Magazine"] = [magazine, floor_plate]

    trigger = _bevelled_box("vm_trigger", (0.008, 0.014, 0.032), bevel=0.003)
    trigger.location = o + Vector((0.0, -0.026, -0.048))
    parts["Trigger"] = [trigger]

    return parts


# --------------------------------------------------------------------------
# Arms
# --------------------------------------------------------------------------

def _limb(name, p0, p1, width, thickness):
    """A blocky rectangular limb segment between two points.

    Deliberately a box, not a tapered cylinder: the arms read better as clean
    rectangular blocks than as low-poly tubes, and there is nothing to shade
    badly at viewmodel distance.
    """
    start, end = Vector(p0), Vector(p1)
    axis = end - start
    length = axis.length
    rotation = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()

    bm = bmesh.new()
    corners = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
    rings = []
    for level in (0.0, 1.0):
        ring = []
        for cx, cy in corners:
            local = Vector((cx * width, cy * thickness, level * length))
            ring.append(bm.verts.new(start + rotation @ local))
        rings.append(ring)
    for index in range(4):
        nxt = (index + 1) % 4
        bm.faces.new((rings[0][index], rings[0][nxt], rings[1][nxt], rings[1][index]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return pf.bm_to_object(bm, name)


def _hand(name, wrist, direction, side, spread=0.030):
    """One block. No fingers.

    Modelled fingers at this scale read as a bundle of sausages rather than a
    hand; a single clean block is both cheaper and easier to look at.
    """
    direction = Vector(direction).normalized()
    basis = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()

    block = _bevelled_box(f"{name}_block", (0.070, 0.062, 0.105), bevel=0.012)
    block.location = Vector(wrist) + direction * 0.052
    block.rotation_euler = basis.to_euler()
    return [block]


def build_arms():
    sleeve, skin = [], []
    bones = dict((name, (Vector(head), Vector(tail))) for name, _p, head, tail in _skeleton())

    for side_name, sign in (("R", 1.0), ("L", -1.0)):
        upper_head, upper_tail = bones[f"Arm{side_name}_Upper"]
        fore_head, fore_tail = bones[f"Arm{side_name}_Fore"]
        hand_head, hand_tail = bones[f"Arm{side_name}_Hand"]

        sleeve.append(_limb(f"vm_arm{side_name}_upper", upper_head, upper_tail, 0.105, 0.095))
        sleeve.append(_limb(f"vm_arm{side_name}_fore", fore_head, fore_tail, 0.092, 0.082))
        # Cuff where the sleeve ends and the hand begins.
        cuff = _bevelled_box(f"vm_arm{side_name}_cuff", (0.098, 0.030, 0.090), bevel=0.006)
        cuff.location = fore_tail
        sleeve.append(cuff)

        skin += _hand(f"vm_hand{side_name}", hand_head, hand_tail - hand_head, sign)

    return sleeve, skin


# --------------------------------------------------------------------------
# Skinning
# --------------------------------------------------------------------------

def rigid_bind(obj, armature, bone_name):
    """Bind every vertex of `obj` fully to one bone."""
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = armature
    obj.parent = armature


def skin_arms(obj, armature):
    """Distance-weighted skinning limited to the arm chains.

    Arms must not pick up weight from the weapon bones: a forearm that follows
    the magazine tears the mesh apart the moment a reload plays.
    """
    chains = [name for name, _p, _h, _t in _skeleton() if name.startswith("Arm")]
    segments = {name: (np.array(head), np.array(tail))
                for name, _p, head, tail in _skeleton() if name in chains}

    mesh = obj.data
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", coords)
    points = coords.reshape(-1, 3)

    names = list(segments)
    distances = []
    for name in names:
        head, tail = segments[name]
        axis = tail - head
        length_sq = float(axis @ axis)
        t = np.clip(((points - head) @ axis) / max(length_sq, 1e-9), 0.0, 1.0)
        closest = head[None, :] + t[:, None] * axis[None, :]
        distances.append(np.linalg.norm(points - closest, axis=1))
    distances = np.stack(distances, axis=1)

    groups = {name: obj.vertex_groups.new(name=name) for name in names}
    order = np.argsort(distances, axis=1)[:, :2]
    rows = np.arange(points.shape[0])[:, None]
    picked = distances[rows, order]
    weights = 1.0 / np.power(picked + 1e-4, 4.0)
    weights /= weights.sum(axis=1, keepdims=True)

    for slot in range(2):
        for index, name in enumerate(names):
            mask = order[:, slot] == index
            if not mask.any():
                continue
            indices = np.nonzero(mask)[0]
            values = np.round(weights[indices, slot], 3)
            for bucket in np.unique(values):
                groups[name].add(indices[values == bucket].tolist(), float(bucket), "ADD")

    modifier = obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = armature
    obj.parent = armature


# --------------------------------------------------------------------------
# Animation
# --------------------------------------------------------------------------

def _key(armature, bone, frame, rotation=None, location=None):
    pose_bone = armature.pose.bones[bone]
    pose_bone.rotation_mode = "XYZ"
    if rotation is not None:
        pose_bone.rotation_euler = Euler([math.radians(a) for a in rotation])
        pose_bone.keyframe_insert("rotation_euler", frame=frame)
    if location is not None:
        pose_bone.location = Vector(location)
        pose_bone.keyframe_insert("location", frame=frame)


def _rest(armature):
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "XYZ"
        pose_bone.rotation_euler = Euler((0, 0, 0))
        pose_bone.location = Vector((0, 0, 0))


def _new_action(armature, name):
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    armature.animation_data.action = action
    return action


def build_animations(armature):
    armature.animation_data_create()
    clips = []

    # --- idle: breathing sway on the weapon, arms follow --------------------
    action = _new_action(armature, "vm_idle")
    _rest(armature)
    length = 96
    for frame in range(1, length + 1):
        phase = (frame - 1) / float(length)
        breath = math.sin(phase * math.tau)
        drift = math.sin(phase * math.tau * 0.5)
        _key(armature, "Weapon", frame,
             rotation=(breath * 1.1, drift * 0.8, drift * 1.4),
             location=(drift * 0.004, 0.0, breath * 0.005))
        _key(armature, "ArmR_Fore", frame, rotation=(breath * 1.0, 0.0, 0.0))
        _key(armature, "ArmL_Fore", frame, rotation=(breath * 1.2, 0.0, 0.0))
    clips.append((action, length, True))

    # --- walk: figure-eight bob ---------------------------------------------
    action = _new_action(armature, "vm_walk")
    _rest(armature)
    length = 32
    for frame in range(1, length + 1):
        phase = (frame - 1) / float(length)
        _key(armature, "Weapon", frame,
             rotation=(math.sin(phase * math.tau * 2.0) * 2.2,
                       math.sin(phase * math.tau) * 2.6,
                       math.sin(phase * math.tau) * 3.2),
             location=(math.sin(phase * math.tau) * 0.010, 0.0,
                       abs(math.cos(phase * math.tau)) * 0.009 - 0.004))
        _key(armature, "ArmL_Fore", frame,
             rotation=(math.sin(phase * math.tau * 2.0) * 2.0, 0.0, 0.0))
    clips.append((action, length, True))

    # --- fire: kick, muzzle rise, and a full bolt cycle ---------------------
    action = _new_action(armature, "vm_fire")
    _rest(armature)
    # frame, recoil amount, bolt travel (metres back), trigger pull
    stages = [(1, 0.0, 0.0, 0.0), (2, 1.0, 0.55, 1.0), (4, 0.72, 1.0, 1.0),
              (6, 0.40, 0.45, 0.6), (9, 0.16, 0.0, 0.2), (13, 0.0, 0.0, 0.0)]
    for frame, kick, bolt, trigger in stages:
        _key(armature, "Weapon", frame,
             rotation=(-kick * 6.5, 0.0, kick * 2.2),
             location=(0.0, -kick * 0.045, kick * 0.012))
        # Bolt rides straight back in the receiver, then returns.
        _key(armature, "Bolt", frame, location=(0.0, -bolt * 0.075, 0.0))
        _key(armature, "Charging", frame, location=(0.0, -bolt * 0.075, 0.0))
        _key(armature, "Trigger", frame, rotation=(trigger * 18.0, 0.0, 0.0))
        _key(armature, "ArmR_Fore", frame, rotation=(-kick * 5.0, 0.0, 0.0))
        _key(armature, "ArmL_Fore", frame, rotation=(-kick * 4.0, 0.0, 0.0))
    clips.append((action, 13, False))

    # --- reload: magazine out, new one in, bolt released --------------------
    action = _new_action(armature, "vm_reload")
    _rest(armature)
    reload_stages = [
        # frame, weapon tilt, mag drop, left-arm reach, bolt back
        (1,   0.0,  0.0,  0.0, 0.0),
        (8,  -14.0, 0.0,  0.0, 0.0),
        (16, -18.0, 1.0, -55.0, 0.0),   # magazine falls clear
        (26, -18.0, 1.0, -70.0, 0.0),   # hand goes to the pouch
        (38, -16.0, 0.25, -40.0, 0.0),  # fresh magazine offered up
        (46, -12.0, 0.0, -12.0, 0.0),   # seated
        (54,  -6.0, 0.0, -30.0, 1.0),   # bolt pulled
        (60,   0.0, 0.0,  0.0, 0.0),    # released, back on target
    ]
    for frame, tilt, drop, reach, bolt in reload_stages:
        _key(armature, "Weapon", frame, rotation=(tilt, tilt * 0.4, -tilt * 0.5),
             location=(0.0, -0.02 if tilt else 0.0, tilt * 0.001))
        _key(armature, "Magazine", frame, location=(0.0, 0.0, -drop * 0.30))
        _key(armature, "Bolt", frame, location=(0.0, -bolt * 0.075, 0.0))
        _key(armature, "Charging", frame, location=(0.0, -bolt * 0.075, 0.0))
        _key(armature, "ArmL_Upper", frame, rotation=(reach * 0.5, 0.0, reach * 0.2))
        _key(armature, "ArmL_Fore", frame, rotation=(reach, 0.0, 0.0))
        _key(armature, "ArmR_Fore", frame, rotation=(tilt * 0.3, 0.0, 0.0))
    clips.append((action, 60, False))

    # --- aim: weapon rises to the sight line --------------------------------
    action = _new_action(armature, "vm_aim")
    _rest(armature)
    for frame, blend in ((1, 0.0), (8, 1.0), (40, 1.0)):
        _key(armature, "Weapon", frame,
             rotation=(blend * 1.2, 0.0, 0.0),
             location=(-blend * 0.105, blend * 0.045, blend * 0.058))
        _key(armature, "ArmR_Fore", frame, rotation=(blend * 6.0, 0.0, 0.0))
        _key(armature, "ArmL_Upper", frame, rotation=(blend * 9.0, 0.0, blend * 5.0))
        _key(armature, "ArmL_Fore", frame, rotation=(blend * 12.0, 0.0, 0.0))
    clips.append((action, 40, True))

    # --- draw: weapon swings up into the carry ------------------------------
    action = _new_action(armature, "vm_draw")
    _rest(armature)
    for frame, amount in ((1, 1.0), (10, 0.35), (18, 0.0)):
        _key(armature, "Weapon", frame,
             rotation=(-amount * 55.0, amount * 20.0, 0.0),
             location=(0.0, -amount * 0.06, -amount * 0.22))
        _key(armature, "ArmR_Upper", frame, rotation=(-amount * 22.0, 0.0, 0.0))
        _key(armature, "ArmL_Upper", frame, rotation=(-amount * 26.0, 0.0, 0.0))
    clips.append((action, 18, False))

    for action, _length, _loop in clips:
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"
                point.easing = "AUTO"
    return clips


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def main():
    pf.reset_scene()
    pf.report("First-person viewmodel")

    armature = build_armature()

    # Static weapon body: bound rigidly to the Weapon bone.
    groups = build_weapon()
    body_parts = []
    for band, parts in groups.items():
        merged = pf.join_objects(parts, f"vm_body_{band}")
        pf.select_only(merged)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        pf.box_project_uv(merged, scale=0.22)
        body_parts.append((band, merged))

    from gen_weapons import BANDS
    for band, merged in body_parts:
        lo, hi = BANDS[band]
        pf.atlas_uv(merged, lo, hi)

    body = pf.join_objects([m for _b, m in body_parts], "vm_weapon")
    pf.shade_flat(body)
    pf.triangulate(body)
    pf.set_material(body, "gunmetal")
    rigid_bind(body, armature, "Weapon")

    # Moving parts, one rigid bind each.
    moving = []
    for bone_name, parts in build_moving_parts().items():
        merged = pf.join_objects(parts, f"vm_part_{bone_name.lower()}")
        pf.select_only(merged)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        pf.box_project_uv(merged, scale=0.22)
        lo, hi = BANDS["steel" if bone_name != "Magazine" else "polymer"]
        pf.atlas_uv(merged, lo, hi)
        pf.shade_flat(merged)
        pf.triangulate(merged)
        pf.set_material(merged, "gunmetal")
        rigid_bind(merged, armature, bone_name)
        moving.append(merged)

    # Arms: sleeves skinned to the arm chains, hands rigid to the wrists.
    sleeve_parts, hand_parts = build_arms()
    sleeves = pf.join_objects(sleeve_parts, "vm_sleeves")
    pf.select_only(sleeves)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.box_project_uv(sleeves, scale=0.30)
    pf.shade_flat(sleeves)
    pf.triangulate(sleeves)
    pf.set_material(sleeves, "uniform_ranger")
    skin_arms(sleeves, armature)

    hands = pf.join_objects(hand_parts, "vm_hands")
    pf.select_only(hands)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pf.box_project_uv(hands, scale=0.22)
    pf.shade_flat(hands)
    pf.triangulate(hands)
    pf.set_material(hands, "skin")
    skin_arms(hands, armature)

    clips = build_animations(armature)

    meshes = [body] + moving + [sleeves, hands]
    total = sum(pf.tri_count(m) for m in meshes)
    print(f"  viewmodel: {total} tris across {len(meshes)} meshes, "
          f"{len(armature.data.bones)} bones, {len(clips)} clips")
    for action, length, loop in clips:
        print(f"      {action.name:<12} {length:3d} frames ({length / FPS:.2f}s)"
              f"{'  loop' if loop else ''}")

    path = os.path.join(pf.MODEL_DIR, "viewmodel.glb")
    pf.export_glb([armature] + meshes, path, with_animation=True)


if __name__ == "__main__":
    main()

"""Generate the rigged, animated soldier.

    blender -b --python gen_character.py

Builds a low-poly 1.78 m soldier, a 24-bone rig, distance-based skin weights
and eleven animation clips, then exports one GLB per faction.

Skinning is done by explicit bone-segment distance rather than Blender's heat
weighting: heat diffusion needs watertight, connected geometry and fails on a
figure assembled from separate limb prisms, which is exactly what this is.
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

# --------------------------------------------------------------------------
# Skeleton
# --------------------------------------------------------------------------
# name, parent, head, tail. Rest pose is a relaxed A-pose: arms hang, which
# keeps shoulder weights sane without a corrective pass.

def _skeleton():
    bones = [
        ("Root",       None,      (0.00, 0.00, 0.00), (0.00, 0.16, 0.00)),
        ("Hips",       "Root",    (0.00, 0.00, 0.94), (0.00, 0.00, 1.06)),
        ("Spine",      "Hips",    (0.00, 0.00, 1.06), (0.00, 0.00, 1.24)),
        ("Chest",      "Spine",   (0.00, 0.00, 1.24), (0.00, 0.00, 1.43)),
        ("Neck",       "Chest",   (0.00, 0.00, 1.43), (0.00, 0.00, 1.53)),
        ("Head",       "Neck",    (0.00, 0.00, 1.53), (0.00, 0.00, 1.76)),
    ]
    for side, sign in (("L", 1.0), ("R", -1.0)):
        bones += [
            (f"Shoulder.{side}", "Chest",           (sign * 0.045, 0.0, 1.40), (sign * 0.185, 0.0, 1.42)),
            (f"UpperArm.{side}", f"Shoulder.{side}", (sign * 0.185, 0.0, 1.42), (sign * 0.215, 0.0, 1.15)),
            (f"LowerArm.{side}", f"UpperArm.{side}", (sign * 0.215, 0.0, 1.15), (sign * 0.230, 0.0, 0.92)),
            (f"Hand.{side}",     f"LowerArm.{side}", (sign * 0.230, 0.0, 0.92), (sign * 0.235, 0.0, 0.80)),
            (f"UpperLeg.{side}", "Hips",             (sign * 0.105, 0.0, 0.92), (sign * 0.115, 0.0, 0.50)),
            (f"LowerLeg.{side}", f"UpperLeg.{side}", (sign * 0.115, 0.0, 0.50), (sign * 0.120, 0.0, 0.10)),
            (f"Foot.{side}",     f"LowerLeg.{side}", (sign * 0.120, 0.0, 0.10), (sign * 0.120, 0.17, 0.04)),
            (f"Toe.{side}",      f"Foot.{side}",     (sign * 0.120, 0.17, 0.04), (sign * 0.120, 0.25, 0.03)),
        ]
    # Where the weapon hangs. Godot attaches the gun with a BoneAttachment3D.
    bones.append(("WeaponSocket", "Hand.R", (-0.24, 0.10, 0.90), (-0.24, 0.26, 0.90)))
    return bones


def build_armature(name="soldier_rig"):
    armature_data = bpy.data.armatures.new(name)
    armature = bpy.data.objects.new(name, armature_data)
    bpy.context.collection.objects.link(armature)
    pf.select_only(armature)
    bpy.ops.object.mode_set(mode="EDIT")

    created = {}
    for bone_name, parent, head, tail in _skeleton():
        bone = armature_data.edit_bones.new(bone_name)
        bone.head = Vector(head)
        bone.tail = Vector(tail)
        bone.use_deform = bone_name not in ("Root", "WeaponSocket")
        if parent:
            bone.parent = created[parent]
            bone.use_connect = False
        created[bone_name] = bone

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


# --------------------------------------------------------------------------
# Body mesh
# --------------------------------------------------------------------------

def _prism(name, p0, p1, r0, r1, sides=6, twist=0.0):
    """Tapered prism between two points — arms, legs, neck."""
    start, end = Vector(p0), Vector(p1)
    axis = end - start
    length = axis.length
    if length < 1e-6:
        raise ValueError(f"{name}: zero-length prism")
    rotation = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()

    bm = bmesh.new()
    rings = []
    for level, radius in ((0.0, r0), (1.0, r1)):
        ring = []
        for index in range(sides):
            angle = (index / sides) * math.tau + twist
            local = Vector((math.cos(angle) * radius[0], math.sin(angle) * radius[1],
                            level * length))
            ring.append(bm.verts.new(start + rotation @ local))
        rings.append(ring)
    bm.verts.ensure_lookup_table()
    for index in range(sides):
        nxt = (index + 1) % sides
        bm.faces.new((rings[0][index], rings[0][nxt], rings[1][nxt], rings[1][index]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return pf.bm_to_object(bm, name)


def build_body():
    """Return (cloth, skin, gear) — one group per uniform atlas band.

    The split has to match materials.UNIFORM_BANDS exactly; head and neck get
    their own band so the faction accent painted on the gear band can never
    end up across the soldier's face.
    """
    cloth, skin, gear = [], [], []

    # Torso: chest tapering into the waist, plus a slight back curve.
    chest = _bevelled_box("chest", (0.45, 0.26, 0.35), bevel=0.04)
    chest.location = (0.0, 0.0, 1.28)
    cloth.append(chest)
    waist = _bevelled_box("waist", (0.36, 0.22, 0.17), bevel=0.035)
    waist.location = (0.0, 0.0, 1.05)
    cloth.append(waist)
    hips = _bevelled_box("hips", (0.40, 0.25, 0.22), bevel=0.045)
    hips.location = (0.0, 0.0, 0.92)
    cloth.append(hips)

    neck = _prism("neck", (0, 0, 1.40), (0, 0, 1.54), (0.070, 0.062), (0.062, 0.056), sides=6)
    skin.append(neck)

    # Head and helmet.
    head = _bevelled_box("head", (0.20, 0.23, 0.24), bevel=0.05)
    head.location = (0.0, 0.015, 1.635)
    skin.append(head)

    helmet = _prism("helmet", (0, 0.008, 1.635), (0, 0.008, 1.765),
                    (0.132, 0.142), (0.085, 0.09), sides=8)
    gear.append(helmet)
    brim = _prism("helmet_brim", (0, 0.012, 1.612), (0, 0.012, 1.648),
                  (0.145, 0.163), (0.136, 0.148), sides=8)
    gear.append(brim)

    # Limbs.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        upper = _prism(f"upperarm_{side}", (sign * 0.185, 0, 1.42), (sign * 0.215, 0, 1.15),
                       (0.075, 0.075), (0.062, 0.062), sides=8)
        lower = _prism(f"lowerarm_{side}", (sign * 0.215, 0, 1.15), (sign * 0.230, 0, 0.93),
                       (0.062, 0.062), (0.050, 0.053), sides=8)
        cloth += [upper, lower]

        hand = _bevelled_box(f"hand_{side}", (0.085, 0.065, 0.14), bevel=0.022)
        hand.location = (sign * 0.232, 0.0, 0.865)
        gear.append(hand)

        thigh = _prism(f"thigh_{side}", (sign * 0.105, 0, 0.95), (sign * 0.115, 0, 0.50),
                       (0.105, 0.112), (0.082, 0.088), sides=8)
        shin = _prism(f"shin_{side}", (sign * 0.115, 0, 0.50), (sign * 0.120, 0, 0.12),
                      (0.082, 0.088), (0.062, 0.066), sides=8)
        cloth += [thigh, shin]

        boot = _bevelled_box(f"boot_{side}", (0.135, 0.155, 0.18), bevel=0.028)
        boot.location = (sign * 0.120, 0.0, 0.13)
        gear.append(boot)
        toe = _bevelled_box(f"toe_{side}", (0.135, 0.185, 0.085), bevel=0.028)
        toe.location = (sign * 0.120, 0.08, 0.045)
        gear.append(toe)

    # Webbing, pouches and pack — the gear silhouette that separates a soldier
    # from a mannequin at 60 m.
    belt = _bevelled_box("belt", (0.42, 0.26, 0.06), bevel=0.018)
    belt.location = (0.0, 0.0, 1.00)
    gear.append(belt)

    for sign in (-1, 1):
        strap = _bevelled_box(f"strap_{sign}", (0.055, 0.235, 0.02), bevel=0.008)
        strap.location = (sign * 0.085, 0.0, 1.36)
        strap.rotation_euler = Euler((0.0, sign * 0.12, 0.0))
        gear.append(strap)
        pouch = _bevelled_box(f"pouch_{sign}", (0.10, 0.075, 0.11), bevel=0.018)
        pouch.location = (sign * 0.10, -0.115, 1.02)
        gear.append(pouch)

    pack = _bevelled_box("pack", (0.30, 0.15, 0.30), bevel=0.03)
    pack.location = (0.0, -0.19, 1.30)
    gear.append(pack)
    roll = _prism("bedroll", (-0.15, -0.24, 1.44), (0.15, -0.24, 1.44),
                  (0.055, 0.055), (0.055, 0.055), sides=6)
    gear.append(roll)

    return cloth, skin, gear


# --------------------------------------------------------------------------
# Skinning
# --------------------------------------------------------------------------

def _segment_distance(points, head, tail):
    """Distance from each point to a bone segment."""
    head = np.asarray(head, dtype=np.float64)
    tail = np.asarray(tail, dtype=np.float64)
    axis = tail - head
    length_sq = float(axis @ axis)
    if length_sq < 1e-12:
        return np.linalg.norm(points - head, axis=1)
    t = np.clip(((points - head) @ axis) / length_sq, 0.0, 1.0)
    closest = head[None, :] + t[:, None] * axis[None, :]
    return np.linalg.norm(points - closest, axis=1)


def skin_mesh(obj, armature, influences=3, falloff=4.0):
    """Assign vertex weights from bone-segment distance.

    Each vertex takes the `influences` nearest deform bones, weighted by
    1/d^falloff and normalised. A high falloff keeps the influence local, so
    a hand vertex is not dragged around by the spine.
    """
    deform = [(name, head, tail) for name, parent, head, tail in _skeleton()
              if name not in ("Root", "WeaponSocket")]

    mesh = obj.data
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", coords)
    points = coords.reshape(-1, 3)

    distances = np.stack([_segment_distance(points, head, tail)
                          for _name, head, tail in deform], axis=1)

    groups = {name: obj.vertex_groups.new(name=name) for name, _h, _t in deform}

    order = np.argsort(distances, axis=1)[:, :influences]
    rows = np.arange(points.shape[0])[:, None]
    picked = distances[rows, order]
    weights = 1.0 / np.power(picked + 1e-4, falloff)
    weights /= weights.sum(axis=1, keepdims=True)

    for slot in range(influences):
        for bone_index in range(len(deform)):
            mask = order[:, slot] == bone_index
            if not mask.any():
                continue
            name = deform[bone_index][0]
            indices = np.nonzero(mask)[0]
            # add_multiple would be nicer, but the API takes one weight value,
            # so bucket vertices by rounded weight to keep the call count low.
            values = weights[indices, slot]
            for bucket in np.unique(np.round(values, 3)):
                subset = indices[np.round(values, 3) == bucket]
                groups[name].add(subset.tolist(), float(bucket), "ADD")

    modifier = obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = armature
    obj.parent = armature


# --------------------------------------------------------------------------
# Animation
# --------------------------------------------------------------------------

def _pose(armature, bone, frame, rotation=None, location=None):
    pose_bone = armature.pose.bones[bone]
    pose_bone.rotation_mode = "XYZ"
    if rotation is not None:
        pose_bone.rotation_euler = Euler([math.radians(a) for a in rotation])
        pose_bone.keyframe_insert("rotation_euler", frame=frame)
    if location is not None:
        pose_bone.location = Vector(location)
        pose_bone.keyframe_insert("location", frame=frame)


def _new_action(armature, name):
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    armature.animation_data.action = action
    return action


def _rest(armature):
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "XYZ"
        pose_bone.rotation_euler = Euler((0, 0, 0))
        pose_bone.location = Vector((0, 0, 0))


def _cycle(armature, name, length, poser):
    """Build a looping clip; the last frame repeats frame 1 exactly."""
    action = _new_action(armature, name)
    _rest(armature)
    for frame in range(1, length + 1):
        phase = (frame - 1) / float(length)
        poser(frame, phase)
    return action, length


def _walk_poser(armature, stride=32.0, lift=18.0, arm=22.0, lean=6.0, bob=0.035):
    def poser(frame, phase):
        swing = math.sin(phase * math.tau)
        opposite = -swing
        _pose(armature, "Hips", frame,
              rotation=(lean, math.sin(phase * math.tau * 2.0) * 3.0, swing * 4.0),
              location=(0.0, 0.0, abs(math.cos(phase * math.tau)) * bob))
        _pose(armature, "Spine", frame, rotation=(lean * 0.4, 0.0, -swing * 3.0))
        _pose(armature, "Chest", frame, rotation=(0.0, 0.0, -swing * 4.0))
        _pose(armature, "Head", frame, rotation=(-lean * 0.6, 0.0, 0.0))

        for side, sign in (("L", 1.0), ("R", -1.0)):
            leg = swing * sign
            knee = max(0.0, -leg) * lift + lift * 0.25
            _pose(armature, f"UpperLeg.{side}", frame, rotation=(leg * stride, 0.0, 0.0))
            _pose(armature, f"LowerLeg.{side}", frame, rotation=(-knee, 0.0, 0.0))
            _pose(armature, f"Foot.{side}", frame,
                  rotation=(max(-25.0, leg * 18.0), 0.0, 0.0))

            hand = opposite * sign
            _pose(armature, f"UpperArm.{side}", frame,
                  rotation=(hand * arm, 0.0, -sign * 8.0))
            _pose(armature, f"LowerArm.{side}", frame,
                  rotation=(-abs(hand) * arm * 0.6 - 12.0, 0.0, 0.0))
    return poser


def _carry_pose(armature, frame, ready=True):
    """Both hands on the weapon — the base for idle, aim and fire."""
    reach = 62.0 if ready else 48.0
    _pose(armature, "UpperArm.R", frame, rotation=(-reach, 0.0, 28.0))
    _pose(armature, "LowerArm.R", frame, rotation=(-72.0, 0.0, -18.0))
    _pose(armature, "Hand.R", frame, rotation=(0.0, 0.0, -12.0))
    _pose(armature, "UpperArm.L", frame, rotation=(-reach - 6.0, 0.0, -42.0))
    _pose(armature, "LowerArm.L", frame, rotation=(-84.0, 0.0, 22.0))
    _pose(armature, "Hand.L", frame, rotation=(0.0, 0.0, 14.0))


def build_animations(armature):
    armature.animation_data_create()
    clips = []

    # idle — weight shift and breathing
    def idle(frame, phase):
        breath = math.sin(phase * math.tau)
        _pose(armature, "Hips", frame, rotation=(0.0, 0.0, breath * 1.6),
              location=(0.0, 0.0, breath * 0.012))
        _pose(armature, "Spine", frame, rotation=(breath * 1.2, 0.0, 0.0))
        _pose(armature, "Chest", frame, rotation=(breath * 1.6, 0.0, -breath * 1.2))
        _pose(armature, "Head", frame, rotation=(-breath * 1.0, 0.0, breath * 2.4))
        _carry_pose(armature, frame, ready=False)
    clips.append(_cycle(armature, "idle", 90, idle))

    clips.append(_cycle(armature, "walk", 32, _walk_poser(armature)))
    clips.append(_cycle(armature, "run", 22,
                        _walk_poser(armature, stride=46.0, lift=34.0, arm=38.0,
                                    lean=14.0, bob=0.06)))

    # crouch idle / walk share a crouched base offset
    def crouch_base(frame, extra_lean=0.0):
        _pose(armature, "Hips", frame, rotation=(16.0 + extra_lean, 0.0, 0.0),
              location=(0.0, 0.0, -0.30))
        _pose(armature, "Spine", frame, rotation=(10.0, 0.0, 0.0))
        for side in ("L", "R"):
            _pose(armature, f"UpperLeg.{side}", frame, rotation=(58.0, 0.0, 0.0))
            _pose(armature, f"LowerLeg.{side}", frame, rotation=(-78.0, 0.0, 0.0))
            _pose(armature, f"Foot.{side}", frame, rotation=(24.0, 0.0, 0.0))

    def crouch_idle(frame, phase):
        breath = math.sin(phase * math.tau)
        crouch_base(frame, extra_lean=breath * 1.2)
        _pose(armature, "Chest", frame, rotation=(breath * 1.4, 0.0, 0.0))
        _carry_pose(armature, frame, ready=True)
    clips.append(_cycle(armature, "crouch_idle", 90, crouch_idle))

    def crouch_walk(frame, phase):
        swing = math.sin(phase * math.tau)
        _pose(armature, "Hips", frame, rotation=(18.0, 0.0, swing * 3.0),
              location=(0.0, 0.0, -0.30 + abs(math.cos(phase * math.tau)) * 0.02))
        _pose(armature, "Spine", frame, rotation=(10.0, 0.0, -swing * 2.0))
        for side, sign in (("L", 1.0), ("R", -1.0)):
            leg = swing * sign
            _pose(armature, f"UpperLeg.{side}", frame, rotation=(58.0 + leg * 22.0, 0.0, 0.0))
            _pose(armature, f"LowerLeg.{side}", frame,
                  rotation=(-78.0 - max(0.0, -leg) * 16.0, 0.0, 0.0))
            _pose(armature, f"Foot.{side}", frame, rotation=(24.0 + leg * 10.0, 0.0, 0.0))
        _carry_pose(armature, frame, ready=True)
    clips.append(_cycle(armature, "crouch_walk", 34, crouch_walk))

    # aim — shouldered, head down to the sights
    action = _new_action(armature, "aim")
    _rest(armature)
    for frame in (1, 40):
        _pose(armature, "Chest", frame, rotation=(4.0, 0.0, -16.0))
        _pose(armature, "Head", frame, rotation=(6.0, 0.0, 12.0))
        _pose(armature, "UpperArm.R", frame, rotation=(-74.0, 0.0, 46.0))
        _pose(armature, "LowerArm.R", frame, rotation=(-88.0, 0.0, -24.0))
        _pose(armature, "UpperArm.L", frame, rotation=(-80.0, 0.0, -54.0))
        _pose(armature, "LowerArm.L", frame, rotation=(-92.0, 0.0, 30.0))
    clips.append((action, 40))

    # fire — sharp recoil, quick recovery
    action = _new_action(armature, "fire")
    _rest(armature)
    recoil = ((1, 0.0), (2, 1.0), (4, 0.55), (7, 0.2), (10, 0.0))
    for frame, amount in recoil:
        _pose(armature, "Chest", frame, rotation=(4.0 - amount * 7.0, 0.0, -16.0))
        _pose(armature, "Head", frame, rotation=(6.0 - amount * 5.0, 0.0, 12.0))
        _pose(armature, "UpperArm.R", frame, rotation=(-74.0 + amount * 9.0, 0.0, 46.0))
        _pose(armature, "LowerArm.R", frame, rotation=(-88.0 + amount * 12.0, 0.0, -24.0))
        _pose(armature, "UpperArm.L", frame, rotation=(-80.0 + amount * 7.0, 0.0, -54.0))
        _pose(armature, "LowerArm.L", frame, rotation=(-92.0 + amount * 10.0, 0.0, 30.0))
    clips.append((action, 10))

    # reload — drop the weapon, left hand to the pouch and back
    action = _new_action(armature, "reload")
    _rest(armature)
    stages = (
        (1,  (-62.0, 28.0), (-72.0, -18.0), (-64.0, -42.0), (-84.0, 22.0), 0.0),
        (10, (-40.0, 22.0), (-56.0, -14.0), (-20.0, -30.0), (-52.0, 40.0), -8.0),
        (22, (-40.0, 22.0), (-56.0, -14.0), (-96.0, -18.0), (-38.0, 46.0), -10.0),
        (34, (-44.0, 24.0), (-62.0, -16.0), (-30.0, -36.0), (-70.0, 34.0), -6.0),
        (48, (-62.0, 28.0), (-72.0, -18.0), (-64.0, -42.0), (-84.0, 22.0), 0.0),
    )
    for frame, right_up, right_low, left_up, left_low, lean in stages:
        _pose(armature, "Chest", frame, rotation=(lean, 0.0, -10.0))
        _pose(armature, "Head", frame, rotation=(-lean * 0.6, 0.0, 6.0))
        _pose(armature, "UpperArm.R", frame, rotation=(right_up[0], 0.0, right_up[1]))
        _pose(armature, "LowerArm.R", frame, rotation=(right_low[0], 0.0, right_low[1]))
        _pose(armature, "UpperArm.L", frame, rotation=(left_up[0], 0.0, left_up[1]))
        _pose(armature, "LowerArm.L", frame, rotation=(left_low[0], 0.0, left_low[1]))
    clips.append((action, 48))

    # hit — flinch back
    action = _new_action(armature, "hit")
    _rest(armature)
    for frame, amount in ((1, 0.0), (3, 1.0), (8, 0.4), (14, 0.0)):
        _pose(armature, "Spine", frame, rotation=(-amount * 16.0, 0.0, amount * 8.0))
        _pose(armature, "Chest", frame, rotation=(-amount * 12.0, 0.0, amount * 10.0))
        _pose(armature, "Head", frame, rotation=(-amount * 18.0, 0.0, amount * 12.0))
        _carry_pose(armature, frame, ready=False)
    clips.append((action, 14))

    # death — collapse backwards onto the ground
    action = _new_action(armature, "death")
    _rest(armature)
    frames = (
        (1,  0.0, 0.0, 0.0),
        (6,  -18.0, 0.0, -0.10),
        (16, -52.0, 14.0, -0.45),
        (28, -84.0, 22.0, -0.80),
        (40, -88.0, 24.0, -0.86),
    )
    for frame, pitch, roll, drop in frames:
        _pose(armature, "Hips", frame, rotation=(pitch, roll, 0.0), location=(0.0, 0.0, drop))
        _pose(armature, "Spine", frame, rotation=(pitch * 0.3, -roll * 0.5, 0.0))
        _pose(armature, "Chest", frame, rotation=(pitch * 0.2, -roll * 0.4, 0.0))
        _pose(armature, "Head", frame, rotation=(pitch * 0.25, roll, 0.0))
        for side, sign in (("L", 1.0), ("R", -1.0)):
            _pose(armature, f"UpperArm.{side}", frame,
                  rotation=(pitch * 0.5, 0.0, sign * (10.0 - pitch * 0.4)))
            _pose(armature, f"LowerArm.{side}", frame, rotation=(pitch * 0.3, 0.0, 0.0))
            _pose(armature, f"UpperLeg.{side}", frame, rotation=(-pitch * 0.55, 0.0, 0.0))
            _pose(armature, f"LowerLeg.{side}", frame, rotation=(pitch * 0.35, 0.0, 0.0))
    clips.append((action, 40))

    # jump — crouch, extend, tuck, land
    action = _new_action(armature, "jump")
    _rest(armature)
    steps = (
        (1,  0.0,   0.0,  0.0),
        (5,  40.0, -55.0, -0.16),
        (10, -12.0, 20.0, 0.10),
        (18, 22.0, -36.0, -0.06),
        (24, 0.0,   0.0,  0.0),
    )
    for frame, thigh, shin, drop in steps:
        _pose(armature, "Hips", frame, rotation=(thigh * 0.2, 0.0, 0.0), location=(0.0, 0.0, drop))
        _pose(armature, "Spine", frame, rotation=(thigh * 0.15, 0.0, 0.0))
        for side, sign in (("L", 1.0), ("R", -1.0)):
            _pose(armature, f"UpperLeg.{side}", frame, rotation=(thigh, 0.0, 0.0))
            _pose(armature, f"LowerLeg.{side}", frame, rotation=(shin, 0.0, 0.0))
            _pose(armature, f"UpperArm.{side}", frame, rotation=(-thigh * 0.8, 0.0, sign * 16.0))
        _carry_pose(armature, frame, ready=False)
    clips.append((action, 24))

    for clip_action, length in clips:
        for curve in clip_action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"
                point.easing = "AUTO"
    return clips


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

# Must match materials.UNIFORM_BANDS. Each range is inset slightly so
# bilinear filtering never samples across a band boundary.
ATLAS_BANDS = {
    "cloth": (0.02, 0.55),
    "skin": (0.605, 0.675),
    "gear": (0.725, 0.98),
}


def build_soldier(material_name):
    cloth_parts, skin_parts, gear_parts = build_body()

    groups = []
    for name, parts, projection in (("cloth", cloth_parts, 0.9),
                                    ("skin", skin_parts, 0.5),
                                    ("gear", gear_parts, 0.55)):
        merged = pf.join_objects(parts, "soldier_%s" % name)
        pf.select_only(merged)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        pf.box_project_uv(merged, scale=projection)
        lo, hi = ATLAS_BANDS[name]
        pf.atlas_uv(merged, lo, hi)
        groups.append(merged)

    body = pf.join_objects(groups, "soldier")
    pf.shade_smooth(body, angle_deg=34.0)
    pf.apply_modifiers(body)
    pf.triangulate(body)
    pf.set_material(body, material_name)
    return body


def main():
    pf.reset_scene()
    pf.report("Soldier — mesh, rig, animation")

    factions = {"ranger": "uniform_ranger", "legion": "uniform_legion"}
    summary = []

    for faction, material in factions.items():
        pf.reset_scene()
        armature = build_armature(f"{faction}_rig")
        body = build_soldier(material)
        skin_mesh(body, armature)
        clips = build_animations(armature)

        bone_count = len(armature.data.bones)
        print(f"  {faction}: {pf.tri_count(body)} tris, {bone_count} bones, "
              f"{len(clips)} clips")
        for action, length in clips:
            print(f"      {action.name:<14} {length:3d} frames "
                  f"({length / FPS:.2f}s, {len(action.fcurves)} curves)")

        path = os.path.join(pf.MODEL_DIR, f"soldier_{faction}.glb")
        info = pf.export_glb([armature, body], path, with_animation=True)
        summary.append((faction, info))

    return summary


if __name__ == "__main__":
    main()

"""Shared Blender helpers for the Polyfield 2 asset pipeline.

Run everything through `blender -b --python <script>`. Nothing here touches
the UI, and every generator is deterministic for a given seed so a rebuild
reproduces the same assets byte for byte.
"""

import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
# Generators write straight into the Godot project so there is no copy step
# and no chance of the engine importing a stale duplicate of an asset.
ASSET_DIR = os.path.join(ROOT, "game", "assets")
TEXTURE_DIR = os.path.join(ASSET_DIR, "textures")
MODEL_DIR = os.path.join(ASSET_DIR, "models")
MAP_DIR = os.path.join(ASSET_DIR, "map")


# ---------------------------------------------------------------------------
# Scene management
# ---------------------------------------------------------------------------

def reset_scene():
    """Wipe the file back to an empty scene, including orphaned datablocks."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                       bpy.data.armatures, bpy.data.actions, bpy.data.node_groups):
        for item in list(collection):
            collection.remove(item)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def new_object(name, mesh):
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def mesh_from_arrays(name, verts, faces, uvs=None, normals_split=False):
    """Build a mesh from vertex/face arrays.

    `uvs` is a per-loop array shaped (total_loops, 2) matching the face list
    flattened in order.
    """
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.update()

    if uvs is not None:
        layer = mesh.uv_layers.new(name="UVMap")
        flat = np.asarray(uvs, dtype=np.float32).reshape(-1)
        layer.data.foreach_set("uv", flat)

    mesh.validate(verbose=False)
    mesh.update()
    return mesh


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_modifiers(obj):
    select_only(obj)
    for modifier in list(obj.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        except RuntimeError as error:
            print(f"  ! could not apply {modifier.name} on {obj.name}: {error}")


def join_objects(objects, name):
    """Join a list of objects into the first one and rename it."""
    objects = [o for o in objects if o is not None]
    if not objects:
        return None
    if len(objects) == 1:
        objects[0].name = name
        return objects[0]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    objects[0].name = name
    return objects[0]


def shade_flat(obj):
    select_only(obj)
    bpy.ops.object.shade_flat()


def shade_smooth(obj, angle_deg=35.0):
    """Smooth shading limited by an edge-split angle.

    Godot honours the split normals baked into the glTF, so doing this here
    means hard edges stay hard on the phone without a runtime shader trick.
    """
    select_only(obj)
    bpy.ops.object.shade_smooth()
    modifier = obj.modifiers.new("EdgeSplit", "EDGE_SPLIT")
    modifier.split_angle = math.radians(angle_deg)
    modifier.use_edge_angle = True
    modifier.use_edge_sharp = True


def triangulate(obj):
    modifier = obj.modifiers.new("Triangulate", "TRIANGULATE")
    modifier.quad_method = "SHORTEST_DIAGONAL"
    modifier.min_vertices = 4
    apply_modifiers(obj)


def tri_count(obj):
    mesh = obj.data
    total = 0
    for polygon in mesh.polygons:
        total += max(0, len(polygon.vertices) - 2)
    return total


# ---------------------------------------------------------------------------
# UV projection
# ---------------------------------------------------------------------------

def box_project_uv(obj, scale=2.0):
    """World-scale box (triplanar-style) UVs.

    Each face is projected along its dominant axis at a fixed metres-per-tile
    scale, so a 4 m rock and a 40 m cliff show the same grain size. This is
    what lets one tiling texture serve wildly different object sizes.
    """
    mesh = obj.data
    layer = mesh.uv_layers.get("UVMap") or mesh.uv_layers.new(name="UVMap")

    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(-1, 3)

    uvs = []
    for polygon in mesh.polygons:
        nx, ny, nz = polygon.normal
        ax, ay, az = abs(nx), abs(ny), abs(nz)
        for loop_index in polygon.loop_indices:
            x, y, z = coords[mesh.loops[loop_index].vertex_index]
            if az >= ax and az >= ay:
                u, v = x, y
            elif ax >= ay:
                u, v = y, z
            else:
                u, v = x, z
            uvs.append((u / scale, v / scale))

    flat = np.asarray(uvs, dtype=np.float32).reshape(-1)
    layer.data.foreach_set("uv", flat)
    mesh.update()


def planar_uv(obj, axis="Z", scale=2.0):
    """Project every face along one world axis — used for terrain."""
    mesh = obj.data
    layer = mesh.uv_layers.get("UVMap") or mesh.uv_layers.new(name="UVMap")
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(-1, 3)
    pick = {"X": (1, 2), "Y": (0, 2), "Z": (0, 1)}[axis]

    uvs = []
    for loop in mesh.loops:
        point = coords[loop.vertex_index]
        uvs.append((point[pick[0]] / scale, point[pick[1]] / scale))
    layer.data.foreach_set("uv", np.asarray(uvs, dtype=np.float32).reshape(-1))
    mesh.update()


def atlas_uv(obj, u_lo, u_hi, v_lo=0.0, v_hi=1.0, axis_scale=1.0):
    """Remap an object's existing UVs into a horizontal band of an atlas.

    Character and weapon textures are banded atlases (see materials.py), so
    each part gets squeezed into the band that carries its material.
    """
    mesh = obj.data
    layer = mesh.uv_layers.get("UVMap")
    if layer is None:
        box_project_uv(obj, axis_scale)
        layer = mesh.uv_layers["UVMap"]

    data = np.empty(len(layer.data) * 2, dtype=np.float32)
    layer.data.foreach_get("uv", data)
    data = data.reshape(-1, 2)

    for column, (lo, hi) in enumerate(((u_lo, u_hi), (v_lo, v_hi))):
        channel = data[:, column]
        span = channel.max() - channel.min()
        if span < 1e-6:
            channel[:] = (lo + hi) * 0.5
        else:
            channel[:] = lo + (channel - channel.min()) / span * (hi - lo)
        data[:, column] = channel

    layer.data.foreach_set("uv", data.reshape(-1))
    mesh.update()


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

_GLTF_GROUP_NAME = "glTF Material Output"


def _gltf_output_group():
    """The node group the glTF exporter reads occlusion from.

    Blender's Principled BSDF has no occlusion socket, so the exporter looks
    for a group with this exact name and takes its 'Occlusion' input. Without
    it the AO channel of our ORM pack would never reach the GLB.
    """
    group = bpy.data.node_groups.get(_GLTF_GROUP_NAME)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(_GLTF_GROUP_NAME, "ShaderNodeTree")
    group.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    group.nodes.new("NodeGroupInput")
    return group


def _image(path, non_color):
    name = os.path.basename(path)
    image = bpy.data.images.get(name)
    if image is None:
        image = bpy.data.images.load(path, check_existing=True)
        image.name = name
    image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return image


def make_material(name, texture_dir=None, uv_scale=1.0):
    """Build a glTF-clean PBR material from the generated map set.

    Wires albedo -> Base Color, ORM.G -> Roughness, ORM.B -> Metallic,
    normal -> Normal Map, ORM.R -> glTF occlusion. That is exactly the
    layout glTF's metallicRoughness/occlusion textures expect, so the
    exporter emits one shared image instead of three.
    """
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing

    texture_dir = texture_dir or TEXTURE_DIR
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (600, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (280, 0)
    tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    coords = tree.nodes.new("ShaderNodeTexCoord")
    coords.location = (-900, 0)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-720, 0)
    mapping.inputs["Scale"].default_value = (uv_scale, uv_scale, 1.0)
    tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])

    def texture(suffix, non_color, y, required=True):
        path = os.path.join(texture_dir, f"{name}_{suffix}.png")
        if not os.path.exists(path):
            if required:
                raise FileNotFoundError(f"missing texture map: {path}")
            # Optional maps are genuinely optional: alpha-cut foliage cards
            # carry no normal map, and demanding one would block the material.
            return None
        node = tree.nodes.new("ShaderNodeTexImage")
        node.location = (-480, y)
        node.image = _image(path, non_color)
        node.interpolation = "Smart"
        tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    albedo = texture("albedo", False, 260)
    tree.links.new(albedo.outputs["Color"], bsdf.inputs["Base Color"])

    orm = texture("orm", True, -40)
    if orm is None:
        raise FileNotFoundError(f"missing ORM map for material '{name}'")
    separate = tree.nodes.new("ShaderNodeSeparateColor")
    separate.location = (-200, -40)
    tree.links.new(orm.outputs["Color"], separate.inputs["Color"])
    tree.links.new(separate.outputs["Green"], bsdf.inputs["Roughness"])
    tree.links.new(separate.outputs["Blue"], bsdf.inputs["Metallic"])

    normal_tex = texture("normal", True, -360, required=False)
    if normal_tex is not None:
        normal_map = tree.nodes.new("ShaderNodeNormalMap")
        normal_map.location = (-200, -360)
        tree.links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
        tree.links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

    # Cutout foliage: the albedo's alpha is the mask, and the material has to
    # be marked clipped or the glTF exporter writes it out fully opaque.
    if albedo.image is not None and albedo.image.depth in (32, 64):
        tree.links.new(albedo.outputs["Alpha"], bsdf.inputs["Alpha"])
        material.blend_method = "CLIP"
        material.alpha_threshold = 0.5
        material.use_backface_culling = False

    gltf_out = tree.nodes.new("ShaderNodeGroup")
    gltf_out.node_tree = _gltf_output_group()
    gltf_out.location = (280, -420)
    tree.links.new(separate.outputs["Red"], gltf_out.inputs["Occlusion"])

    return material


def make_terrain_material(name="terrain_splat", layers=("rock_granite", "grass_highland",
                                                        "ground_rocky"),
                          texture_dir=None, uv_scale=1.0):
    """Three-way splat material driven by the mesh's vertex colours.

    Godot replaces this with its own terrain shader, but the node tree still
    has to reference the colour attribute — the glTF exporter drops COLOR_0
    entirely when nothing in the material consumes it, and that attribute is
    the whole splat mask. Building the real blend here means the Blender
    preview is also honest instead of a placeholder grey.
    """
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing

    texture_dir = texture_dir or TEXTURE_DIR
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (620, 0)
    tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    splat = tree.nodes.new("ShaderNodeVertexColor")
    splat.layer_name = "splat"
    splat.location = (-1100, -300)
    separate = tree.nodes.new("ShaderNodeSeparateColor")
    separate.location = (-920, -300)
    tree.links.new(splat.outputs["Color"], separate.inputs["Color"])

    coords = tree.nodes.new("ShaderNodeTexCoord")
    coords.location = (-1300, 200)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-1120, 200)
    mapping.inputs["Scale"].default_value = (uv_scale, uv_scale, 1.0)
    tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])

    def image_node(layer, suffix, non_color, position):
        path = os.path.join(texture_dir, f"{layer}_{suffix}.png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"missing texture map: {path}")
        node = tree.nodes.new("ShaderNodeTexImage")
        node.location = position
        node.image = _image(path, non_color)
        tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    albedos = [image_node(layer, "albedo", False, (-780, 400 - index * 300))
               for index, layer in enumerate(layers)]
    orms = [image_node(layer, "orm", True, (-780, -500 - index * 300))
            for index, layer in enumerate(layers)]

    # rock over gravel by R, then grass over that by G. Blue is the remainder,
    # so the three weights always resolve even where they do not sum to one.
    def blend(a, b, factor_socket, position):
        node = tree.nodes.new("ShaderNodeMix")
        node.data_type = "RGBA"
        node.location = position
        tree.links.new(factor_socket, node.inputs["Factor"])
        tree.links.new(a, node.inputs[6])   # A (colour)
        tree.links.new(b, node.inputs[7])   # B (colour)
        return node.outputs[2]              # Result (colour)

    albedo_mix = blend(albedos[2].outputs["Color"], albedos[0].outputs["Color"],
                       separate.outputs["Red"], (-380, 300))
    albedo_mix = blend(albedo_mix, albedos[1].outputs["Color"],
                       separate.outputs["Green"], (-160, 300))
    tree.links.new(albedo_mix, bsdf.inputs["Base Color"])

    orm_mix = blend(orms[2].outputs["Color"], orms[0].outputs["Color"],
                    separate.outputs["Red"], (-380, -500))
    orm_mix = blend(orm_mix, orms[1].outputs["Color"],
                    separate.outputs["Green"], (-160, -500))
    orm_split = tree.nodes.new("ShaderNodeSeparateColor")
    orm_split.location = (100, -500)
    tree.links.new(orm_mix, orm_split.inputs["Color"])
    tree.links.new(orm_split.outputs["Green"], bsdf.inputs["Roughness"])
    tree.links.new(orm_split.outputs["Blue"], bsdf.inputs["Metallic"])

    gltf_out = tree.nodes.new("ShaderNodeGroup")
    gltf_out.node_tree = _gltf_output_group()
    gltf_out.location = (620, -560)
    tree.links.new(orm_split.outputs["Red"], gltf_out.inputs["Occlusion"])

    return material


def set_material(obj, material_name, uv_scale=1.0):
    material = make_material(material_name, uv_scale=uv_scale)
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return material


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def bm_to_object(bm, name):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return new_object(name, mesh)


def make_box(name, size=(1, 1, 1), location=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(location), verts=bm.verts)
    return bm_to_object(bm, name)


def make_cylinder(name, radius=0.5, depth=1.0, segments=12, location=(0, 0, 0),
                  cap=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments,
                          radius1=radius, radius2=radius, depth=depth)
    bmesh.ops.translate(bm, vec=Vector(location), verts=bm.verts)
    return bm_to_object(bm, name)


def make_cone(name, radius=0.5, top=0.0, depth=1.0, segments=10, location=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=top, depth=depth)
    bmesh.ops.translate(bm, vec=Vector(location), verts=bm.verts)
    return bm_to_object(bm, name)


def make_icosphere(name, radius=0.5, subdivisions=2, location=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius)
    bmesh.ops.translate(bm, vec=Vector(location), verts=bm.verts)
    return bm_to_object(bm, name)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_glb(objects, path, apply_mods=True, with_animation=False,
               vertex_colour=None, embed_textures=False):
    """Export the given objects to a GLB, Y-up, +Z forward (Godot convention).

    `vertex_colour` names a colour attribute to export unconditionally. The
    exporter's default MATERIAL mode only keeps colours a material actually
    samples through its base-colour path, which silently drops the terrain
    splat mask since that feeds mix factors rather than a colour socket.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]

    colour_mode = "NAME" if vertex_colour else "MATERIAL"

    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=apply_mods,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=True,
        export_materials="EXPORT",
        # Textures stay out of the GLB. Every asset shares the same 13 map
        # sets, so embedding would copy ~3 MB of PNG into each file; Godot
        # binds the real ORMMaterial3D by material name instead.
        export_image_format="AUTO" if embed_textures else "NONE",
        export_vertex_color=colour_mode,
        export_vertex_color_name=vertex_colour or "Color",
        export_all_vertex_colors=False,
        export_animations=with_animation,
        export_skins=with_animation,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
    )
    size_kb = os.path.getsize(path) / 1024.0
    total_tris = sum(tri_count(o) for o in objects if o.type == "MESH")
    print(f"  -> {os.path.relpath(path, ROOT)}  {size_kb:7.1f} KB  {total_tris:6d} tris")
    return {"path": path, "kb": round(size_kb, 1), "tris": total_tris}


def report(title):
    print(f"\n=== {title} ===")


def rng(seed):
    return np.random.default_rng(seed)

extends Node3D
## Builds the Ridgeline level from assets/map/layout.json.
##
## The layout file is written by tools/blender/layout.py — the same module the
## terrain generator carves from. Reading it here rather than re-deriving the
## placement in GDScript is what guarantees a trench module never ends up
## floating above the channel that was cut for it.

const LAYOUT_PATH := "res://assets/map/layout.json"
const TERRAIN_PATH := "res://assets/models/terrain_ridgeline.glb"
const ROCKS_PATH := "res://assets/models/rocks.glb"
const FORTS_PATH := "res://assets/models/fortifications.glb"
const PROPS_PATH := "res://assets/models/props.glb"
const VEGETATION_PATH := "res://assets/models/vegetation.glb"

signal level_ready(stats: Dictionary)

var layout: Dictionary = {}
var stats: Dictionary = {}

var _static_body: StaticBody3D


## Called by Main, not from _ready(). Children are ready before their parent,
## so a level that built itself in _ready() would emit level_ready before Main
## had connected to it and the player would never be placed.
func build() -> void:
	var started := Time.get_ticks_msec()
	layout = _read_layout()
	if layout.is_empty():
		push_error("[Level] layout.json missing or unreadable")
		return

	_static_body = StaticBody3D.new()
	_static_body.name = "WorldCollision"
	add_child(_static_body)

	_build_terrain()
	_build_rocks()
	_build_trenches()
	_build_sandbags()
	_build_props()
	_build_vegetation()
	_build_zones()

	stats["build_ms"] = Time.get_ticks_msec() - started
	print("[Level] %s" % stats)
	level_ready.emit(stats)


func _read_layout() -> Dictionary:
	if not FileAccess.file_exists(LAYOUT_PATH):
		return {}
	var file := FileAccess.open(LAYOUT_PATH, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	return parsed if parsed is Dictionary else {}


## Pull the MeshInstance3D children out of an imported GLB, keyed by node name.
func _meshes_from(path: String) -> Dictionary:
	var packed := ResourceLoader.load(path) as PackedScene
	if packed == null:
		push_error("[Level] cannot load %s" % path)
		return {}
	var root := packed.instantiate()
	var found: Dictionary = {}
	var queue: Array[Node] = [root]
	while not queue.is_empty():
		var node: Node = queue.pop_back()
		if node is MeshInstance3D and node.mesh != null:
			found[node.name] = node.mesh
		queue.append_array(node.get_children())
	root.queue_free()
	return found


func _add_collision(shape: Shape3D, transform: Transform3D) -> void:
	var collider := CollisionShape3D.new()
	collider.shape = shape
	collider.transform = transform
	_static_body.add_child(collider)


func _build_terrain() -> void:
	var meshes := _meshes_from(TERRAIN_PATH)
	if meshes.is_empty():
		return

	var material := MaterialLibrary.terrain_material()
	var container := Node3D.new()
	container.name = "Terrain"
	add_child(container)

	var triangles := 0
	for name: String in meshes:
		var mesh: Mesh = meshes[name]
		var instance := MeshInstance3D.new()
		instance.name = name
		instance.mesh = mesh
		if material != null:
			for surface in range(mesh.get_surface_count()):
				instance.set_surface_override_material(surface, material)
		# Chunked so frustum culling has something to work with, and shadows
		# only cast from nearby chunks.
		instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		instance.lod_bias = 1.4
		container.add_child(instance)

		_add_collision(mesh.create_trimesh_shape(), Transform3D.IDENTITY)
		triangles += _triangles_of(mesh)

	stats["terrain_chunks"] = meshes.size()
	stats["terrain_tris"] = triangles


func _triangles_of(mesh: Mesh) -> int:
	var total := 0
	for surface in range(mesh.get_surface_count()):
		var arrays := mesh.surface_get_arrays(surface)
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		if indices.size() > 0:
			total += indices.size() / 3
		else:
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			total += vertices.size() / 3
	return total


func _multimesh(mesh: Mesh, transforms: Array[Transform3D], node_name: String,
		material: Material) -> MultiMeshInstance3D:
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.mesh = mesh
	multi.instance_count = transforms.size()
	for index in transforms.size():
		multi.set_instance_transform(index, transforms[index])

	var instance := MultiMeshInstance3D.new()
	instance.name = node_name
	instance.multimesh = multi
	if material != null:
		instance.material_override = material
	# One draw call for every rock on the map instead of 190.
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(instance)
	return instance


func _build_rocks() -> void:
	var meshes := _meshes_from(ROCKS_PATH)
	if meshes.is_empty():
		return

	var rocks: Array = layout.get("rocks", [])
	var per_variant: Dictionary = {}
	var shapes: Dictionary = {}

	for entry: Dictionary in rocks:
		var variant: int = int(entry.get("variant", 0))
		var key := "rock_%02d" % variant
		if not meshes.has(key):
			continue
		var transform := _transform_of(entry)
		if not per_variant.has(key):
			per_variant[key] = [] as Array[Transform3D]
		per_variant[key].append(transform)

		if not shapes.has(key):
			shapes[key] = (meshes[key] as Mesh).create_convex_shape()
		_add_collision(shapes[key], transform)

	var placed := 0
	for key: String in per_variant:
		var material := MaterialLibrary.get_material("rock_granite")
		_multimesh(meshes[key], per_variant[key], "Rocks_%s" % key, material)
		placed += per_variant[key].size()
	stats["rocks"] = placed


func _transform_of(entry: Dictionary) -> Transform3D:
	var position := _vector(entry.get("position", [0, 0, 0]))
	var basis := Basis.IDENTITY
	basis = basis.rotated(Vector3.UP, float(entry.get("yaw", 0.0)))
	if entry.has("pitch"):
		basis = basis.rotated(Vector3.RIGHT, float(entry["pitch"]))
	var scale := float(entry.get("scale", 1.0))
	return Transform3D(basis.scaled(Vector3(scale, scale, scale)), position)


func _vector(raw: Variant) -> Vector3:
	var array: Array = raw as Array
	if array == null or array.size() < 3:
		return Vector3.ZERO
	return Vector3(float(array[0]), float(array[1]), float(array[2]))


func _build_trenches() -> void:
	var meshes := _meshes_from(FORTS_PATH)
	if meshes.is_empty():
		return

	var modules: Array = layout.get("trench_modules", [])
	var timber: Array[Transform3D] = []
	var bags: Array[Transform3D] = []
	# One box per bay standing in for the revetment walls. Trimesh collision on
	# 114 trench modules would cost far more than the walls are worth: the
	# player is inside the channel, and the channel is already terrain.
	var wall_shape := BoxShape3D.new()
	wall_shape.size = Vector3(2.4, 0.5, 4.2)

	for entry: Dictionary in modules:
		var position := _vector(entry.get("position", [0, 0, 0]))
		var basis := Basis.IDENTITY.rotated(Vector3.UP, float(entry.get("yaw", 0.0)))
		var transform := Transform3D(basis, position)
		timber.append(transform)
		bags.append(transform)
		_add_collision(wall_shape, Transform3D(basis, position + Vector3.UP * 0.25))

	if meshes.has("trench_straight_timber"):
		_multimesh(meshes["trench_straight_timber"], timber, "TrenchTimber",
			MaterialLibrary.get_material("wood_plank"))
	if meshes.has("trench_straight_bags"):
		_multimesh(meshes["trench_straight_bags"], bags, "TrenchBags",
			MaterialLibrary.get_material("sandbag_burlap"))
	stats["trench_modules"] = modules.size()


func _build_sandbags() -> void:
	var meshes := _meshes_from(FORTS_PATH)
	if meshes.is_empty():
		return

	var grouped: Dictionary = {}
	var shape := BoxShape3D.new()
	shape.size = Vector3(2.6, 0.8, 0.7)

	for entry: Dictionary in layout.get("sandbags", []):
		var kind: String = str(entry.get("kind", "sandbag_wall"))
		if not meshes.has(kind):
			continue
		var position := _vector(entry.get("position", [0, 0, 0]))
		var basis := Basis.IDENTITY.rotated(Vector3.UP, float(entry.get("yaw", 0.0)))
		var transform := Transform3D(basis, position)
		if not grouped.has(kind):
			grouped[kind] = [] as Array[Transform3D]
		grouped[kind].append(transform)
		_add_collision(shape, Transform3D(basis, position + Vector3.UP * 0.4))

	var placed := 0
	for kind: String in grouped:
		_multimesh(meshes[kind], grouped[kind], "Sandbags_%s" % kind,
			MaterialLibrary.get_material("sandbag_burlap"))
		placed += grouped[kind].size()
	stats["sandbags"] = placed


func _build_props() -> void:
	var meshes := _meshes_from(PROPS_PATH)
	if meshes.is_empty():
		return

	var container := Node3D.new()
	container.name = "Props"
	add_child(container)

	var shape := BoxShape3D.new()
	shape.size = Vector3(0.8, 0.7, 0.8)
	var placed := 0

	for entry: Dictionary in layout.get("props", []):
		var kind: String = str(entry.get("kind", ""))
		var position := _vector(entry.get("position", [0, 0, 0]))
		var basis := Basis.IDENTITY.rotated(Vector3.UP, float(entry.get("yaw", 0.0)))

		# The capture mast is two meshes (structure + banner) so the banner can
		# be tinted by the owning team at runtime.
		var parts: Array[String] = []
		if kind == "capture_mast":
			parts = ["capture_mast_metal", "capture_mast_banner"]
		elif meshes.has(kind):
			parts = [kind]
		else:
			continue

		for part: String in parts:
			if not meshes.has(part):
				continue
			var instance := MeshInstance3D.new()
			instance.name = "%s_%d" % [part, placed]
			instance.mesh = meshes[part]
			instance.transform = Transform3D(basis, position)
			MaterialLibrary.apply_to(instance)
			container.add_child(instance)
		if kind != "capture_mast":
			_add_collision(shape, Transform3D(basis, position + Vector3.UP * 0.35))
		placed += 1

	stats["props"] = placed


## Trees, bushes and grass. Density scales with the quality preset, because
## 1270 alpha-cut instances is the difference between 60 and 30 fps on a phone
## and is the first thing that should go when frames are short.
func _build_vegetation() -> void:
	var meshes := _meshes_from(VEGETATION_PATH)
	if meshes.is_empty():
		return

	var density := float(Settings.preset()["vegetation"])
	var species := {
		"tree": ["tree_pine", "tree_oak", "tree_scrub"],
		"bush": ["bush_low", "bush_tall"],
		"grass": ["grass_tuft"],
	}
	var grouped: Dictionary = {}
	var trunk_shape := CylinderShape3D.new()
	trunk_shape.radius = 0.34
	trunk_shape.height = 5.0

	var generator := RandomNumberGenerator.new()
	generator.seed = 20260814

	for entry: Dictionary in layout.get("vegetation", []):
		var kind: String = str(entry.get("kind", ""))
		if not species.has(kind):
			continue
		# Thin by density rather than truncating the list, so what survives is
		# still spread across the whole map.
		if generator.randf() > density:
			continue

		var names: Array = species[kind]
		var variant: int = int(entry.get("variant", 0)) % names.size()
		var position := _vector(entry.get("position", [0, 0, 0]))
		var scale := float(entry.get("scale", 1.0))
		var basis := Basis.IDENTITY.rotated(Vector3.UP, float(entry.get("yaw", 0.0)))
		var transform := Transform3D(basis.scaled(Vector3(scale, scale, scale)), position)

		# A tree is two meshes (bark trunk, cutout foliage) that must be
		# instanced in lockstep or the crown floats away from its trunk.
		var parts: Array[String] = []
		if kind == "tree":
			parts = ["%s_trunk" % names[variant], "%s_leaves" % names[variant]]
			_add_collision(trunk_shape, Transform3D(basis, position + Vector3.UP * 2.5))
		else:
			parts = [names[variant]]

		for part: String in parts:
			if not meshes.has(part):
				continue
			if not grouped.has(part):
				grouped[part] = [] as Array[Transform3D]
			grouped[part].append(transform)

	var placed := 0
	for part: String in grouped:
		var material_name := "leaf" if part.ends_with("_leaves") or part.begins_with("bush") \
			or part.begins_with("grass") else "bark"
		var instance := _multimesh(meshes[part], grouped[part], "Veg_%s" % part,
			MaterialLibrary.get_material(material_name))
		# Foliage casting shadows doubles its cost for very little; the trunks
		# still cast, which is what grounds the tree.
		if material_name == "leaf":
			instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		instance.visibility_range_end = float(Settings.preset()["prop_distance"])
		instance.visibility_range_end_margin = 12.0
		instance.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		placed += grouped[part].size()
	stats["vegetation"] = placed


func _build_zones() -> void:
	var container := Node3D.new()
	container.name = "Zones"
	add_child(container)

	var zone_script := load("res://scripts/capture_zone.gd")
	for entry: Dictionary in layout.get("zones", []):
		var zone := Area3D.new()
		zone.name = "Zone_%s" % str(entry.get("id", "?"))
		zone.set_script(zone_script)
		zone.position = _vector(entry.get("position", [0, 0, 0]))
		zone.monitoring = true

		var shape := CylinderShape3D.new()
		shape.radius = float(entry.get("radius", 10.0))
		shape.height = 12.0
		var collider := CollisionShape3D.new()
		collider.shape = shape
		collider.position = Vector3.UP * 4.0
		zone.add_child(collider)

		container.add_child(zone)
		zone.setup(str(entry.get("id", "?")), str(entry.get("owner", "neutral")),
			float(entry.get("radius", 10.0)))

	stats["zones"] = container.get_child_count()


func spawn_points(team: String) -> Array:
	var spawns: Dictionary = layout.get("spawns", {})
	var raw: Array = spawns.get(team, [])
	var points: Array[Vector3] = []
	for item: Variant in raw:
		points.append(_vector(item))
	return points

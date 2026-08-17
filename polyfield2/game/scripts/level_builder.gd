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
const BUILDINGS_PATH := "res://assets/models/buildings.glb"

signal level_ready(stats: Dictionary)

var layout: Dictionary = {}
var stats: Dictionary = {}

var _static_body: StaticBody3D
var _chunk_root: Node3D
var _budget: Dictionary = {}

## Cell size in metres for each family of instanced geometry, and how far it is
## drawn. Vegetation gets the finest grid because it is alpha-scissor and by far
## the most expensive thing per pixel; rocks and fortifications are opaque and
## fewer, so a coarser grid keeps their draw-call count down.
const CHUNK := {
	"vegetation": 56.0,
	"rocks": 96.0,
	"forts": 64.0,
}


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

	_chunk_root = Node3D.new()
	_chunk_root.name = "Chunks"
	add_child(_chunk_root)

	_build_terrain()
	_build_rocks()
	_build_trenches()
	_build_sandbags()
	_build_props()
	_build_vegetation()
	_build_zones()

	stats["build_ms"] = Time.get_ticks_msec() - started
	print("[Level] %s" % stats)
	_report_budget()
	level_ready.emit(stats)


## Where the triangles actually are, worst case (nothing culled). Printed at
## build so a change that quietly triples a category is visible immediately.
func _report_budget() -> void:
	var rows: Array = []
	var total: int = int(stats.get("terrain_tris", 0))
	for name: String in _budget:
		rows.append([name, _budget[name]])
		total += int(_budget[name]["tris"])
	rows.sort_custom(func(a, b): return int(a[1]["tris"]) > int(b[1]["tris"]))

	print("[Budget] worst-case %d tris (terrain %d)" % [total, stats.get("terrain_tris", 0)])
	for row: Array in rows.slice(0, 8):
		var info: Dictionary = row[1]
		print("[Budget]   %-22s %5d x %5d = %7d" % [row[0], info["instances"],
			info["each"], info["tris"]])


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


## Spatially partition instances into cells, one MultiMesh per (cell, mesh).
##
## This is the single most important thing in the file. A MultiMesh holding
## every rock on the map has an AABB the size of the map, so the renderer can
## never frustum-cull it and `visibility_range_end` measures from the map
## centre — which means every rock, trench module, sandbag and tree was
## submitted every frame no matter where the player stood or which way they
## faced. That was 1.12 million primitives per frame at spawn.
##
## Cut into cells, each MultiMesh has a tight AABB: the ones behind the player
## are culled by the frustum and the distant ones by range. It costs more draw
## calls per visible cell and saves most of the geometry, which is the right
## trade on a phone — a mobile GPU will take a few hundred draw calls far more
## happily than a million triangles.
##
## Cell size is the tuning knob. Too large and culling is coarse; too small and
## the draw-call count grows faster than the geometry falls.
func _chunked(mesh: Mesh, transforms: Array[Transform3D], node_name: String,
		material: Material, cell_metres: float, view_distance: float,
		casts_shadow: bool = true) -> int:
	if transforms.is_empty():
		return 0

	# Budget accounting. Guessing which category dominates the frame is how you
	# spend an afternoon optimising the wrong thing.
	var tris := _triangles_of(mesh) * transforms.size()
	_budget[node_name] = {"instances": transforms.size(), "tris": tris,
		"each": _triangles_of(mesh)}

	var cells: Dictionary = {}
	for transform in transforms:
		var key := Vector2i(floori(transform.origin.x / cell_metres),
			floori(transform.origin.z / cell_metres))
		if not cells.has(key):
			cells[key] = [] as Array[Transform3D]
		cells[key].append(transform)

	for key: Vector2i in cells:
		var group: Array[Transform3D] = cells[key]
		var centre := Vector3((key.x + 0.5) * cell_metres, 0.0, (key.y + 0.5) * cell_metres)

		var multi := MultiMesh.new()
		multi.transform_format = MultiMesh.TRANSFORM_3D
		multi.mesh = mesh
		multi.instance_count = group.size()
		for index in group.size():
			# Stored relative to the cell, so the AABB hugs the cell rather than
			# stretching back to the world origin.
			var local := group[index]
			multi.set_instance_transform(index,
				Transform3D(local.basis, local.origin - centre))

		var instance := MultiMeshInstance3D.new()
		instance.name = "%s_%d_%d" % [node_name, key.x, key.y]
		instance.multimesh = multi
		instance.position = centre
		if material != null:
			instance.material_override = material
		instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if casts_shadow \
			else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if view_distance > 0.0:
			instance.visibility_range_end = view_distance
			instance.visibility_range_end_margin = cell_metres
		# Deliberately no fade: VISIBILITY_RANGE_FADE_SELF needs the material to
		# blend, which pushes opaque geometry into the transparent pass and costs
		# more fill than the culling saves. A hard cut this far out is invisible.
		instance.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
		_chunk_root.add_child(instance)

	return transforms.size()


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
	var material := MaterialLibrary.get_material("rock_granite")
	var distance := float(Settings.preset()["rock_distance"])
	for key: String in per_variant:
		placed += _chunked(meshes[key], per_variant[key], "Rocks_%s" % key, material,
			CHUNK["rocks"], distance)
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

	var distance := float(Settings.preset()["fort_distance"])
	if meshes.has("trench_straight_timber"):
		_chunked(meshes["trench_straight_timber"], timber, "TrenchTimber",
			MaterialLibrary.get_material("wood_plank"), CHUNK["forts"], distance, false)
	if meshes.has("trench_straight_bags"):
		_chunked(meshes["trench_straight_bags"], bags, "TrenchBags",
			MaterialLibrary.get_material("sandbag_burlap"), CHUNK["forts"], distance, false)
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
	var material := MaterialLibrary.get_material("sandbag_burlap")
	var distance := float(Settings.preset()["fort_distance"])
	for kind: String in grouped:
		placed += _chunked(meshes[kind], grouped[kind], "Sandbags_%s" % kind,
			material, CHUNK["forts"], distance, false)
	stats["sandbags"] = placed


func _build_props() -> void:
	var meshes := _meshes_from(PROPS_PATH)
	# Zone structures live in their own file but are placed by the same prop
	# pass, so merge the two lookups.
	meshes.merge(_meshes_from(BUILDINGS_PATH), true)
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

		# Buildings and the capture masts are landmarks — a player navigates by
		# them, so they stay visible across the map. A crate is not a landmark.
		var is_landmark := kind in ["bunker", "watchtower", "ruin", "capture_mast"]

		for part: String in parts:
			if not meshes.has(part):
				continue
			var instance := MeshInstance3D.new()
			instance.name = "%s_%d" % [part, placed]
			instance.mesh = meshes[part]
			instance.transform = Transform3D(basis, position)
			MaterialLibrary.apply_to(instance)
			if not is_landmark:
				instance.visibility_range_end = float(Settings.preset()["prop_distance"]) * 0.6
				instance.visibility_range_end_margin = 8.0
				instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			container.add_child(instance)
		if kind in ["bunker", "watchtower", "ruin"]:
			# Buildings need real collision: the player walks into and behind
			# them, so a box would either block the doorway or let them
			# through the walls.
			var building_mesh: Mesh = meshes.get(kind, null)
			if building_mesh != null:
				_add_collision(building_mesh.create_trimesh_shape(),
					Transform3D(basis, position))
		elif kind != "capture_mast":
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
	# Order matters: the layout records a species as an index, and it indexed
	# against layout.py TREE_SPECIES. Reordering this list here silently plants
	# snags where the map recorded pines.
	var species := {
		"tree": ["tree_pine", "tree_fir", "tree_oak", "tree_birch",
			"tree_scrub", "tree_dead"],
		"bush": ["bush_low", "bush_tall"],
		"grass": ["grass_tuft"],
	}
	var grouped: Dictionary = {}

	# One collider per species rather than one for all of them: a birch is half
	# the girth of an oak, and giving a 3.6 m scrub the oak's 5 m cylinder walls
	# the player off from a shrub they can see straight over. Shapes are shared
	# between every instance of a species, so this is six resources, not 260.
	var trunk_shapes: Dictionary = {}
	for entry: Array in [["tree_pine", 0.30, 6.0], ["tree_fir", 0.26, 5.0],
			["tree_oak", 0.44, 4.4], ["tree_birch", 0.22, 5.4],
			["tree_scrub", 0.36, 2.4], ["tree_dead", 0.32, 4.6]]:
		var shape := CylinderShape3D.new()
		shape.radius = float(entry[1])
		shape.height = float(entry[2])
		trunk_shapes[entry[0]] = shape

	var generator := RandomNumberGenerator.new()
	generator.seed = 20260814

	for entry: Dictionary in layout.get("vegetation", []):
		var kind: String = str(entry.get("kind", ""))
		if not species.has(kind):
			continue
		# Thin by density rather than truncating the list, so what survives is
		# still spread across the whole map.
		# Trees survive thinning: they are the silhouettes that make the ridge
		# read as country rather than as quarry spoil, and there are few enough
		# of them that keeping all of them costs little.
		if kind != "tree" and generator.randf() > density:
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
			# The snag has no crown at all, so its `_leaves` mesh does not exist;
			# the lookup below skips whatever is missing.
			parts = ["%s_trunk" % names[variant], "%s_leaves" % names[variant]]
			var shape: Shape3D = trunk_shapes.get(names[variant], null)
			if shape != null:
				var half: float = (shape as CylinderShape3D).height * 0.5 * scale
				_add_collision(shape, Transform3D(basis.scaled(Vector3(scale, scale, scale)),
					position + Vector3.UP * half))
		else:
			parts = [names[variant]]

		for part: String in parts:
			if not meshes.has(part):
				continue
			if not grouped.has(part):
				grouped[part] = [] as Array[Transform3D]
			grouped[part].append(transform)

	var placed := 0
	var base_distance := float(Settings.preset()["prop_distance"])
	for part: String in grouped:
		var is_foliage := part.ends_with("_leaves") or part.begins_with("bush") \
			or part.begins_with("grass")
		var material_name := "leaf" if is_foliage else "bark"

		# A tree read at 180 m is scenery; a tuft of grass at 180 m is overdraw.
		# Trees get the longer range — capped, not simply doubled. Ground cover
		# is cut much shorter still: it is alpha-scissor, the most expensive
		# thing per pixel on a phone, and nobody sees a blade of grass at 90 m.
		var distance := base_distance
		if part.begins_with("tree"):
			distance = min(base_distance * 1.5, 180.0)
		elif part.begins_with("grass"):
			distance = min(base_distance * 0.45, 48.0)
		elif part.begins_with("bush"):
			distance = min(base_distance * 0.8, 90.0)

		# Foliage casting shadows doubles its cost for very little; the trunks
		# still cast, which is what grounds the tree.
		placed += _chunked(meshes[part], grouped[part], "Veg_%s" % part,
			MaterialLibrary.get_material(material_name), CHUNK["vegetation"],
			distance, not is_foliage)
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

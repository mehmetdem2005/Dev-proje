extends Node3D
## Build demo/mobile_demo.tscn with a real, sculptable Terrain3D in it.
##
##     godot --headless --quit-after 60 tools/build_starter.tscn
##
## The first version of this package created the Terrain3D node at runtime in
## _ready(). That kept the scene file free of a hard dependency on the
## GDExtension, and it was wrong: with no Terrain3D node saved in the scene
## there is nothing to select in the editor, so Terrain3D's sculpting toolbar
## never appears — it is shown only while a Terrain3D node is the selection —
## and with `world_background = NONE` and no regions there is no ground to see
## either. An empty screen and no tools.
##
## So the node goes in the scene, and the scene ships with terrain data: four
## regions of gentle hills, already sculpted, already saved to demo/data.

const MobileConfig := preload("res://mobile/terrain3d_mobile.gd")

const DATA_DIR := "res://demo/data"
const ASSETS := "res://terrain3d_assets.tres"
const SCENE_OUT := "res://demo/mobile_demo.tscn"

const WORLD_M := 512.0
const TIER := MobileConfig.Tier.MEDIUM

## 2x2 regions of 256 vertices. At the MEDIUM tier's 1.5 m spacing that is
## 768 m of ground, comfortably covering the 512 m the clipmap reaches.
const REGION_VERTICES := 256
const GRID := 2


func _ready() -> void:
	if not ClassDB.class_exists("Terrain3D"):
		print("FAIL: Terrain3D extension not loaded. Enable the plugin first.")
		get_tree().quit(1)
		return
	_build()


func _build() -> void:
	var root := Node3D.new()
	root.name = "MobileDemo"

	add_child(root)

	var terrain: Node = ClassDB.instantiate("Terrain3D")
	terrain.name = "Terrain3D"
	terrain.set("data_directory", DATA_DIR)
	if ResourceLoader.exists(ASSETS):
		terrain.set("assets", ResourceLoader.load(ASSETS))
	root.add_child(terrain)

	# Without a WorldEnvironment there is no sky and no ambient light: the
	# background is the flat grey clear colour and the terrain is lit by the
	# sun alone, which makes every slope facing away from it read as dead flat.
	var environment := Environment.new()
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_horizon_color = Color(0.62, 0.65, 0.70)
	sky_material.ground_horizon_color = Color(0.62, 0.65, 0.70)
	sky_material.sky_top_color = Color(0.38, 0.52, 0.75)
	sky_material.ground_bottom_color = Color(0.24, 0.22, 0.20)
	var sky := Sky.new()
	sky.sky_material = sky_material
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	# Ambient from the sky, which is what stops unlit slopes going black.
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.ambient_light_sky_contribution = 1.0
	# Everything below is deliberately off: SSAO, SSIL, SDFGI and glow are all
	# desktop-class post effects that a phone pays for every pixel.
	environment.ssao_enabled = false
	environment.ssil_enabled = false
	environment.sdfgi_enabled = false
	environment.glow_enabled = false
	# Light fog, mostly to soften the edge of a bounded map into the sky rather
	# than ending on a hard silhouette. 0.0015 over a 500 m view washes the
	# whole scene grey; this is barely there until the far edge.
	environment.fog_enabled = true
	environment.fog_light_color = Color(0.66, 0.70, 0.76)
	environment.fog_density = 0.0004
	environment.fog_sky_affect = 0.0
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.tonemap_white = 3.0

	var world_environment := WorldEnvironment.new()
	world_environment.name = "WorldEnvironment"
	world_environment.environment = environment
	root.add_child(world_environment)

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-62.0, -130.0, 0.0)
	sun.shadow_enabled = true
	# Terrain is a huge matte surface. Full specular from a directional light
	# puts a blown highlight across it at grazing angles, which reads as wet
	# plastic and costs fill for the privilege.
	sun.light_specular = 0.15
	root.add_child(sun)

	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.position = Vector3(0.0, 60.0, 120.0)
	camera.rotation_degrees = Vector3(-22.0, 0.0, 0.0)
	camera.far = 2000.0
	camera.current = true
	root.add_child(camera)

	# Do this before configuring so the configurator does not warn, and so the
	# clipmap has something to follow the moment the scene runs.
	terrain.call("set_camera", camera)

	var config := MobileConfig.new()
	config.name = "Terrain3DMobile"
	config.world_size_m = WORLD_M
	config.tier = TIER
	terrain.add_child(config)

	var report: Dictionary = MobileConfig.configure(terrain, WORLD_M, TIER)
	print(MobileConfig.format_report(report))

	# Terrain3D initialises its data on the frame after it enters the tree.
	await get_tree().process_frame
	await get_tree().process_frame

	_sculpt(terrain, float(report["vertex_spacing"]))

	var script := load("res://demo/mobile_demo.gd")
	if script != null:
		root.set_script(script)

	# Every node needs an owner or PackedScene.pack() silently drops it.
	for node: Node in [terrain, sun, camera, config, world_environment]:
		node.owner = root

	remove_child(root)

	var packed := PackedScene.new()
	if packed.pack(root) != OK:
		print("FAIL: could not pack the scene")
		get_tree().quit(1)
		return
	if ResourceSaver.save(packed, SCENE_OUT) != OK:
		print("FAIL: could not save %s" % SCENE_OUT)
		get_tree().quit(1)
		return

	print("wrote %s" % SCENE_OUT)
	get_tree().quit(0)


## Give the starter map some shape. Flat ground is legal but it makes the
## terrain look broken rather than empty, and it gives nothing to judge the
## sculpting tools against.
func _sculpt(terrain: Node, spacing: float) -> void:
	var data: Object = terrain.get("data")
	if data == null:
		print("FAIL: terrain has no data object")
		return

	var size := REGION_VERTICES * GRID
	var image := Image.create(size, size, false, Image.FORMAT_RF)

	var hills := FastNoiseLite.new()
	hills.seed = 20260818
	hills.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	hills.frequency = 0.0035
	hills.fractal_octaves = 4

	var ridges := FastNoiseLite.new()
	ridges.seed = 991
	ridges.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	ridges.fractal_type = FastNoiseLite.FRACTAL_RIDGED
	ridges.frequency = 0.0016
	ridges.fractal_octaves = 3

	for y in size:
		for x in size:
			# Rolling ground with a ridge running through it, and the edges
			# eased down so the bounded map ends on low ground rather than on a
			# cliff of nothing.
			var rolling := hills.get_noise_2d(float(x), float(y)) * 0.5 + 0.5
			var ridge := ridges.get_noise_2d(float(x), float(y)) * 0.5 + 0.5
			var height := rolling * 18.0 + pow(ridge, 2.0) * 34.0

			var u := (float(x) / size) * 2.0 - 1.0
			var v := (float(y) / size) * 2.0 - 1.0
			var edge := clampf(1.0 - maxf(absf(u), absf(v)), 0.0, 1.0)
			height *= smoothstep(0.0, 0.35, edge)

			image.set_pixel(x, y, Color(height, 0.0, 0.0, 1.0))

	# import_images wants one entry per map type even when blank.
	var images: Array[Image] = [image, Image.new(), Image.new()]
	var origin := -0.5 * float(size) * spacing
	data.call("import_images", images, Vector3(origin, 0.0, origin), 0.0, 1.0)

	var regions: int = data.call("get_region_count")
	print("[starter] sculpted %dx%d heightmap -> %d regions" % [size, size, regions])

	var error: int = data.call("save_directory", DATA_DIR)
	if error != OK:
		print("WARN: save_directory returned %d" % error)

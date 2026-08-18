extends Node3D
## Minimal proof that the mobile configuration loads, builds and renders.
##
## Builds a Terrain3D at runtime rather than storing it in the scene, so the
## demo does not carry a .tscn that hard-references the GDExtension — this file
## still opens if the addon is missing, and tells you so instead of erroring.

const DATA_DIR := "res://demo/data"
const ASSETS := "res://terrain3d_assets.tres"
const SIZE_M := 512.0
const TIER := Terrain3DMobile.Tier.MEDIUM

var terrain: Node


func _ready() -> void:
	if not ClassDB.class_exists("Terrain3D"):
		push_error("[Demo] Terrain3D extension not loaded. Enable the plugin in " +
			"Project > Project Settings > Plugins, then restart the editor.")
		return

	terrain = ClassDB.instantiate("Terrain3D")
	terrain.name = "Terrain3D"
	# Terrain3D writes one .res per region here. Without it every region load
	# logs "Resource file not found: res://" and no data can be saved.
	terrain.set("data_directory", DATA_DIR)
	add_child(terrain)

	# The 32-texture pack, ready to paint with.
	if ResourceLoader.exists(ASSETS):
		terrain.set("assets", ResourceLoader.load(ASSETS))
	elif ClassDB.class_exists("Terrain3DAssets"):
		push_warning("[Demo] %s missing — run tools/fetch_textures.py then " % ASSETS +
			"tools/build_assets.gd")
		terrain.set("assets", ClassDB.instantiate("Terrain3DAssets"))

	# Set the camera *before* configuring, so the clipmap has something to
	# follow. Terrain3D drives its clipmap from a camera; without one it
	# disables its own _physics_process and the ground never moves with the
	# player, which still renders and so is easy to miss.
	# By node, not get_camera_3d(): a camera is not yet the viewport's current
	# one this early in _ready, so the lookup returns null and the clipmap
	# silently never gets a target.
	var camera := get_node_or_null("Camera3D")
	if camera != null:
		terrain.call("set_camera", camera)

	var report := Terrain3DMobile.configure(terrain, SIZE_M, TIER)
	print(Terrain3DMobile.format_report(report))

	_report_runtime(report)


## Cross-check the arithmetic against what the extension actually built. The
## instance count is derived from Terrain3DMesher's source; if a future version
## changes the clipmap layout, this is where it shows up.
func _report_runtime(report: Dictionary) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	print("[Demo] renderer: %s" % RenderingServer.get_video_adapter_name())
	print("[Demo] mesh_lods=%s mesh_size=%s vertex_spacing=%s" % [
		terrain.get("mesh_lods"), terrain.get("mesh_size"),
		terrain.get("vertex_spacing")])
	print("[Demo] material world_background=%s (0=None 1=Flat 2=Noise)" %
		terrain.get("material").get("world_background"))
	print("[Demo] predicted MeshInstances=%d" % report.get("mesh_instances", -1))
	var assets: Object = terrain.get("assets")
	if assets != null:
		print("[Demo] textures loaded=%d" % assets.get("texture_list").size())
	print("[Demo] video memory=%.1f MB" % (
		Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0))
	print("[Demo] objects in frame=%d draw calls=%d prims=%d" % [
		Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])

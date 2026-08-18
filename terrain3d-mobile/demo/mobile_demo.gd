extends Node3D
## Minimal proof that the mobile configuration loads, builds and renders.
##
## Builds a Terrain3D at runtime rather than storing it in the scene, so the
## demo does not carry a .tscn that hard-references the GDExtension — this file
## still opens if the addon is missing, and tells you so instead of erroring.

const DATA_DIR := "res://demo/data"
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

	# Terrain3D needs an assets resource before it will build a material.
	if terrain.get("assets") == null and ClassDB.class_exists("Terrain3DAssets"):
		terrain.set("assets", ClassDB.instantiate("Terrain3DAssets"))

	var report := Terrain3DMobile.configure(terrain, SIZE_M, TIER)
	print(Terrain3DMobile.format_report(report))

	# Terrain3D drives its clipmap from a camera; without one it disables its
	# own _physics_process and never snaps the mesh to the viewer.
	var camera := get_viewport().get_camera_3d()
	if camera != null and terrain.has_method("set_camera"):
		terrain.call("set_camera", camera)

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
	print("[Demo] objects in frame=%d draw calls=%d prims=%d" % [
		Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])

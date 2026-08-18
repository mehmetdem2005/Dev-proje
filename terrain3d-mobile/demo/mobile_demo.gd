extends Node3D
## Reports what the starter scene actually built, at runtime.
##
## The Terrain3D node lives in the scene file, not in this script. That matters:
## Terrain3D's sculpting toolbar only appears while a Terrain3D node is selected
## in the editor, so a terrain created in _ready() gives you an empty viewport
## and no tools. Rebuild the scene with:
##
##     godot --headless --quit-after 60 tools/build_starter.tscn

@onready var terrain: Node = get_node_or_null("Terrain3D")


func _ready() -> void:
	if terrain == null:
		push_error("[Demo] no Terrain3D in the scene — rebuild it with " +
			"tools/build_starter.tscn")
		return

	var camera := get_node_or_null("Camera3D")
	if camera != null:
		# Terrain3D snaps its clipmap to a camera. Without one it disables its
		# own _physics_process, so the ground stops following the player while
		# still rendering — which is easy to miss.
		terrain.call("set_camera", camera)

	if OS.get_environment("T3D_STOCK_SHADER") != "":
		var m: Object = terrain.get("material")
		m.call("enable_shader_override", false)
		print("[Demo] stock Terrain3D shader (anisotropic) for comparison")

	_report.call_deferred()


func _report() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

	var data: Object = terrain.get("data")
	var assets: Object = terrain.get("assets")
	var material: Object = terrain.get("material")

	print("[Demo] renderer: %s" % RenderingServer.get_video_adapter_name())
	print("[Demo] mesh_lods=%s mesh_size=%s vertex_spacing=%s" % [
		terrain.get("mesh_lods"), terrain.get("mesh_size"),
		terrain.get("vertex_spacing")])
	print("[Demo] world_background=%s (0=None 1=Flat 2=Noise)" %
		material.get("world_background"))
	var textures: int = 0 if assets == null else assets.call("get_texture_count")
	print("[Demo] regions=%s  texture assets=%d" % [
		"?" if data == null else data.call("get_region_count"), textures])
	if textures == 0:
		# Not a failure. Terrain3D's `free_editor_textures` defaults to true and
		# releases the source Texture2Ds outside the editor once it has built
		# its texture arrays — the arrays are still there, the individual
		# textures are not. Exactly what you want on a phone.
		print("[Demo]   0 is expected in a running game: free_editor_textures " +
			"released the sources after building the arrays.")
	print("[Demo] video memory=%.1f MB" % (
		Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0))
	print("[Demo] objects=%d draw calls=%d prims=%d" % [
		Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])

	# Capture, so "is the ground actually there" is answered by a picture.
	var shot := OS.get_environment("T3D_SHOT")
	if not shot.is_empty():
		await RenderingServer.frame_post_draw
		var image := get_viewport().get_texture().get_image()
		if image != null and image.save_png(shot) == OK:
			print("[Demo] wrote %s" % shot)
		get_tree().quit(0)

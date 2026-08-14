extends Node
## Capture-and-quit harness for automated verification.
##
##     godot --rendering-driver vulkan -- --shot out.png --shot-frame 120 \
##           --shot-cam 0,12,40 --shot-look 0,4,0
##
## Exists so the pipeline can prove what the game actually renders instead of
## only proving that it loaded without errors. Reads its arguments from the
## user args (everything after a bare `--`), so it never collides with Godot's
## own flags.

var _path: String = ""
var _frame_target: int = 120
var _frames: int = 0
var _camera_position: Vector3 = Vector3.INF
var _camera_look: Vector3 = Vector3.ZERO
var _armed: bool = false


func _arg(name: String, fallback: String = "") -> String:
	var args := OS.get_cmdline_user_args()
	var index := args.find(name)
	if index >= 0 and index + 1 < args.size():
		return args[index + 1]
	return fallback


func _vector_arg(name: String, fallback: Vector3) -> Vector3:
	var raw := _arg(name)
	if raw.is_empty():
		return fallback
	var parts := raw.split(",")
	if parts.size() < 3:
		return fallback
	return Vector3(float(parts[0]), float(parts[1]), float(parts[2]))


func _ready() -> void:
	_path = _arg("--shot")
	if _path.is_empty():
		queue_free()
		return
	_frame_target = int(_arg("--shot-frame", "120"))
	_camera_position = _vector_arg("--shot-cam", Vector3.INF)
	_camera_look = _vector_arg("--shot-look", Vector3.ZERO)
	_armed = true
	print("[Shot] arming for frame %d -> %s" % [_frame_target, _path])


func _process(_delta: float) -> void:
	if not _armed:
		return
	_frames += 1

	if _frames < _frame_target:
		return
	_armed = false

	# Camera placement happens on the capture frame, not earlier. Under
	# software rasterisation a frame can be a third of a second, so a subject
	# framed 30 frames ahead of the shot has already walked out of view.
	if _arg("--shot-follow") != "":
		_follow_subject(_arg("--shot-follow"))
	elif _camera_position != Vector3.INF:
		_place_camera()

	# Two frames: the first applies the new camera, the second draws with it.
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw

	var image := get_viewport().get_texture().get_image()
	if image == null:
		push_error("[Shot] no viewport image")
	else:
		var error := image.save_png(_path)
		if error != OK:
			push_error("[Shot] save failed: %d" % error)
		else:
			print("[Shot] wrote %s (%dx%d)" % [_path, image.get_width(), image.get_height()])
	print("[Shot] fps=%d objects=%d prims=%d draw_calls=%d" % [
		Engine.get_frames_per_second(),
		Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
	])
	get_tree().quit()


## Frame a live node from a group instead of a fixed world position. Guessing
## coordinates on a 192 m map reliably puts the camera inside a hill.
func _follow_subject(group: String) -> void:
	var subjects := get_tree().get_nodes_in_group(group)
	if subjects.is_empty():
		push_warning("[Shot] no nodes in group %s" % group)
		return
	var subject: Node3D = subjects[0]
	var origin := subject.global_position
	_camera_position = origin + Vector3(2.6, 1.5, 2.6)
	_camera_look = origin + Vector3.UP * 1.0
	_place_camera()


func _place_camera() -> void:
	var camera := Camera3D.new()
	camera.fov = 70.0
	camera.far = 500.0
	get_tree().root.add_child(camera)
	camera.global_position = _camera_position
	camera.look_at(_camera_look, Vector3.UP)
	camera.make_current()
	print("[Shot] observer camera at %s looking at %s" % [_camera_position, _camera_look])

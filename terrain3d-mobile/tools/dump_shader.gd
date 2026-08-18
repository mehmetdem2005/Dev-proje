extends Node3D
## Dump Terrain3D's generated shader, patched for mobile.
##
##     godot --headless --quit-after 20 tools/dump_shader.tscn
##
## Terrain3D assembles its shader at runtime from the enabled features, so the
## only way to get the exact code for the mobile feature set is to configure a
## real terrain and ask it. Runs as a scene rather than a `-s` script because
## the material only fills the override once it has been initialized with a
## frame running.

const MobileConfig := preload("res://mobile/terrain3d_mobile.gd")
const OUT := "res://mobile/terrain3d_mobile.gdshader"


func _ready() -> void:
	if not ClassDB.class_exists("Terrain3D"):
		push_error("Terrain3D extension not loaded")
		get_tree().quit(1)
		return

	var terrain: Object = ClassDB.instantiate("Terrain3D")
	terrain.set("data_directory", "res://demo/data")
	if ResourceLoader.exists("res://terrain3d_assets.tres"):
		terrain.set("assets", ResourceLoader.load("res://terrain3d_assets.tres"))
	add_child(terrain)

	MobileConfig.configure(terrain, 512.0, MobileConfig.Tier.MEDIUM)

	await get_tree().process_frame
	await get_tree().process_frame

	var material: Object = terrain.get("material")
	material.call("enable_shader_override", true)

	await get_tree().process_frame

	var shader: Shader = material.get("shader_override")
	var code := "" if shader == null else shader.code
	if code.is_empty():
		push_error("generated shader came back empty")
		get_tree().quit(1)
		return

	var before := code.count("_anisotropic")
	# THE patch. Terrain3D has no non-anisotropic sampler path: both of its
	# texture_filtering options are anisotropic, so this cannot be done through
	# the plugin's own settings. Anisotropic sampling of two texture arrays
	# over a surface that fills the screen is bandwidth a phone does not have.
	code = code.replace("_mipmap_anisotropic", "_mipmap")
	var after := code.count("_anisotropic")

	var header := """// Terrain3D mobile shader.
//
// Generated from Terrain3D %s with the mobile feature set (world_background
// NONE, auto_shader off, dual_scaling off), then patched:
//
//   filter_*_mipmap_anisotropic -> filter_*_mipmap    (%d samplers)
//
// Terrain3D offers no non-anisotropic path — both of its texture_filtering
// options are anisotropic — so this is an override, not a setting.
//
// Regenerate with:  godot --headless --quit-after 20 tools/dump_shader.tscn
// Do not hand-edit; edits are lost on regeneration.

""" % ["1.0.2-stable", before]

	var file := FileAccess.open(OUT, FileAccess.WRITE)
	if file == null:
		push_error("cannot write %s" % OUT)
		get_tree().quit(1)
		return
	file.store_string(header + code)
	file.close()

	print("[dump] wrote %s" % OUT)
	print("[dump] %d chars, anisotropic samplers %d -> %d" % [code.length(), before, after])
	get_tree().quit(0)

extends Node
## Persisted settings and quality presets.
##
## The first build ran one fixed configuration and stuttered on anything that
## was not a desktop GPU. Quality here is not a cosmetic slider: each preset
## moves render scale, shadows, view distance, bot count and vegetation
## density together, because those are what actually cost frames on a phone.

const CONFIG_PATH := "user://settings.cfg"

signal quality_changed(level: int)

enum Quality { LOW, MEDIUM, HIGH }

const PRESETS := {
	Quality.LOW: {
		"label": "Düşük",
		"render_scale": 0.72,
		"msaa": Viewport.MSAA_DISABLED,
		"shadows": false,
		"shadow_size": 1024,
		"shadow_distance": 55.0,
		"terrain_far": 40.0,
		"bots": 8,
		"vegetation": 0.45,
		"prop_distance": 90.0,
		"fps_cap": 30,
	},
	Quality.MEDIUM: {
		"label": "Orta",
		"render_scale": 0.85,
		"msaa": Viewport.MSAA_DISABLED,
		"shadows": true,
		"shadow_size": 2048,
		"shadow_distance": 80.0,
		"terrain_far": 60.0,
		"bots": 12,
		"vegetation": 0.75,
		"prop_distance": 140.0,
		"fps_cap": 60,
	},
	Quality.HIGH: {
		"label": "Yüksek",
		"render_scale": 1.0,
		"msaa": Viewport.MSAA_2X,
		"shadows": true,
		"shadow_size": 4096,
		"shadow_distance": 130.0,
		"terrain_far": 95.0,
		"bots": 16,
		"vegetation": 1.0,
		"prop_distance": 220.0,
		"fps_cap": 60,
	},
}

var quality: int = Quality.MEDIUM
var look_sensitivity: float = 1.0
var invert_look: bool = false
var show_fps: bool = false
var master_volume: float = 0.8

var _config := ConfigFile.new()


func _ready() -> void:
	load_settings()


func preset() -> Dictionary:
	return PRESETS[quality]


func load_settings() -> void:
	if _config.load(CONFIG_PATH) != OK:
		# No file yet: guess from the platform rather than dropping a desktop
		# preset onto a phone.
		quality = Quality.MEDIUM if OS.has_feature("mobile") else Quality.HIGH
		apply()
		return
	quality = int(_config.get_value("video", "quality", Quality.MEDIUM))
	look_sensitivity = float(_config.get_value("input", "look_sensitivity", 1.0))
	invert_look = bool(_config.get_value("input", "invert_look", false))
	show_fps = bool(_config.get_value("video", "show_fps", false))
	master_volume = float(_config.get_value("audio", "master_volume", 0.8))
	apply()


func save_settings() -> void:
	_config.set_value("video", "quality", quality)
	_config.set_value("video", "show_fps", show_fps)
	_config.set_value("input", "look_sensitivity", look_sensitivity)
	_config.set_value("input", "invert_look", invert_look)
	_config.set_value("audio", "master_volume", master_volume)
	_config.save(CONFIG_PATH)


func set_quality(level: int) -> void:
	quality = clampi(level, Quality.LOW, Quality.HIGH)
	apply()
	save_settings()
	quality_changed.emit(quality)


func apply() -> void:
	var settings := preset()
	var viewport := get_viewport()
	if viewport != null:
		viewport.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
		viewport.scaling_3d_scale = float(settings["render_scale"])
		viewport.msaa_3d = int(settings["msaa"])
	Engine.max_fps = int(settings["fps_cap"])

	var bus := AudioServer.get_bus_index("Master")
	if bus >= 0:
		AudioServer.set_bus_volume_db(bus, linear_to_db(clampf(master_volume, 0.0001, 1.0)))


## Apply the parts that need scene nodes. Called by the level once it exists.
func apply_to_scene(sun: DirectionalLight3D, terrain_material: ShaderMaterial) -> void:
	var settings := preset()
	if sun != null:
		sun.shadow_enabled = bool(settings["shadows"])
		sun.directional_shadow_max_distance = float(settings["shadow_distance"])
	if terrain_material != null:
		terrain_material.set_shader_parameter("far_distance", float(settings["terrain_far"]))

	RenderingServer.directional_shadow_atlas_set_size(int(settings["shadow_size"]),
		quality != Quality.LOW)

extends Node3D
## Match root: builds the level, lights it, spawns the player and the bots,
## and runs Territory Control scoring.

const TICKET_RATE := 1.0          ## points per held zone per second

const SOLDIER_SCENE := "res://scenes/soldier.tscn"

var scores := {"ranger": 0.0, "legion": 0.0}

var _pause_layer: CanvasLayer

@onready var _level: Node3D = $Level
@onready var _hud: Control = $HUDLayer/HUD
@onready var _player: CharacterBody3D = $Player


func _ready() -> void:
	_level.add_to_group("level")
	_level.level_ready.connect(_on_level_ready)
	_configure_environment()
	_level.build()

	_hud.pause_requested.connect(_toggle_pause)
	_hud.set_show_fps(Settings.show_fps)
	Settings.apply_to_scene($Sun, MaterialLibrary.terrain_material())
	_build_pause_menu()

	var shot := Node.new()
	shot.name = "Screenshot"
	shot.set_script(load("res://scripts/screenshot.gd"))
	add_child(shot)


func _on_level_ready(stats: Dictionary) -> void:
	_place_player()
	_wire_zones()
	_spawn_bots()
	print("[Main] level ready: %s" % stats)
	print("[Main] player at %s, %d bots" % [_player.global_position,
		get_tree().get_nodes_in_group("soldiers").size()])


## Pause overlay. Built here rather than in the HUD because it has to stop the
## tree, and the HUD keeps running so its buttons stay live.
func _build_pause_menu() -> void:
	_pause_layer = CanvasLayer.new()
	_pause_layer.layer = 10
	_pause_layer.visible = false
	add_child(_pause_layer)

	var dim := ColorRect.new()
	dim.color = Color(0.04, 0.05, 0.07, 0.82)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_pause_layer.add_child(dim)

	var centre := CenterContainer.new()
	centre.set_anchors_preset(Control.PRESET_FULL_RECT)
	_pause_layer.add_child(centre)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	centre.add_child(column)

	var heading := Label.new()
	heading.text = "DURAKLATILDI"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 36)
	column.add_child(heading)

	for entry in [["DEVAM ET", "resume"], ["ANA MENÜ", "menu"]]:
		var button := Button.new()
		button.text = str(entry[0])
		button.custom_minimum_size = Vector2(280, 56)
		button.add_theme_font_size_override("font_size", 22)
		if str(entry[1]) == "resume":
			button.pressed.connect(_toggle_pause)
		else:
			button.pressed.connect(func() -> void:
				get_tree().paused = false
				get_tree().change_scene_to_file("res://scenes/menu.tscn"))
		column.add_child(button)

	# The overlay must keep processing while the tree is paused, or its own
	# resume button would be dead.
	_pause_layer.process_mode = Node.PROCESS_MODE_WHEN_PAUSED


func _toggle_pause() -> void:
	var paused := not get_tree().paused
	get_tree().paused = paused
	_pause_layer.visible = paused


func _configure_environment() -> void:
	# Authored for the Mobile renderer: one directional light, no SDFGI, no
	# volumetric fog. Everything atmospheric here is cheap on purpose.
	var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY

	var sky := Sky.new()
	var material := ProceduralSkyMaterial.new()
	material.sky_top_color = Color(0.30, 0.44, 0.62)
	material.sky_horizon_color = Color(0.66, 0.70, 0.72)
	material.ground_bottom_color = Color(0.22, 0.21, 0.19)
	material.ground_horizon_color = Color(0.55, 0.55, 0.52)
	material.sun_angle_max = 12.0
	material.sun_curve = 0.18
	sky.sky_material = material
	environment.sky = sky

	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.ambient_light_sky_contribution = 0.85
	environment.ambient_light_energy = 1.0

	environment.fog_enabled = true
	environment.fog_light_color = Color(0.63, 0.68, 0.72)
	environment.fog_density = 0.0032
	environment.fog_sky_affect = 0.4

	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.tonemap_white = 4.0

	var world := WorldEnvironment.new()
	world.environment = environment
	add_child(world)


func _place_player() -> void:
	var points: Array = _level.spawn_points("ranger")
	if points.is_empty():
		return
	_player.global_position = points[0] + Vector3.UP * 1.2
	_player.weapon_changed.connect(_hud.set_weapon)
	_player.ammo_changed.connect(_hud.set_ammo)
	_player.health_changed.connect(_hud.set_health)
	# The player emitted its starting loadout during its own _ready(), before
	# this connection existed, so ask it to say everything again.
	_player.publish_state()


func _wire_zones() -> void:
	var container := _level.get_node_or_null("Zones")
	if container == null:
		return
	for zone in container.get_children():
		zone.add_to_group("capture_zones")
		zone.owner_changed.connect(_on_zone_owner_changed)
		_hud.set_zone_owner(zone.zone_id, zone.owner_team)


func _on_zone_owner_changed(zone_id: String, new_owner: String) -> void:
	_hud.set_zone_owner(zone_id, new_owner)


func _spawn_bots() -> void:
	var packed := ResourceLoader.load(SOLDIER_SCENE) as PackedScene
	if packed == null:
		push_error("[Main] soldier scene missing")
		return

	var container := Node3D.new()
	container.name = "Soldiers"
	add_child(container)

	for index in int(Settings.preset()["bots"]):
		var team := "legion" if index % 2 == 0 else "ranger"
		var points: Array = _level.spawn_points(team)
		if points.is_empty():
			continue
		var soldier := packed.instantiate()
		soldier.team = team
		container.add_child(soldier)
		soldier.global_position = points[index % points.size()] + Vector3.UP * 0.6


func _process(delta: float) -> void:
	var held := {"ranger": 0, "legion": 0}
	for zone in get_tree().get_nodes_in_group("capture_zones"):
		if held.has(zone.owner_team):
			held[zone.owner_team] += 1

	for team: String in held:
		scores[team] += held[team] * TICKET_RATE * delta
	_hud.set_scores(int(scores["ranger"]), int(scores["legion"]))


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		_toggle_pause()

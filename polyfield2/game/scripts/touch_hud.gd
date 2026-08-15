extends Control
## Touch controls and match HUD, built in code.
##
## Multi-touch is tracked by finger index, not by "the touch": a player holding
## the move stick with the left thumb while dragging to look with the right is
## the normal case, and anything that assumes a single active touch breaks the
## moment they do both at once.

const STICK_RADIUS := 110.0
const STICK_DEADZONE := 0.12

var move_vector: Vector2 = Vector2.ZERO
var fire_held: bool = false
var aim_held: bool = false
var crouch_held: bool = false
var sprint_held: bool = false

var _look_delta: Vector2 = Vector2.ZERO
var _fire_pressed: bool = false
var _jump_pressed: bool = false

var _stick_finger: int = -1
var _look_finger: int = -1
var _stick_origin: Vector2 = Vector2.ZERO
var _stick_position: Vector2 = Vector2.ZERO

var _buttons: Dictionary = {}
var _zone_chips: Dictionary = {}
var _ammo_label: Label
var _weapon_label: Label
var _health_bar: ProgressBar
var _score_label: Label


func _ready() -> void:
	add_to_group("hud")
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build_ui()


# ---------------------------------------------------------------- construction

func _panel(colour: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = colour
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	return style


func _build_ui() -> void:
	# --- top strip: the five capture zones, always in A..E order ------------
	var top := HBoxContainer.new()
	top.set_anchors_preset(Control.PRESET_CENTER_TOP)
	top.position = Vector2(-190, 14)
	top.add_theme_constant_override("separation", 8)
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(top)

	for id in ["A", "B", "C", "D", "E"]:
		var chip := Label.new()
		chip.text = id
		chip.custom_minimum_size = Vector2(58, 34)
		chip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		chip.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		chip.add_theme_stylebox_override("normal", _panel(Color(0.08, 0.09, 0.10, 0.62)))
		chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		top.add_child(chip)
		_zone_chips[id] = chip

	_score_label = Label.new()
	_score_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_score_label.position = Vector2(-90, 54)
	_score_label.custom_minimum_size = Vector2(180, 26)
	_score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_score_label.text = "0  —  0"
	_score_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_score_label)

	# --- bottom left: health --------------------------------------------------
	_health_bar = ProgressBar.new()
	_health_bar.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	_health_bar.position = Vector2(24, -46)
	_health_bar.custom_minimum_size = Vector2(210, 18)
	_health_bar.max_value = 100.0
	_health_bar.value = 100.0
	_health_bar.show_percentage = false
	_health_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_health_bar)

	# --- bottom right: ammo ---------------------------------------------------
	_ammo_label = Label.new()
	_ammo_label.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_ammo_label.position = Vector2(-210, -52)
	_ammo_label.custom_minimum_size = Vector2(180, 30)
	_ammo_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_ammo_label.text = "0 / 0"
	_ammo_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_ammo_label)

	_weapon_label = Label.new()
	_weapon_label.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_weapon_label.position = Vector2(-210, -78)
	_weapon_label.custom_minimum_size = Vector2(180, 24)
	_weapon_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_weapon_label.text = "—"
	_weapon_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_weapon_label)

	# --- action buttons, inside the right thumb arc ---------------------------
	var layout := {
		"fire": Vector2(-150, -170),
		"aim": Vector2(-268, -132),
		"jump": Vector2(-150, -290),
		"crouch": Vector2(-268, -246),
		"reload": Vector2(-64, -256),
		"sprint": Vector2(-360, -190),
	}
	var sizes := {"fire": 108.0, "aim": 82.0}
	for action: String in layout:
		var size: float = sizes.get(action, 72.0)
		var control := Button.new()
		control.name = action
		control.text = action.to_upper()
		control.custom_minimum_size = Vector2(size, size)
		control.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
		control.position = layout[action]
		control.add_theme_stylebox_override("normal", _panel(Color(0.10, 0.12, 0.14, 0.55)))
		control.add_theme_stylebox_override("hover", _panel(Color(0.16, 0.19, 0.22, 0.62)))
		control.add_theme_stylebox_override("pressed", _panel(Color(0.28, 0.42, 0.56, 0.80)))
		control.button_down.connect(_on_button_down.bind(action))
		control.button_up.connect(_on_button_up.bind(action))
		add_child(control)
		_buttons[action] = control

	# --- crosshair ------------------------------------------------------------
	var crosshair := Label.new()
	crosshair.text = "+"
	crosshair.set_anchors_preset(Control.PRESET_CENTER)
	crosshair.position = Vector2(-6, -12)
	crosshair.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(crosshair)


# ---------------------------------------------------------------------- input

func _on_button_down(action: String) -> void:
	match action:
		"fire":
			fire_held = true
			_fire_pressed = true
		"aim":
			aim_held = true
		"crouch":
			crouch_held = not crouch_held
		"sprint":
			sprint_held = true
		"jump":
			_jump_pressed = true
		"reload":
			var player := get_tree().get_first_node_in_group("players")
			if player != null:
				player.call("_begin_reload")


func _on_button_up(action: String) -> void:
	match action:
		"fire":
			fire_held = false
		"aim":
			aim_held = false
		"sprint":
			sprint_held = false


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_handle_touch(event as InputEventScreenTouch)
	elif event is InputEventScreenDrag:
		_handle_drag(event as InputEventScreenDrag)


func _over_button(position: Vector2) -> bool:
	for action: String in _buttons:
		var control: Control = _buttons[action]
		if control.get_global_rect().has_point(position):
			return true
	return false


func _handle_touch(event: InputEventScreenTouch) -> void:
	if event.pressed:
		if _over_button(event.position):
			return
		# Left half drives the stick, right half drives the look — assigned on
		# touch-down and held until that same finger lifts.
		if event.position.x < size.x * 0.5 and _stick_finger == -1:
			_stick_finger = event.index
			_stick_origin = event.position
			_stick_position = event.position
		elif _look_finger == -1:
			_look_finger = event.index
	else:
		if event.index == _stick_finger:
			_stick_finger = -1
			move_vector = Vector2.ZERO
		elif event.index == _look_finger:
			_look_finger = -1


func _handle_drag(event: InputEventScreenDrag) -> void:
	if event.index == _stick_finger:
		_stick_position = event.position
		var offset := (_stick_position - _stick_origin) / STICK_RADIUS
		if offset.length() < STICK_DEADZONE:
			move_vector = Vector2.ZERO
		else:
			move_vector = offset.limit_length(1.0)
	elif event.index == _look_finger:
		_look_delta += event.relative


# --------------------------------------------------------------------- output

func consume_look() -> Vector2:
	var value := _look_delta
	_look_delta = Vector2.ZERO
	return value


func consume_fire() -> bool:
	var value := _fire_pressed
	_fire_pressed = false
	return value


func consume_jump() -> bool:
	var value := _jump_pressed
	_jump_pressed = false
	return value


# ---------------------------------------------------------------------- state

func set_zone_owner(zone_id: String, owner_team: String) -> void:
	var chip: Label = _zone_chips.get(zone_id, null)
	if chip == null:
		return
	var colour := Color(0.08, 0.09, 0.10, 0.62)
	match owner_team:
		"ranger":
			colour = Color(0.247, 0.663, 0.961, 0.78)   # #3FA9F5, reserved
		"legion":
			colour = Color(0.961, 0.325, 0.247, 0.78)   # #F5533F, reserved
	chip.add_theme_stylebox_override("normal", _panel(colour))


func set_scores(ranger: int, legion: int) -> void:
	_score_label.text = "%d  —  %d" % [ranger, legion]


func set_ammo(loaded: int, reserve: int) -> void:
	_ammo_label.text = "%d / %d" % [loaded, reserve]


func set_weapon(label: String, loaded: int, reserve: int) -> void:
	_weapon_label.text = label
	set_ammo(loaded, reserve)


func set_health(value: float) -> void:
	_health_bar.value = value


func _draw() -> void:
	# The stick only draws while it is being held, so it never sits on screen
	# as furniture during a firefight.
	if _stick_finger == -1:
		return
	draw_circle(_stick_origin, STICK_RADIUS, Color(1, 1, 1, 0.10))
	draw_arc(_stick_origin, STICK_RADIUS, 0.0, TAU, 48, Color(1, 1, 1, 0.35), 2.0)
	var knob := _stick_origin + move_vector * STICK_RADIUS
	draw_circle(knob, 34.0, Color(1, 1, 1, 0.28))


func _process(_delta: float) -> void:
	if _stick_finger != -1:
		queue_redraw()

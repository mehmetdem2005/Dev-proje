extends Control
## Touch controls and match HUD.
##
## Rewritten after the first build. Three things were wrong with it:
##
##   * the stick was drawn wherever the finger landed and was never repainted
##     on release, so the old one stayed on screen and the next touch drew a
##     second — it looked like the joystick was duplicating,
##   * the action buttons were stock Buttons with the action name as text,
##     which reads as a debug overlay rather than a game,
##   * aiming changed FOV slightly and nothing else, so there was no scope.
##
## The stick now has a fixed home, every button is an icon, and ADS drives a
## real scope overlay.

const STICK_RADIUS := 96.0
const STICK_DEADZONE := 0.14
const STICK_HOME := Vector2(200.0, -190.0)     # from bottom-left

signal pause_requested
signal weapon_cycle_requested

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
var _stick_home: Vector2 = Vector2.ZERO
var _stick_origin: Vector2 = Vector2.ZERO
var _knob: Vector2 = Vector2.ZERO

var _buttons: Array[HudButton] = []
var _zone_chips: Dictionary = {}
var _ammo_label: Label
var _weapon_label: Label
var _health_bar: ProgressBar
var _score_label: Label
var _fps_label: Label
var _scope: Control
var _hit_marker_time: float = 0.0

var _weapon_scoped: bool = false


func _ready() -> void:
	add_to_group("hud")
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build_ui()
	resized.connect(_relayout)
	_relayout()


# --------------------------------------------------------------- construction

func _panel(colour: Color, radius: int = 10) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = colour
	style.corner_radius_top_left = radius
	style.corner_radius_top_right = radius
	style.corner_radius_bottom_left = radius
	style.corner_radius_bottom_right = radius
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 5
	style.content_margin_bottom = 5
	return style


func _make_label(text: String, alignment: int, font_size: int = 18) -> Label:
	var label := Label.new()
	label.text = text
	label.horizontal_alignment = alignment
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.7))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	add_child(label)
	return label


func _add_button(icon: StringName, radius: float, toggle: bool = false) -> HudButton:
	var button := HudButton.new()
	button.icon = icon
	button.radius = radius
	button.toggle_mode = toggle
	add_child(button)
	_buttons.append(button)
	return button


func _build_ui() -> void:
	# --- capture zones, always A..E ------------------------------------------
	var strip := HBoxContainer.new()
	strip.name = "ZoneStrip"
	strip.add_theme_constant_override("separation", 6)
	strip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(strip)
	for id in ["A", "B", "C", "D", "E"]:
		var chip := Label.new()
		chip.text = id
		chip.custom_minimum_size = Vector2(52, 30)
		chip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		chip.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		chip.add_theme_stylebox_override("normal", _panel(Color(0.06, 0.07, 0.08, 0.55), 6))
		chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		strip.add_child(chip)
		_zone_chips[id] = chip

	_score_label = _make_label("0  —  0", HORIZONTAL_ALIGNMENT_CENTER, 20)
	_health_bar = ProgressBar.new()
	_health_bar.max_value = 100.0
	_health_bar.value = 100.0
	_health_bar.show_percentage = false
	_health_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_health_bar.add_theme_stylebox_override("background", _panel(Color(0.05, 0.05, 0.06, 0.6), 4))
	_health_bar.add_theme_stylebox_override("fill", _panel(Color(0.80, 0.32, 0.28, 0.92), 4))
	add_child(_health_bar)

	_ammo_label = _make_label("0 / 0", HORIZONTAL_ALIGNMENT_RIGHT, 30)
	_weapon_label = _make_label("—", HORIZONTAL_ALIGNMENT_RIGHT, 16)
	_fps_label = _make_label("", HORIZONTAL_ALIGNMENT_LEFT, 14)
	_fps_label.visible = false

	# --- action buttons -------------------------------------------------------
	_add_button(&"fire", 62.0).pressed_down.connect(func() -> void:
		fire_held = true
		_fire_pressed = true)
	_buttons[-1].released.connect(func() -> void: fire_held = false)

	_add_button(&"aim", 46.0, true).pressed_down.connect(func() -> void:
		aim_held = _buttons[1].toggled
		_update_scope())
	_buttons[-1].released.connect(func() -> void: pass)

	_add_button(&"crouch", 40.0, true).pressed_down.connect(func() -> void:
		crouch_held = _buttons[2].toggled)

	_add_button(&"jump", 40.0).pressed_down.connect(func() -> void: _jump_pressed = true)

	_add_button(&"reload", 40.0).pressed_down.connect(func() -> void:
		var player := get_tree().get_first_node_in_group("players")
		if player != null:
			player.call("begin_reload"))

	_add_button(&"weapon", 36.0).pressed_down.connect(func() -> void:
		weapon_cycle_requested.emit())

	_add_button(&"sprint", 38.0, true).pressed_down.connect(func() -> void:
		sprint_held = _buttons[6].toggled)

	_add_button(&"pause", 26.0).pressed_down.connect(func() -> void:
		pause_requested.emit())

	# --- scope overlay --------------------------------------------------------
	_scope = Control.new()
	_scope.name = "Scope"
	_scope.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scope.set_anchors_preset(Control.PRESET_FULL_RECT)
	_scope.visible = false
	_scope.draw.connect(_draw_scope)
	add_child(_scope)


func _relayout() -> void:
	var view := size
	_stick_home = Vector2(STICK_HOME.x, view.y + STICK_HOME.y)
	if _stick_finger == -1:
		_stick_origin = _stick_home
		_knob = _stick_home

	var strip: Control = get_node_or_null("ZoneStrip")
	if strip != null:
		strip.position = Vector2(view.x * 0.5 - 145.0, 12.0)
	_score_label.position = Vector2(view.x * 0.5 - 90.0, 48.0)
	_score_label.size = Vector2(180, 26)

	_health_bar.position = Vector2(26.0, view.y - 44.0)
	_health_bar.size = Vector2(200, 14)

	_ammo_label.position = Vector2(view.x - 214.0, view.y - 62.0)
	_ammo_label.size = Vector2(190, 36)
	_weapon_label.position = Vector2(view.x - 214.0, view.y - 84.0)
	_weapon_label.size = Vector2(190, 20)
	_fps_label.position = Vector2(14.0, 10.0)
	_fps_label.size = Vector2(160, 20)

	# Thumb arc: fire lowest and largest, the rest fanned above and left of it.
	var anchor := Vector2(view.x - 130.0, view.y - 130.0)
	var places := [
		anchor,                                    # fire
		anchor + Vector2(-128.0, -18.0),           # aim
		anchor + Vector2(-38.0, -136.0),           # crouch
		anchor + Vector2(-160.0, -122.0),          # jump
		anchor + Vector2(46.0, -168.0),            # reload
		anchor + Vector2(-244.0, -60.0),           # weapon
		anchor + Vector2(-222.0, -178.0),          # sprint
		Vector2(view.x - 52.0, 34.0),              # pause
	]
	for index in mini(_buttons.size(), places.size()):
		var button := _buttons[index]
		button.position = places[index] - button.size * 0.5

	queue_redraw()


# --------------------------------------------------------------------- input

func _button_at(point: Vector2) -> HudButton:
	for button in _buttons:
		if button.contains(point):
			return button
	return null


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_handle_touch(event as InputEventScreenTouch)
	elif event is InputEventScreenDrag:
		_handle_drag(event as InputEventScreenDrag)


func _handle_touch(event: InputEventScreenTouch) -> void:
	if event.pressed:
		var button := _button_at(event.position)
		if button != null:
			button.press(event.index)
			return
		# Left half drives the stick, right half the look. The stick snaps to
		# wherever the thumb lands within its zone, but returns home on release
		# so it is always in the same place when idle.
		if event.position.x < size.x * 0.45 and _stick_finger == -1:
			_stick_finger = event.index
			_stick_origin = event.position
			_knob = event.position
		elif _look_finger == -1:
			_look_finger = event.index
	else:
		for button in _buttons:
			if button.owns(event.index):
				button.release(event.index)
				return
		if event.index == _stick_finger:
			_stick_finger = -1
			move_vector = Vector2.ZERO
			_stick_origin = _stick_home
			_knob = _stick_home
		elif event.index == _look_finger:
			_look_finger = -1
	# Always repaint on any touch change. Not doing this is what left a stale
	# stick painted on screen after release.
	queue_redraw()


func _handle_drag(event: InputEventScreenDrag) -> void:
	if event.index == _stick_finger:
		var offset := (event.position - _stick_origin) / STICK_RADIUS
		move_vector = Vector2.ZERO if offset.length() < STICK_DEADZONE else offset.limit_length(1.0)
		_knob = _stick_origin + move_vector * STICK_RADIUS
		queue_redraw()
	elif event.index == _look_finger:
		_look_delta += event.relative


# -------------------------------------------------------------------- output

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


# --------------------------------------------------------------------- state

func set_zone_owner(zone_id: String, owner_team: String) -> void:
	var chip: Label = _zone_chips.get(zone_id, null)
	if chip == null:
		return
	var colour := Color(0.06, 0.07, 0.08, 0.55)
	match owner_team:
		"ranger":
			colour = Color(0.247, 0.663, 0.961, 0.80)
		"legion":
			colour = Color(0.961, 0.325, 0.247, 0.80)
	chip.add_theme_stylebox_override("normal", _panel(colour, 6))


func set_scores(ranger: int, legion: int) -> void:
	_score_label.text = "%d  —  %d" % [ranger, legion]


func set_ammo(loaded: int, reserve: int) -> void:
	_ammo_label.text = "%d / %d" % [loaded, reserve]


func set_weapon(label: String, loaded: int, reserve: int) -> void:
	_weapon_label.text = label.to_upper()
	set_ammo(loaded, reserve)
	# A launcher has no scope; the button should not pretend otherwise.
	_update_scope()


func set_health(value: float) -> void:
	_health_bar.value = value


func flash_hit() -> void:
	_hit_marker_time = 0.25
	queue_redraw()


func aiming() -> bool:
	return aim_held


## The player owns whether the equipped weapon actually has a sight; the HUD
## must not guess, or an SMG gets a 6x scope overlay.
func set_weapon_scoped(scoped: bool) -> void:
	_weapon_scoped = scoped
	_update_scope()


func _update_scope() -> void:
	_scope.visible = aim_held and _weapon_scoped
	_scope.queue_redraw()


func _process(delta: float) -> void:
	if _hit_marker_time > 0.0:
		_hit_marker_time -= delta
		if _hit_marker_time <= 0.0:
			queue_redraw()

	if _fps_label.visible:
		_fps_label.text = "%d FPS" % Engine.get_frames_per_second()


func set_show_fps(enabled: bool) -> void:
	_fps_label.visible = enabled


# --------------------------------------------------------------------- paint

func _draw_scope() -> void:
	# Vignette the corners so the sight picture is the middle of the screen,
	# then draw the reticle. Cheap: four rects and a handful of lines, no
	# fullscreen shader.
	var view := _scope.size
	var centre := view * 0.5
	var radius: float = minf(view.x, view.y) * 0.42
	var dark := Color(0, 0, 0, 0.92)

	var left := centre.x - radius
	var right := centre.x + radius
	_scope.draw_rect(Rect2(0, 0, left, view.y), dark)
	_scope.draw_rect(Rect2(right, 0, view.x - right, view.y), dark)
	_scope.draw_rect(Rect2(left, 0, radius * 2.0, centre.y - radius), dark)
	_scope.draw_rect(Rect2(left, centre.y + radius, radius * 2.0, view.y - centre.y - radius), dark)

	# Rounded corners of the sight picture.
	for index in 42:
		var a0 := TAU * index / 42.0
		var a1 := TAU * (index + 1) / 42.0
		var p0 := centre + Vector2(cos(a0), sin(a0)) * radius
		var p1 := centre + Vector2(cos(a1), sin(a1)) * radius
		var q0 := centre + Vector2(cos(a0), sin(a0)) * (radius + 90.0)
		var q1 := centre + Vector2(cos(a1), sin(a1)) * (radius + 90.0)
		_scope.draw_colored_polygon([p0, p1, q1, q0], dark)

	var ink := Color(0.05, 0.06, 0.05, 0.95)
	_scope.draw_arc(centre, radius, 0.0, TAU, 96, Color(0, 0, 0, 0.95), 5.0, true)
	_scope.draw_line(centre + Vector2(-radius, 0), centre + Vector2(-radius * 0.12, 0), ink, 2.0)
	_scope.draw_line(centre + Vector2(radius * 0.12, 0), centre + Vector2(radius, 0), ink, 2.0)
	_scope.draw_line(centre + Vector2(0, -radius), centre + Vector2(0, -radius * 0.12), ink, 2.0)
	_scope.draw_line(centre + Vector2(0, radius * 0.12), centre + Vector2(0, radius), ink, 2.0)
	# Mil ticks down the vertical, the part that makes it read as a scope.
	for index in range(1, 5):
		var y := radius * 0.16 * index
		var width := radius * (0.06 if index % 2 else 0.10)
		_scope.draw_line(centre + Vector2(-width, y), centre + Vector2(width, y), ink, 2.0)
	_scope.draw_circle(centre, 2.0, ink)


func _draw() -> void:
	# Movement stick. Always drawn, dimmed when idle, so the player knows where
	# it is before touching the screen.
	var idle: bool = _stick_finger == -1
	var base_alpha := 0.10 if idle else 0.20
	draw_circle(_stick_origin, STICK_RADIUS, Color(1, 1, 1, base_alpha * 0.6))
	draw_arc(_stick_origin, STICK_RADIUS, 0.0, TAU, 48, Color(1, 1, 1, base_alpha + 0.18), 2.0, true)
	draw_circle(_knob, 30.0, Color(1, 1, 1, base_alpha + 0.16))
	draw_arc(_knob, 30.0, 0.0, TAU, 32, Color(1, 1, 1, base_alpha + 0.28), 2.0, true)

	# Crosshair, hidden while scoped because the scope draws its own reticle.
	if not _scope.visible:
		var centre := size * 0.5
		var gap := 7.0
		var length := 13.0
		var colour := Color(1, 1, 1, 0.75)
		for dir in [Vector2.LEFT, Vector2.RIGHT, Vector2.UP, Vector2.DOWN]:
			draw_line(centre + dir * gap, centre + dir * (gap + length), colour, 2.0, true)
		draw_circle(centre, 1.5, colour)

	if _hit_marker_time > 0.0:
		var centre := size * 0.5
		var alpha: float = clampf(_hit_marker_time / 0.25, 0.0, 1.0)
		var mark := Color(1.0, 0.35, 0.3, alpha)
		for dir in [Vector2(1, 1), Vector2(-1, 1), Vector2(1, -1), Vector2(-1, -1)]:
			draw_line(centre + dir * 9.0, centre + dir * 19.0, mark, 2.5, true)

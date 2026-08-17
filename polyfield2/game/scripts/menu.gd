extends Control
## Main menu, settings and pause, built in code.
##
## The game used to boot straight into the level with no way out and no way to
## change anything. This is the shell around the match: a title screen, a
## quality selector that matters on a phone, and a pause overlay.

const GAME_SCENE := "res://scenes/main.tscn"

enum Page { TITLE, SETTINGS }

var _pages: Dictionary = {}
var _quality_buttons: Array[Button] = []


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)

	# The capture harness lives inside the match scene, so a --shot run that
	# stops at the title screen never arms it and never exits — it just sits
	# here until something kills it. Boot straight into the match instead.
	if OS.get_cmdline_user_args().has("--shot"):
		print("[Menu] --shot given, entering the match directly")
		call_deferred("_on_play")
		return

	_build()
	_show(Page.TITLE)


func _panel(colour: Color, radius: int = 10) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = colour
	style.corner_radius_top_left = radius
	style.corner_radius_top_right = radius
	style.corner_radius_bottom_left = radius
	style.corner_radius_bottom_right = radius
	style.content_margin_left = 20
	style.content_margin_right = 20
	style.content_margin_top = 12
	style.content_margin_bottom = 12
	return style


func _button(text: String, size: int = 22) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(300, 58)
	button.add_theme_font_size_override("font_size", size)
	button.add_theme_stylebox_override("normal", _panel(Color(0.11, 0.14, 0.17, 0.92)))
	button.add_theme_stylebox_override("hover", _panel(Color(0.17, 0.22, 0.27, 0.95)))
	button.add_theme_stylebox_override("pressed", _panel(Color(0.26, 0.42, 0.56, 0.98)))
	button.add_theme_stylebox_override("focus", _panel(Color(0, 0, 0, 0)))
	return button


func _column(name: String) -> VBoxContainer:
	var wrapper := CenterContainer.new()
	wrapper.name = name
	wrapper.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(wrapper)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	wrapper.add_child(column)
	return column


func _build() -> void:
	var background := ColorRect.new()
	background.color = Color(0.07, 0.09, 0.11)
	background.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	# --- title ---------------------------------------------------------------
	var title_page := _column("TitlePage")
	_pages[Page.TITLE] = title_page.get_parent()

	var title := Label.new()
	title.text = "POLYFIELD 2"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 56)
	title_page.add_child(title)

	var subtitle := Label.new()
	subtitle.text = "RIDGELINE"
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle.add_theme_font_size_override("font_size", 22)
	subtitle.add_theme_color_override("font_color", Color(0.62, 0.70, 0.76))
	title_page.add_child(subtitle)

	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 30)
	title_page.add_child(spacer)

	var play := _button("SAVAŞA GİR", 26)
	play.pressed.connect(_on_play)
	title_page.add_child(play)

	var settings := _button("AYARLAR")
	settings.pressed.connect(func() -> void: _show(Page.SETTINGS))
	title_page.add_child(settings)

	var quit := _button("ÇIKIŞ")
	quit.pressed.connect(func() -> void: get_tree().quit())
	title_page.add_child(quit)

	# --- settings ------------------------------------------------------------
	var settings_page := _column("SettingsPage")
	_pages[Page.SETTINGS] = settings_page.get_parent()

	var heading := Label.new()
	heading.text = "AYARLAR"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_size_override("font_size", 34)
	settings_page.add_child(heading)

	var quality_label := Label.new()
	quality_label.text = "Grafik kalitesi"
	quality_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	settings_page.add_child(quality_label)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	settings_page.add_child(row)
	for level in [Settings.Quality.LOW, Settings.Quality.MEDIUM, Settings.Quality.HIGH]:
		var button := _button(str(Settings.PRESETS[level]["label"]), 20)
		button.custom_minimum_size = Vector2(140, 52)
		button.pressed.connect(_on_quality.bind(level))
		row.add_child(button)
		_quality_buttons.append(button)

	var sensitivity_label := Label.new()
	sensitivity_label.text = "Bakış hassasiyeti"
	sensitivity_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	settings_page.add_child(sensitivity_label)

	var slider := HSlider.new()
	slider.min_value = 0.3
	slider.max_value = 2.5
	slider.step = 0.1
	slider.value = Settings.look_sensitivity
	slider.custom_minimum_size = Vector2(300, 28)
	slider.value_changed.connect(func(value: float) -> void:
		Settings.look_sensitivity = value
		Settings.save_settings())
	settings_page.add_child(slider)

	var fps_toggle := _button("FPS göstergesi: %s" % ("AÇIK" if Settings.show_fps else "KAPALI"))
	fps_toggle.pressed.connect(func() -> void:
		Settings.show_fps = not Settings.show_fps
		Settings.save_settings()
		fps_toggle.text = "FPS göstergesi: %s" % ("AÇIK" if Settings.show_fps else "KAPALI"))
	settings_page.add_child(fps_toggle)

	var back := _button("GERİ")
	back.pressed.connect(func() -> void: _show(Page.TITLE))
	settings_page.add_child(back)

	_refresh_quality()


func _show(page: int) -> void:
	for key: int in _pages:
		_pages[key].visible = key == page


func _on_quality(level: int) -> void:
	Settings.set_quality(level)
	_refresh_quality()


func _refresh_quality() -> void:
	for index in _quality_buttons.size():
		var selected: bool = index == Settings.quality
		_quality_buttons[index].add_theme_stylebox_override("normal",
			_panel(Color(0.26, 0.42, 0.56, 0.98) if selected else Color(0.11, 0.14, 0.17, 0.92)))


func _on_play() -> void:
	get_tree().change_scene_to_file(GAME_SCENE)

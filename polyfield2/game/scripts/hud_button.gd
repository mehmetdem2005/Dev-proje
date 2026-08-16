extends Control
class_name HudButton
## A round touch button that draws its own vector icon.
##
## The first HUD used stock Buttons with the action name as text ("FIRE",
## "CROUCH"). That reads as debug UI, and text labels are the slowest thing to
## parse mid-firefight. These are icons at thumb size, drawn in code so there
## is no icon atlas to ship or scale.

signal pressed_down
signal released

@export var icon: StringName = &"fire"
@export var radius: float = 46.0
@export var toggle_mode: bool = false
@export var accent: Color = Color(0.86, 0.90, 0.94)

var held: bool = false
var toggled: bool = false

var _finger: int = -1


func _ready() -> void:
	custom_minimum_size = Vector2(radius * 2.0, radius * 2.0)
	size = custom_minimum_size
	mouse_filter = Control.MOUSE_FILTER_STOP


func contains(point: Vector2) -> bool:
	return point.distance_to(global_position + size * 0.5) <= radius * 1.08


## Driven by the HUD's own multi-touch router rather than by _gui_input, so a
## finger that starts on a button keeps owning it even if it drifts off.
func press(finger: int) -> void:
	if _finger != -1:
		return
	_finger = finger
	held = true
	if toggle_mode:
		toggled = not toggled
	queue_redraw()
	pressed_down.emit()


func release(finger: int) -> void:
	if finger != _finger:
		return
	_finger = -1
	held = false
	queue_redraw()
	released.emit()


func owns(finger: int) -> bool:
	return _finger == finger


func _draw() -> void:
	var centre := size * 0.5
	var lit: bool = held or (toggle_mode and toggled)

	var fill := Color(0.06, 0.08, 0.10, 0.34)
	var rim := Color(1, 1, 1, 0.22)
	if lit:
		fill = Color(0.22, 0.42, 0.58, 0.62)
		rim = Color(1, 1, 1, 0.55)

	draw_circle(centre, radius, fill)
	draw_arc(centre, radius, 0.0, TAU, 44, rim, 2.5, true)

	var ink := accent if not lit else Color.WHITE
	var r := radius * 0.46
	match icon:
		&"fire":
			# Crosshair-in-ring: the universal "shoot" affordance.
			draw_arc(centre, r, 0.0, TAU, 28, ink, 3.0, true)
			for angle in [0.0, PI * 0.5, PI, PI * 1.5]:
				var dir := Vector2(cos(angle), sin(angle))
				draw_line(centre + dir * r * 0.45, centre + dir * r * 1.35, ink, 3.0, true)
		&"aim":
			# Scope reticle.
			draw_arc(centre, r, 0.0, TAU, 28, ink, 2.5, true)
			draw_line(centre + Vector2(-r * 1.3, 0), centre + Vector2(r * 1.3, 0), ink, 2.0, true)
			draw_line(centre + Vector2(0, -r * 1.3), centre + Vector2(0, r * 1.3), ink, 2.0, true)
			draw_circle(centre, 2.5, ink)
		&"crouch":
			# Down chevrons.
			for index in 2:
				var y := -r * 0.35 + index * r * 0.7
				draw_polyline([centre + Vector2(-r * 0.75, y),
							   centre + Vector2(0, y + r * 0.55),
							   centre + Vector2(r * 0.75, y)], ink, 3.0, true)
		&"jump":
			# Up chevron over a ground line.
			draw_polyline([centre + Vector2(-r * 0.75, r * 0.1),
						   centre + Vector2(0, -r * 0.6),
						   centre + Vector2(r * 0.75, r * 0.1)], ink, 3.0, true)
			draw_line(centre + Vector2(-r * 0.8, r * 0.75),
					  centre + Vector2(r * 0.8, r * 0.75), ink, 3.0, true)
		&"reload":
			# Circular arrow.
			draw_arc(centre, r, PI * 0.35, PI * 1.9, 26, ink, 3.0, true)
			var tip := centre + Vector2(cos(PI * 0.35), sin(PI * 0.35)) * r
			draw_polyline([tip + Vector2(-6, -7), tip, tip + Vector2(7, -4)], ink, 3.0, true)
		&"sprint":
			# Motion lines.
			for index in 3:
				var y := -r * 0.5 + index * r * 0.5
				var length := r * (1.1 - index * 0.22)
				draw_line(centre + Vector2(-length, y), centre + Vector2(length * 0.5, y),
						  ink, 3.0, true)
		&"weapon":
			# Simple rifle profile.
			draw_line(centre + Vector2(-r, -r * 0.15), centre + Vector2(r, -r * 0.15), ink, 4.0, true)
			draw_line(centre + Vector2(-r * 0.55, -r * 0.15),
					  centre + Vector2(-r * 0.95, r * 0.6), ink, 4.0, true)
			draw_line(centre + Vector2(r * 0.15, -r * 0.15),
					  centre + Vector2(r * 0.05, r * 0.35), ink, 3.0, true)
		&"pause":
			draw_rect(Rect2(centre + Vector2(-r * 0.5, -r * 0.7), Vector2(r * 0.3, r * 1.4)), ink)
			draw_rect(Rect2(centre + Vector2(r * 0.2, -r * 0.7), Vector2(r * 0.3, r * 1.4)), ink)

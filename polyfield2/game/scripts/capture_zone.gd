extends Area3D
## A Territory Control point.
##
## Capture is a tug of war on a single -1..+1 bar rather than two independent
## timers: whoever has more bodies inside drags the bar their way, and a
## contested zone simply stops moving. One value keeps the HUD honest and
## removes the "both teams capturing at once" state entirely.

signal owner_changed(zone_id: String, new_owner: String)

const CAPTURE_RATE := 0.14      ## bar units per second per net attacker
const MAX_RATE_BODIES := 4      ## more than this stops speeding it up

var zone_id: String = "?"
var radius: float = 10.0
var owner_team: String = "neutral"
var progress: float = 0.0       ## -1 = legion held, +1 = ranger held

var _occupants: Dictionary = {"ranger": 0, "legion": 0}


func setup(id: String, initial_owner: String, zone_radius: float) -> void:
	zone_id = id
	radius = zone_radius
	owner_team = initial_owner
	progress = 1.0 if initial_owner == "ranger" else (-1.0 if initial_owner == "legion" else 0.0)
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


func _team_of(body: Node) -> String:
	if body.has_method("get_team"):
		return str(body.call("get_team"))
	return ""


func _on_body_entered(body: Node3D) -> void:
	var team := _team_of(body)
	if _occupants.has(team):
		_occupants[team] += 1


func _on_body_exited(body: Node3D) -> void:
	var team := _team_of(body)
	if _occupants.has(team) and _occupants[team] > 0:
		_occupants[team] -= 1


func _physics_process(delta: float) -> void:
	var rangers: int = _occupants["ranger"]
	var legion: int = _occupants["legion"]
	var net := clampi(rangers - legion, -MAX_RATE_BODIES, MAX_RATE_BODIES)
	if net == 0:
		return

	progress = clampf(progress + net * CAPTURE_RATE * delta, -1.0, 1.0)

	var next_owner := owner_team
	if progress >= 1.0:
		next_owner = "ranger"
	elif progress <= -1.0:
		next_owner = "legion"
	elif absf(progress) < 0.999 and owner_team != "neutral":
		# Losing full control flips the point neutral before the other side
		# can score it, so a half-taken zone pays nobody.
		var held_sign := 1.0 if owner_team == "ranger" else -1.0
		if progress * held_sign < 0.6:
			next_owner = "neutral"

	if next_owner != owner_team:
		owner_team = next_owner
		owner_changed.emit(zone_id, owner_team)


func contested() -> bool:
	return _occupants["ranger"] > 0 and _occupants["legion"] > 0


func occupancy() -> Dictionary:
	return _occupants.duplicate()

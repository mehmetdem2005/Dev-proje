extends CharacterBody3D
## First-person player.
##
## Input arrives from two places that must not fight each other: keyboard/mouse
## (desktop, and the only way to drive this in a headless test) and the touch
## HUD. Both are folded into the same `_move_input` / `_look_input` vectors at
## the top of the frame, so nothing downstream cares which one is live.

const WALK_SPEED := 4.6
const SPRINT_SPEED := 7.2
const CROUCH_SPEED := 2.3
const ACCELERATION := 12.0
const AIR_ACCELERATION := 2.5
const JUMP_VELOCITY := 6.2
const MOUSE_SENSITIVITY := 0.0022
const TOUCH_SENSITIVITY := 0.0042
const STAND_HEIGHT := 1.75
const CROUCH_HEIGHT := 1.15
const CROUCH_LERP := 9.0
const VIEWMODEL_PATH := "res://assets/models/viewmodel.glb"

signal weapon_changed(name: String, ammo: int, reserve: int)
signal ammo_changed(ammo: int, reserve: int)
signal health_changed(health: float)

@export var team: String = "ranger"

var health: float = 100.0
var _pitch: float = 0.0
var _move_input: Vector2 = Vector2.ZERO
var _look_input: Vector2 = Vector2.ZERO
var _crouching: bool = false
var _bob_time: float = 0.0
var _recoil: Vector2 = Vector2.ZERO
var _recoil_velocity: Vector2 = Vector2.ZERO
var _fire_cooldown: float = 0.0
var _reload_timer: float = 0.0
var _aiming: bool = false
var _scoped: bool = false
var _viewmodel: Node3D = null
var _viewmodel_anim: AnimationPlayer = null
var _viewmodel_state: String = ""
var _viewmodel_lock: float = 0.0

var _weapons: Array[Dictionary] = []
var _weapon_index: int = 0
var _hud: Node = null

@onready var _head: Node3D = $Head
@onready var _camera: Camera3D = $Head/Camera3D
@onready var _weapon_pivot: Node3D = $Head/Camera3D/WeaponPivot
@onready var _collision: CollisionShape3D = $CollisionShape3D
@onready var _muzzle_ray: RayCast3D = $Head/Camera3D/MuzzleRay


func get_team() -> String:
	return team


func _ready() -> void:
	add_to_group("players")
	_weapons = _weapon_table()
	_ensure_hud()
	_equip(0)
	health_changed.emit(health)
	if DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


## Resolve the HUD lazily instead of once in _ready().
##
## The player is declared before the HUD layer in main.tscn, so at the moment
## _ready() runs the HUD has not yet added itself to its group and the lookup
## returns null — which silently killed every touch input: fire, aim, crouch,
## jump and look all went nowhere on a phone. Resolving on demand makes the
## wiring independent of scene ordering, so this cannot regress by someone
## moving a node.
func _ensure_hud() -> bool:
	if _hud != null and is_instance_valid(_hud):
		return true
	_hud = get_tree().get_first_node_in_group("hud")
	if _hud == null:
		return false
	if _hud.has_signal("weapon_cycle_requested") \
			and not _hud.weapon_cycle_requested.is_connected(cycle_weapon):
		_hud.weapon_cycle_requested.connect(cycle_weapon)
	_hud.call("set_weapon_scoped", bool(_weapon().get("scoped", false)))
	print("[Player] HUD connected")
	return true


func _weapon_table() -> Array[Dictionary]:
	# Fire interval and recoil are what actually differentiate these in the
	# hand; damage numbers are placeholders until balance passes happen.
	return [
		{"id": "wpn_rifle", "label": "Rifle", "interval": 0.85, "damage": 48.0,
		 "mag": 5, "reserve": 40, "recoil": Vector2(0.030, 0.010), "spread": 0.004,
		 "auto": false, "reload": 2.4, "scoped": true, "scope_fov": 20.0},
		{"id": "wpn_smg", "label": "SMG", "interval": 0.085, "damage": 16.0,
		 "mag": 32, "reserve": 190, "recoil": Vector2(0.012, 0.006), "spread": 0.016,
		 "auto": true, "reload": 1.9},
		{"id": "wpn_lmg", "label": "LMG", "interval": 0.11, "damage": 24.0,
		 "mag": 50, "reserve": 200, "recoil": Vector2(0.016, 0.008), "spread": 0.020,
		 "auto": true, "reload": 4.2, "scoped": false},
		{"id": "wpn_pistol", "label": "Pistol", "interval": 0.20, "damage": 22.0,
		 "mag": 8, "reserve": 56, "recoil": Vector2(0.018, 0.008), "spread": 0.009,
		 "auto": false, "reload": 1.5},
		{"id": "wpn_launcher", "label": "Launcher", "interval": 1.4, "damage": 120.0,
		 "mag": 1, "reserve": 4, "recoil": Vector2(0.070, 0.020), "spread": 0.002,
		 "auto": false, "reload": 3.2},
	]


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion := event as InputEventMouseMotion
		_look_input += motion.relative * MOUSE_SENSITIVITY
	elif event.is_action_pressed("next_weapon"):
		_equip((_weapon_index + 1) % _weapons.size())
	elif event.is_action_pressed("reload"):
		begin_reload()


func _gather_input() -> void:
	_move_input = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var sprinting := Input.is_action_pressed("sprint")
	_crouching = Input.is_action_pressed("crouch")
	_aiming = Input.is_action_pressed("aim")

	if _ensure_hud():
		var stick: Vector2 = _hud.move_vector
		if stick.length() > 0.05:
			_move_input = Vector2(stick.x, -stick.y)
		_look_input += _hud.consume_look() * TOUCH_SENSITIVITY
		_crouching = _crouching or _hud.crouch_held
		_aiming = _aiming or _hud.aim_held
		sprinting = sprinting or _hud.sprint_held

	_move_input = _move_input.limit_length(1.0)
	set_meta("sprinting", sprinting)


func _physics_process(delta: float) -> void:
	_gather_input()
	_apply_look(delta)
	_apply_crouch(delta)
	_apply_movement(delta)
	_apply_weapon(delta)
	_apply_bob(delta)
	_update_viewmodel(delta)


func _apply_look(delta: float) -> void:
	if _look_input != Vector2.ZERO:
		var sensitivity := Settings.look_sensitivity
		var pitch_sign := -1.0 if Settings.invert_look else 1.0
		# Aiming slows the look, and a scoped shot slows it much further —
		# without this, a 6x sight is unusable with a thumb.
		var aim_scale := 1.0
		if _aiming:
			aim_scale = 0.32 if _scoped else 0.55
		rotate_y(-_look_input.x * sensitivity * aim_scale)
		_pitch = clampf(_pitch - _look_input.y * sensitivity * aim_scale * pitch_sign,
			-1.45, 1.45)
		_look_input = Vector2.ZERO

	# Recoil is a spring on top of the aim rather than a permanent offset, so
	# the sight walks up and settles back instead of drifting away forever.
	_recoil_velocity = _recoil_velocity.lerp(Vector2.ZERO, clampf(delta * 9.0, 0.0, 1.0))
	_recoil = _recoil.lerp(Vector2.ZERO, clampf(delta * 6.5, 0.0, 1.0)) + _recoil_velocity * delta
	_head.rotation.x = _pitch + _recoil.y
	_head.rotation.z = _recoil.x * 0.35


func _apply_crouch(delta: float) -> void:
	var target := CROUCH_HEIGHT if _crouching else STAND_HEIGHT
	var capsule := _collision.shape as CapsuleShape3D
	if capsule != null:
		capsule.height = lerpf(capsule.height, target, clampf(delta * CROUCH_LERP, 0.0, 1.0))
		_collision.position.y = capsule.height * 0.5
	_head.position.y = lerpf(_head.position.y, target - 0.18,
		clampf(delta * CROUCH_LERP, 0.0, 1.0))


func _apply_movement(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	elif Input.is_action_just_pressed("jump") or (_hud != null and _hud.consume_jump()):
		velocity.y = JUMP_VELOCITY

	var speed := WALK_SPEED
	if _crouching:
		speed = CROUCH_SPEED
	elif get_meta("sprinting", false) and _move_input.y < -0.1:
		speed = SPRINT_SPEED
	if _aiming:
		speed *= 0.55

	var direction := (transform.basis * Vector3(_move_input.x, 0.0, _move_input.y)).normalized()
	var target := direction * speed * _move_input.length()
	var rate := ACCELERATION if is_on_floor() else AIR_ACCELERATION
	velocity.x = move_toward(velocity.x, target.x, rate * delta * speed)
	velocity.z = move_toward(velocity.z, target.z, rate * delta * speed)

	move_and_slide()


func _apply_bob(delta: float) -> void:
	var planar := Vector2(velocity.x, velocity.z).length()
	if is_on_floor() and planar > 0.4:
		_bob_time += delta * planar * 1.5
	else:
		_bob_time = lerpf(_bob_time, 0.0, clampf(delta * 4.0, 0.0, 1.0))
	var amount := 0.018 if not _aiming else 0.005
	_camera.position.y = sin(_bob_time * 2.0) * amount
	_camera.position.x = sin(_bob_time) * amount * 0.6


func _weapon() -> Dictionary:
	return _weapons[_weapon_index]


func _equip(index: int) -> void:
	_weapon_index = index
	var weapon := _weapon()
	_reload_timer = 0.0
	_fire_cooldown = 0.0
	if not weapon.has("loaded"):
		weapon["loaded"] = int(weapon["mag"])
	_rebuild_viewmodel(str(weapon["id"]))
	if _hud != null:
		_hud.call("set_weapon_scoped", bool(weapon.get("scoped", false)))
	weapon_changed.emit(str(weapon["label"]), int(weapon["loaded"]), int(weapon["reserve"]))


func _rebuild_viewmodel(_weapon_id: String) -> void:
	"""Instance the animated first-person viewmodel.

	The first build parented a bare weapon mesh to the camera: no arms, and
	nothing moved when you fired. This loads the rigged viewmodel and keeps a
	handle on its AnimationPlayer so firing, reloading and aiming drive real
	motion — including the bolt cycling and the magazine leaving the well.
	"""
	if _viewmodel != null and is_instance_valid(_viewmodel):
		return

	var packed := ResourceLoader.load(VIEWMODEL_PATH) as PackedScene
	if packed == null:
		push_error("[Player] viewmodel missing at %s" % VIEWMODEL_PATH)
		return

	_viewmodel = packed.instantiate()
	# Authored at world scale in camera space, which puts the rifle 30 cm from
	# the eye and filling a quarter of the screen. Scale it down and push it
	# out to normal first-person framing.
	_viewmodel.scale = Vector3(0.60, 0.60, 0.60)
	_viewmodel.position = Vector3(0.012, -0.055, -0.175)
	_weapon_pivot.add_child(_viewmodel)

	var queue: Array[Node] = [_viewmodel]
	while not queue.is_empty():
		var node: Node = queue.pop_back()
		if node is AnimationPlayer:
			_viewmodel_anim = node
		elif node is MeshInstance3D:
			MaterialLibrary.apply_to(node)
			# The viewmodel lives inside the world but must never be occluded
			# by it or cast shadows into it.
			node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		queue.append_array(node.get_children())

	if _viewmodel_anim != null:
		for clip: String in _viewmodel_anim.get_animation_list():
			var animation := _viewmodel_anim.get_animation(clip)
			if animation == null:
				continue
			animation.loop_mode = (Animation.LOOP_LINEAR
				if clip in ["vm_idle", "vm_walk", "vm_aim"] else Animation.LOOP_NONE)
		_viewmodel_anim.set_blend_time("vm_idle", "vm_walk", 0.2)
		_viewmodel_anim.set_blend_time("vm_walk", "vm_idle", 0.2)
		_viewmodel_anim.play("vm_draw")
		_viewmodel_state = "vm_draw"


## One-shots (fire, reload, draw) must finish before locomotion resumes.
func _play_viewmodel(clip: String, force: bool = false) -> void:
	if _viewmodel_anim == null or not _viewmodel_anim.has_animation(clip):
		return
	if _viewmodel_state == clip and not force:
		return
	_viewmodel_state = clip
	_viewmodel_anim.play(clip, 0.12)


func _update_viewmodel(delta: float) -> void:
	if _viewmodel_anim == null:
		return
	_viewmodel_lock = maxf(0.0, _viewmodel_lock - delta)
	if _viewmodel_lock > 0.0:
		return

	if _aiming:
		_play_viewmodel("vm_aim")
		return
	var planar := Vector2(velocity.x, velocity.z).length()
	_play_viewmodel("vm_walk" if (is_on_floor() and planar > 0.6) else "vm_idle")


func cycle_weapon() -> void:
	_equip((_weapon_index + 1) % _weapons.size())
	_play_viewmodel("vm_draw", true)
	_viewmodel_lock = 0.6


func begin_reload() -> void:
	var weapon := _weapon()
	if _reload_timer > 0.0:
		return
	if int(weapon["loaded"]) >= int(weapon["mag"]) or int(weapon["reserve"]) <= 0:
		return
	_reload_timer = float(weapon["reload"])
	# Hold locomotion off for the length of the clip so the reload plays out.
	_play_viewmodel("vm_reload", true)
	_viewmodel_lock = 2.0


func _apply_weapon(delta: float) -> void:
	var weapon := _weapon()
	_fire_cooldown = maxf(0.0, _fire_cooldown - delta)

	if _reload_timer > 0.0:
		_reload_timer -= delta
		if _reload_timer <= 0.0:
			var needed: int = int(weapon["mag"]) - int(weapon["loaded"])
			var taken: int = mini(needed, int(weapon["reserve"]))
			weapon["loaded"] = int(weapon["loaded"]) + taken
			weapon["reserve"] = int(weapon["reserve"]) - taken
			ammo_changed.emit(int(weapon["loaded"]), int(weapon["reserve"]))
	else:
		var wants_fire := Input.is_action_pressed("fire") if bool(weapon["auto"]) \
			else Input.is_action_just_pressed("fire")
		if _hud != null:
			wants_fire = wants_fire or (_hud.fire_held if bool(weapon["auto"]) else _hud.consume_fire())
		if wants_fire and _fire_cooldown <= 0.0:
			_fire(weapon)

	# Aiming pulls the weapon towards the centre of the screen and narrows FOV.
	# Position is animated by the viewmodel rig now; the pivot only holds it.
	var rest := Vector3.ZERO
	var sighted := Vector3.ZERO
	var target := sighted if _aiming else rest
	# A scoped weapon hides the viewmodel entirely: you are looking down the
	# sight, not over it.
	var scoped_now := _aiming and bool(weapon.get("scoped", false))
	if scoped_now != _scoped and _hud != null:
		_hud.call("set_weapon_scoped", bool(weapon.get("scoped", false)))
	_scoped = scoped_now
	_weapon_pivot.visible = not _scoped
	_weapon_pivot.position = _weapon_pivot.position.lerp(target, clampf(delta * 12.0, 0.0, 1.0))

	var target_fov := 75.0
	if _scoped:
		target_fov = float(weapon.get("scope_fov", 22.0))
	elif _aiming:
		target_fov = 52.0
	_camera.fov = lerpf(_camera.fov, target_fov, clampf(delta * 12.0, 0.0, 1.0))


func _fire(weapon: Dictionary) -> void:
	if int(weapon["loaded"]) <= 0:
		begin_reload()
		return

	weapon["loaded"] = int(weapon["loaded"]) - 1
	_fire_cooldown = float(weapon["interval"])
	ammo_changed.emit(int(weapon["loaded"]), int(weapon["reserve"]))

	_play_viewmodel("vm_fire", true)
	_viewmodel_lock = 0.42

	var kick: Vector2 = weapon["recoil"]
	var spread := float(weapon["spread"]) * (0.4 if _aiming else 1.0)
	_recoil_velocity += Vector2(randf_range(-kick.x, kick.x) * 0.6, kick.y) * 22.0

	_muzzle_ray.rotation = Vector3(randf_range(-spread, spread), randf_range(-spread, spread), 0.0)
	_muzzle_ray.force_raycast_update()
	if _muzzle_ray.is_colliding():
		var hit := _muzzle_ray.get_collider()
		if hit != null and hit.has_method("take_damage"):
			hit.call("take_damage", float(weapon["damage"]), self)
			if _hud != null:
				_hud.call("flash_hit")


## Re-emit the full HUD-facing state. Needed because the player is ready
## before Main has wired the HUD to it.
func publish_state() -> void:
	var weapon := _weapon()
	weapon_changed.emit(str(weapon["label"]), int(weapon["loaded"]), int(weapon["reserve"]))
	health_changed.emit(health)


func take_damage(amount: float, _source: Node) -> void:
	health = maxf(0.0, health - amount)
	health_changed.emit(health)

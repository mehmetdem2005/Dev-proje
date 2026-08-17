extends CharacterBody3D
## An AI soldier.
##
## The first version walked in a straight line to a random capture zone and
## played a fire animation on a timer at nobody. This one actually fights:
##
##   * it looks for enemies within its view cone and confirms them with a
##     line-of-sight ray, so it does not shoot through a hill,
##   * it shoots at what it sees, with spread and a reaction delay, and deals
##     real damage,
##   * it steers around obstacles with whisker rays instead of grinding into
##     the first boulder on the path,
##   * it breaks for cover when hurt, and spreads out from squadmates so a
##     team does not walk as a single column.

const WALK_SPEED := 3.0
const RUN_SPEED := 5.8
const TURN_RATE := 5.0
const ARRIVAL_RADIUS := 5.0
const REPATH_INTERVAL := 8.0

const VIEW_RANGE := 85.0
const VIEW_ANGLE := 1.15          # radians, half-cone
const REACTION_TIME := 0.45
const BURST_INTERVAL := 0.16
const BURST_SIZE := 4
const BURST_PAUSE := 1.1
const SHOT_DAMAGE := 11.0
const SPREAD := 0.045
const SEPARATION_RADIUS := 6.0

enum State { ADVANCE, ENGAGE, COVER }

@export var team: String = "legion"

var health: float = 100.0

var _state: int = State.ADVANCE
var _target: Vector3 = Vector3.ZERO
var _repath_timer: float = 0.0
var _dead: bool = false
var _hit_timer: float = 0.0

var _enemy: Node3D = null
var _reaction: float = 0.0
var _shot_timer: float = 0.0
var _burst_left: int = 0
var _scan_timer: float = 0.0
var _cover_point: Vector3 = Vector3.ZERO
var _cover_timer: float = 0.0

var _animation: AnimationPlayer = null
var _clips: PackedStringArray = PackedStringArray()
var _current_clip: String = ""

var _eyes: RayCast3D
var _whisker_left: RayCast3D
var _whisker_right: RayCast3D
var _rng := RandomNumberGenerator.new()


func get_team() -> String:
	return team


func enemy_team() -> String:
	return "ranger" if team == "legion" else "legion"


func _ready() -> void:
	add_to_group("soldiers")
	add_to_group("combatants")
	_rng.randomize()
	_build_visual()
	_build_senses()
	_pick_target()
	_scan_timer = _rng.randf_range(0.0, 0.8)


func _build_senses() -> void:
	# Sight ray: collides with world (1) and with players/soldiers (2|4).
	_eyes = RayCast3D.new()
	_eyes.position = Vector3.UP * 1.55
	_eyes.collision_mask = 1 | 2 | 4
	_eyes.enabled = false          # only cast on demand, not every frame
	add_child(_eyes)

	for side in [-1.0, 1.0]:
		var whisker := RayCast3D.new()
		whisker.position = Vector3.UP * 0.9
		whisker.target_position = Vector3(side * 1.5, 0.0, -3.2)
		whisker.collision_mask = 1
		add_child(whisker)
		if side < 0.0:
			_whisker_left = whisker
		else:
			_whisker_right = whisker


func _build_visual() -> void:
	var path := "res://assets/models/soldier_%s.glb" % team
	var packed := ResourceLoader.load(path) as PackedScene
	if packed == null:
		push_error("[Soldier] missing %s" % path)
		return
	var model := packed.instantiate()
	add_child(model)

	var queue: Array[Node] = [model]
	while not queue.is_empty():
		var node: Node = queue.pop_back()
		if node is AnimationPlayer:
			_animation = node
		elif node is MeshInstance3D:
			MaterialLibrary.apply_to(node)
			# A soldier past the fort draw distance is a few pixels tall. Culling
			# the mesh also stops Godot skinning it, which is the expensive half.
			var mesh_instance := node as MeshInstance3D
			mesh_instance.visibility_range_end = 160.0
			mesh_instance.visibility_range_end_margin = 12.0
			mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		queue.append_array(node.get_children())

	if _animation != null:
		_clips = _animation.get_animation_list()
		for clip: String in _clips:
			var animation := _animation.get_animation(clip)
			if animation == null:
				continue
			animation.loop_mode = (Animation.LOOP_LINEAR
				if clip in ["idle", "walk", "run", "crouch_idle", "crouch_walk", "aim"]
				else Animation.LOOP_NONE)
		_animation.set_blend_time("walk", "run", 0.18)
		_animation.set_blend_time("idle", "walk", 0.22)
		_animation.set_blend_time("walk", "idle", 0.22)
		_play("idle")


func _play(clip: String, force: bool = false) -> void:
	if _animation == null or not _clips.has(clip):
		return
	if _current_clip == clip and not force:
		return
	_current_clip = clip
	_animation.play(clip, 0.2)


# ------------------------------------------------------------------ senses

func _eye_point() -> Vector3:
	return global_position + Vector3.UP * 1.55


## Can this soldier actually see `who`? Casts to the target's chest and checks
## the first thing hit is the target, so terrain and rocks block sight.
func _has_line_of_sight(who: Node3D) -> bool:
	if who == null or not is_instance_valid(who):
		return false
	var from := _eye_point()
	var to: Vector3 = who.global_position + Vector3.UP * 1.2
	_eyes.global_position = from
	_eyes.target_position = _eyes.to_local(to)
	_eyes.force_raycast_update()
	if not _eyes.is_colliding():
		return true
	return _eyes.get_collider() == who


## Stop animating soldiers nobody can see.
##
## An AnimationPlayer keeps evaluating its tracks and re-posing the skeleton
## every frame whether or not the mesh is on screen, and a skinned pose is not
## free — sixteen of them was real CPU spent on soldiers behind a hill. The AI
## keeps running; only the pose stops, so a bot never stands still because of
## this, it just stops interpolating a pose no one is looking at.
##
## Re-checked on the scan timer rather than per frame, so it costs one distance
## comparison a second per soldier.
func _throttle_animation() -> void:
	if _animation == null:
		return
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		return
	var far := global_position.distance_squared_to(camera.global_position) > 160.0 * 160.0
	if _animation.active == far:
		_animation.active = not far


func _scan_for_enemy() -> void:
	var best: Node3D = null
	var best_distance := VIEW_RANGE
	var forward := -global_transform.basis.z

	for candidate in get_tree().get_nodes_in_group("combatants"):
		if candidate == self or not is_instance_valid(candidate):
			continue
		if not candidate.has_method("get_team") or candidate.get_team() != enemy_team():
			continue
		# Cheap rejections before the raycast, which is the expensive part.
		if candidate.global_position.distance_squared_to(global_position) > VIEW_RANGE * VIEW_RANGE:
			continue
		if candidate.get("health") != null and float(candidate.get("health")) <= 0.0:
			continue

		var offset: Vector3 = candidate.global_position - global_position
		var distance := offset.length()
		if distance > best_distance:
			continue
		# Behind you is not visible.
		if forward.dot(offset.normalized()) < cos(VIEW_ANGLE):
			continue
		if not _has_line_of_sight(candidate):
			continue
		best = candidate
		best_distance = distance

	if best != _enemy:
		_enemy = best
		_reaction = REACTION_TIME if best != null else 0.0


# ------------------------------------------------------------------ steering

func _pick_target() -> void:
	var zones := get_tree().get_nodes_in_group("capture_zones")
	_repath_timer = REPATH_INTERVAL
	if zones.is_empty():
		return
	# Prefer zones the team does not already hold.
	var options: Array = []
	for zone in zones:
		if str(zone.get("owner_team")) != team:
			options.append(zone)
	if options.is_empty():
		options = zones
	var zone: Node3D = options[_rng.randi() % options.size()]
	var angle := _rng.randf() * TAU
	_target = zone.global_position + Vector3(cos(angle), 0.0, sin(angle)) * _rng.randf_range(2.0, 8.0)


## Whisker rays plus squadmate separation. Cheap, and enough to stop the
## column-of-soldiers-stuck-on-a-rock behaviour the first version had.
func _steer(desired: Vector3) -> Vector3:
	var steering := desired
	if _whisker_left != null and _whisker_left.is_colliding():
		steering += global_transform.basis.x * 1.4
	if _whisker_right != null and _whisker_right.is_colliding():
		steering -= global_transform.basis.x * 1.4

	for other in get_tree().get_nodes_in_group("soldiers"):
		if other == self or not is_instance_valid(other):
			continue
		var offset: Vector3 = global_position - other.global_position
		offset.y = 0.0
		var distance := offset.length()
		if distance > 0.01 and distance < SEPARATION_RADIUS:
			steering += offset.normalized() * (1.0 - distance / SEPARATION_RADIUS) * 1.6

	steering.y = 0.0
	return steering.normalized() if steering.length() > 0.01 else Vector3.ZERO


func _nearest_cover() -> Vector3:
	"""Closest static collider within a short radius — rocks, sandbags, crates."""
	var space := get_world_3d().direct_space_state
	var best := global_position
	var best_distance := 1e9
	for angle_index in 8:
		var angle := TAU * angle_index / 8.0
		var direction := Vector3(cos(angle), 0.0, sin(angle))
		var query := PhysicsRayQueryParameters3D.create(
			_eye_point(), _eye_point() + direction * 9.0, 1)
		var hit := space.intersect_ray(query)
		if hit.is_empty():
			continue
		var point: Vector3 = hit["position"]
		var distance := point.distance_to(global_position)
		if distance < best_distance:
			best_distance = distance
			best = point - direction * 1.1
	return best


# ------------------------------------------------------------------ combat

func _shoot_at(who: Node3D) -> void:
	var from := _eye_point()
	var to: Vector3 = who.global_position + Vector3.UP * 1.1
	var direction := (to - from).normalized()
	direction += Vector3(_rng.randfn(0.0, SPREAD), _rng.randfn(0.0, SPREAD),
		_rng.randfn(0.0, SPREAD))

	var space := get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(from, from + direction.normalized() * VIEW_RANGE,
		1 | 2 | 4)
	query.exclude = [get_rid()]
	var hit := space.intersect_ray(query)
	if hit.is_empty():
		return
	var collider = hit.get("collider")
	if collider != null and collider.has_method("take_damage"):
		collider.call("take_damage", SHOT_DAMAGE, self)
	_play("fire", true)
	_current_clip = ""
	Audio.play_at("fire_rifle", _eye_point(), -6.0)


func _combat(delta: float) -> void:
	if _enemy == null or not is_instance_valid(_enemy):
		_enemy = null
		return
	if _reaction > 0.0:
		_reaction -= delta
		return

	_shot_timer -= delta
	if _shot_timer > 0.0:
		return

	if _burst_left <= 0:
		_burst_left = BURST_SIZE
		_shot_timer = BURST_PAUSE * _rng.randf_range(0.7, 1.4)
		return

	_burst_left -= 1
	_shot_timer = BURST_INTERVAL
	_shoot_at(_enemy)


# ------------------------------------------------------------------ tick

func _physics_process(delta: float) -> void:
	if _dead:
		if not is_on_floor():
			velocity += get_gravity() * delta
			move_and_slide()
		return

	if not is_on_floor():
		velocity += get_gravity() * delta

	_scan_timer -= delta
	if _scan_timer <= 0.0:
		# Scanning every frame for every soldier is wasted work; a few times a
		# second is well inside human reaction time anyway.
		_scan_timer = _rng.randf_range(0.55, 0.85)
		_scan_for_enemy()
		_throttle_animation()

	if health < 35.0 and _enemy != null:
		_state = State.COVER
	elif _enemy != null:
		_state = State.ENGAGE
	else:
		_state = State.ADVANCE

	var desired := Vector3.ZERO
	var speed := WALK_SPEED

	match _state:
		State.ADVANCE:
			_repath_timer -= delta
			var to_target := _target - global_position
			to_target.y = 0.0
			if to_target.length() < ARRIVAL_RADIUS or _repath_timer <= 0.0:
				_pick_target()
				to_target = _target - global_position
				to_target.y = 0.0
			desired = to_target.normalized()
			speed = RUN_SPEED if to_target.length() > 20.0 else WALK_SPEED

		State.ENGAGE:
			# Close to a useful range, then hold and shoot.
			var offset: Vector3 = _enemy.global_position - global_position
			offset.y = 0.0
			var distance := offset.length()
			if distance > 35.0:
				desired = offset.normalized()
				speed = WALK_SPEED
			elif distance < 12.0:
				desired = -offset.normalized()
				speed = WALK_SPEED
			_combat(delta)

		State.COVER:
			# Cover is found once and reused; eight rays every physics frame
			# for every soldier is what stalled the first version of this.
			_cover_timer -= delta
			if _cover_timer <= 0.0:
				_cover_point = _nearest_cover()
				_cover_timer = 2.5
			var to_cover := _cover_point - global_position
			to_cover.y = 0.0
			if to_cover.length() > 1.2:
				desired = to_cover.normalized()
				speed = RUN_SPEED
			_combat(delta)

	var steering := _steer(desired) if desired.length() > 0.01 else Vector3.ZERO

	# Face the enemy when fighting, the direction of travel otherwise.
	var facing := steering
	if _enemy != null and is_instance_valid(_enemy):
		facing = _enemy.global_position - global_position
		facing.y = 0.0
	if facing.length_squared() > 0.01:
		var wanted := atan2(facing.x, facing.z)
		rotation.y = lerp_angle(rotation.y, wanted, clampf(delta * TURN_RATE, 0.0, 1.0))

	velocity.x = steering.x * speed
	velocity.z = steering.z * speed
	move_and_slide()

	_update_animation(delta, speed)


func _update_animation(delta: float, speed: float) -> void:
	_hit_timer = maxf(0.0, _hit_timer - delta)
	if _hit_timer > 0.0:
		return
	if _current_clip == "fire" and _animation != null and _animation.is_playing():
		return

	var planar := Vector2(velocity.x, velocity.z).length()
	if planar < 0.35:
		_play("crouch_idle" if _state == State.COVER else ("aim" if _enemy != null else "idle"))
	elif speed >= RUN_SPEED - 0.01:
		_play("run")
	else:
		_play("walk")


func take_damage(amount: float, source: Node) -> void:
	if _dead:
		return
	health -= amount
	# Being shot from behind is how a soldier learns where the enemy is.
	if _enemy == null and source is Node3D and source.has_method("get_team") \
			and source.get_team() == enemy_team():
		_enemy = source
		_reaction = REACTION_TIME * 1.6

	if health <= 0.0:
		_dead = true
		velocity = Vector3.ZERO
		_play("death", true)
		var timer := get_tree().create_timer(9.0)
		timer.timeout.connect(queue_free)
	else:
		_hit_timer = 0.4
		_play("hit", true)

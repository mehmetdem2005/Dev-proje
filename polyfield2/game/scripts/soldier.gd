extends CharacterBody3D
## An AI soldier.
##
## Deliberately simple: pick a capture zone, walk to it, hold it, pick another.
## Its job in this build is to prove the rig — every animation clip exported
## from Blender is driven from here by actual movement state rather than being
## played back in a viewer.

const WALK_SPEED := 3.0
const RUN_SPEED := 5.6
const TURN_RATE := 4.0
const ARRIVAL_RADIUS := 4.0
const REPATH_INTERVAL := 6.0

@export var team: String = "legion"

var health: float = 100.0

var _target: Vector3 = Vector3.ZERO
var _repath_timer: float = 0.0
var _fire_timer: float = 0.0
var _dead: bool = false
var _hit_timer: float = 0.0

var _animation: AnimationPlayer = null
var _clips: PackedStringArray = PackedStringArray()
var _current_clip: String = ""


func get_team() -> String:
	return team


func _ready() -> void:
	add_to_group("soldiers")
	_build_visual()
	_pick_target()
	_fire_timer = randf_range(2.0, 8.0)


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
		queue.append_array(node.get_children())

	if _animation != null:
		_clips = _animation.get_animation_list()
		# Locomotion clips loop; one-shots (fire, hit, death) must not, or the
		# soldier dies forever in a twitching cycle.
		for clip: String in _clips:
			var animation := _animation.get_animation(clip)
			if animation == null:
				continue
			if clip in ["idle", "walk", "run", "crouch_idle", "crouch_walk", "aim"]:
				animation.loop_mode = Animation.LOOP_LINEAR
			else:
				animation.loop_mode = Animation.LOOP_NONE
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


func _pick_target() -> void:
	var zones := get_tree().get_nodes_in_group("capture_zones")
	if zones.is_empty():
		var level := get_tree().get_first_node_in_group("level")
		if level != null and level.has_method("spawn_points"):
			var points: Array = level.call("spawn_points", team)
			if not points.is_empty():
				_target = points[randi() % points.size()]
		return
	var zone: Node3D = zones[randi() % zones.size()]
	var angle := randf() * TAU
	var offset := Vector3(cos(angle), 0.0, sin(angle)) * randf_range(1.0, 7.0)
	_target = zone.global_position + offset
	_repath_timer = REPATH_INTERVAL


func _physics_process(delta: float) -> void:
	if _dead:
		if not is_on_floor():
			velocity += get_gravity() * delta
			move_and_slide()
		return

	if not is_on_floor():
		velocity += get_gravity() * delta

	var to_target := _target - global_position
	to_target.y = 0.0
	var distance := to_target.length()

	_repath_timer -= delta
	if distance < ARRIVAL_RADIUS or _repath_timer <= 0.0:
		_pick_target()
		to_target = _target - global_position
		to_target.y = 0.0
		distance = to_target.length()

	var speed := RUN_SPEED if distance > 18.0 else WALK_SPEED
	var direction := to_target.normalized()

	if direction.length_squared() > 0.01:
		var desired := atan2(direction.x, direction.z)
		rotation.y = lerp_angle(rotation.y, desired, clampf(delta * TURN_RATE, 0.0, 1.0))

	velocity.x = direction.x * speed
	velocity.z = direction.z * speed
	move_and_slide()

	_update_animation(delta, speed)


func _update_animation(delta: float, speed: float) -> void:
	_hit_timer = maxf(0.0, _hit_timer - delta)
	_fire_timer -= delta

	if _hit_timer > 0.0:
		return

	if _fire_timer <= 0.0:
		_fire_timer = randf_range(3.5, 11.0)
		_play("fire", true)
		_current_clip = ""       # let locomotion take over on the next frame
		return

	var planar := Vector2(velocity.x, velocity.z).length()
	if planar < 0.35:
		_play("idle")
	elif speed >= RUN_SPEED - 0.01:
		_play("run")
	else:
		_play("walk")


func take_damage(amount: float, _source: Node) -> void:
	if _dead:
		return
	health -= amount
	if health <= 0.0:
		_dead = true
		velocity = Vector3.ZERO
		_play("death", true)
		# Bodies stay a while, then clear so the map does not fill with corpses.
		var timer := get_tree().create_timer(9.0)
		timer.timeout.connect(queue_free)
	else:
		_hit_timer = 0.5
		_play("hit", true)

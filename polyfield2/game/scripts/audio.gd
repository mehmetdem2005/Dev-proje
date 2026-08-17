extends Node
## Sound playback.
##
## Two kinds of sound: 2D one-shots for the player's own weapon and UI, and
## positional 3D one-shots for anything happening in the world. Both come from
## a small pool of reusable players, because allocating an AudioStreamPlayer
## per gunshot in a firefight is a reliable way to stutter on a phone.

const AUDIO_DIR := "res://assets/audio/"
const POOL_2D := 6
const POOL_3D := 14

var _clips: Dictionary = {}
var _pool_2d: Array[AudioStreamPlayer] = []
var _pool_3d: Array[AudioStreamPlayer3D] = []
var _next_2d: int = 0
var _next_3d: int = 0
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.randomize()
	_load_clips()
	for index in POOL_2D:
		var player := AudioStreamPlayer.new()
		add_child(player)
		_pool_2d.append(player)
	for index in POOL_3D:
		var player := AudioStreamPlayer3D.new()
		player.max_distance = 120.0
		player.unit_size = 14.0
		player.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_SQUARE_DISTANCE
		add_child(player)
		_pool_3d.append(player)
	print("[Audio] %d clips, %d/%d voices" % [_clips.size(), POOL_2D, POOL_3D])


func _load_clips() -> void:
	var directory := DirAccess.open(AUDIO_DIR)
	if directory == null:
		push_warning("[Audio] no audio directory")
		return
	directory.list_dir_begin()
	var file := directory.get_next()
	while file != "":
		# Godot writes an .import sidecar next to each source file; the stream
		# is loaded by the source path, so skip the sidecars.
		if file.ends_with(".wav"):
			var stream := ResourceLoader.load(AUDIO_DIR + file) as AudioStream
			if stream != null:
				_clips[file.get_basename()] = stream
		file = directory.get_next()
	directory.list_dir_end()


func has(name: String) -> bool:
	return _clips.has(name)


## Non-positional: the player's own weapon, UI, hit markers.
func play(name: String, volume_db: float = 0.0, pitch_spread: float = 0.06) -> void:
	var stream: AudioStream = _clips.get(name, null)
	if stream == null:
		return
	var player := _pool_2d[_next_2d]
	_next_2d = (_next_2d + 1) % _pool_2d.size()
	player.stream = stream
	player.volume_db = volume_db
	player.pitch_scale = 1.0 + _rng.randfn(0.0, pitch_spread)
	player.play()


## Positional: everyone else's weapons, footsteps, impacts.
func play_at(name: String, position: Vector3, volume_db: float = 0.0,
		pitch_spread: float = 0.08) -> void:
	var stream: AudioStream = _clips.get(name, null)
	if stream == null:
		return
	var player := _pool_3d[_next_3d]
	_next_3d = (_next_3d + 1) % _pool_3d.size()
	player.stream = stream
	player.global_position = position
	player.volume_db = volume_db
	player.pitch_scale = 1.0 + _rng.randfn(0.0, pitch_spread)
	player.play()


func random_step() -> String:
	return "step_%d" % _rng.randi_range(0, 3)


## Looping ambience, parented to the listener so it never falls behind.
func start_ambience(parent: Node) -> void:
	var stream: AudioStream = _clips.get("wind", null)
	if stream == null or parent == null:
		return
	if stream is AudioStreamWAV:
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		stream.loop_end = stream.data.size() / 2
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = -12.0
	player.autoplay = true
	parent.add_child(player)
	player.play()

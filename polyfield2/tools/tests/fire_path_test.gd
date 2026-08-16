extends SceneTree
## Drives the touch fire path headlessly and asserts it actually shoots.
## Regression guard: the player used to resolve the HUD in _ready(), before the
## HUD had joined its group, which silently killed every touch input.
func _initialize() -> void:
	var packed: PackedScene = load("res://scenes/main.tscn")
	var main: Node = packed.instantiate()
	root.add_child(main)
	await process_frame
	await process_frame
	await process_frame

	var player := root.get_tree().get_first_node_in_group("players")
	var hud := root.get_tree().get_first_node_in_group("hud")
	if player == null or hud == null:
		print("SELFTEST FAIL: player=%s hud=%s" % [player, hud]); quit(1); return

	var weapon: Dictionary = player.get("_weapons")[player.get("_weapon_index")]
	var before: int = int(weapon["loaded"])

	# Press the fire button exactly as a finger would.
	var fire_button: Node = hud.get("_buttons")[0]
	fire_button.press(0)
	for i in 6:
		await physics_frame
	fire_button.release(0)
	await physics_frame

	var after: int = int(weapon["loaded"])
	print("SELFTEST ammo %d -> %d" % [before, after])
	if after < before:
		print("SELFTEST PASS: touch fire discharges the weapon")
		quit(0)
	else:
		print("SELFTEST FAIL: touch fire did nothing")
		quit(1)

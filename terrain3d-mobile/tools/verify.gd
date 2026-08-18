extends SceneTree
## Headless check that the mobile configuration actually takes effect.
##
##     godot --headless -s tools/verify.gd
##
## Exists because every number in the README is a claim about what Terrain3D
## does, and Terrain3D is a compiled extension that can change under us. This
## asserts the claims against the running extension rather than against the
## source I read.

const MobileConfig := preload("res://mobile/terrain3d_mobile.gd")

var _failures := 0


func _check(label: String, actual: Variant, expected: Variant) -> void:
	if actual == expected:
		print("  ok    %-34s %s" % [label, actual])
	else:
		print("  FAIL  %-34s %s (expected %s)" % [label, actual, expected])
		_failures += 1


func _initialize() -> void:
	print("=== Terrain3D mobile configuration ===")

	if not ClassDB.class_exists("Terrain3D"):
		print("FAIL: Terrain3D extension not loaded")
		quit(1)
		return

	# Arithmetic, independent of the extension.
	print("[clipmap maths]")
	_check("stock instances (7 LODs)", MobileConfig.instance_count(7), 144)
	_check("stock coverage m", int(MobileConfig.coverage_m(48, 7, 1.0)), 12288)
	_check("1 LOD instances", MobileConfig.instance_count(1), 24)
	_check("3 LOD instances", MobileConfig.instance_count(3), 64)

	# Against the real extension.
	for tier: int in [MobileConfig.Tier.LOW, MobileConfig.Tier.MEDIUM,
			MobileConfig.Tier.HIGH]:
		var terrain: Object = ClassDB.instantiate("Terrain3D")
		if terrain.get("assets") == null and ClassDB.class_exists("Terrain3DAssets"):
			terrain.set("assets", ClassDB.instantiate("Terrain3DAssets"))
		root.add_child(terrain)

		var report: Dictionary = MobileConfig.configure(terrain, 512.0, tier)
		print("[%s]" % report["tier"])
		_check("mesh_lods applied", terrain.get("mesh_lods"), report["mesh_lods"])
		_check("mesh_size applied", terrain.get("mesh_size"), report["mesh_size"])
		_check("vertex_spacing applied",
			snappedf(terrain.get("vertex_spacing"), 0.01),
			snappedf(report["vertex_spacing"], 0.01))
		# The one that stops the world looking infinite.
		_check("world_background NONE",
			terrain.get("material").get("world_background"), 0)
		_check("auto_shader off", terrain.get("material").get("auto_shader"), false)
		_check("dual_scaling off", terrain.get("material").get("dual_scaling"), false)
		_check("instances bounded",
			MobileConfig.instance_count(terrain.get("mesh_lods")) <= 84, true)
		print("  ->    %d MeshInstances, reaches %.0f m" % [
			report["mesh_instances"], report["coverage_m"]])

		terrain.queue_free()

	if _failures == 0:
		print("\nVERIFY PASS")
		quit(0)
	else:
		print("\nVERIFY FAIL (%d)" % _failures)
		quit(1)

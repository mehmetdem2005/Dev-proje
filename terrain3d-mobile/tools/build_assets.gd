extends SceneTree
## Build terrain3d_assets.tres from textures/SOURCES.json.
##
##     godot --headless -s tools/build_assets.gd
##
## Written in-engine rather than as a hand-authored .tres because the resource
## holds 32 sub-resources each referencing two imported textures by UID. Hand
## writing that is a reliable way to produce a file that loads with silent
## nulls; ResourceSaver gets the references right by construction.

const SOURCES := "res://textures/SOURCES.json"
const OUT := "res://terrain3d_assets.tres"

## Metres one texture tile covers, per category. A rock face wants a much
## larger tile than grass or the pattern reads as gravel; getting this wrong is
## the most common reason a Terrain3D scene looks like plastic.
const UV_SCALE := {
	"grass": 0.10,
	"soil": 0.09,
	"sand": 0.07,
	"gravel": 0.08,
	"rock": 0.05,
	"snow": 0.08,
}

## Roughness offset per category, added to the texture's own roughness.
const ROUGHNESS := {
	"grass": 0.0,
	"soil": 0.0,
	"sand": 0.05,
	"gravel": 0.0,
	"rock": -0.05,
	"snow": -0.15,
}


func _initialize() -> void:
	if not ClassDB.class_exists("Terrain3DAssets"):
		print("FAIL: Terrain3D extension not loaded")
		quit(1)
		return

	var file := FileAccess.open(SOURCES, FileAccess.READ)
	if file == null:
		print("FAIL: %s missing — run tools/fetch_textures.py first" % SOURCES)
		quit(1)
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		print("FAIL: SOURCES.json unreadable")
		quit(1)
		return

	var entries: Array = parsed.get("textures", [])
	var assets: Object = ClassDB.instantiate("Terrain3DAssets")
	var added := 0

	for entry: Dictionary in entries:
		var name: String = str(entry["name"])
		var category: String = str(entry.get("category", "soil"))
		var albedo_path := "res://textures/%s_alb_ht.png" % name
		var normal_path := "res://textures/%s_nrm_rg.png" % name

		if not ResourceLoader.exists(albedo_path) or not ResourceLoader.exists(normal_path):
			print("  skip %s — textures missing" % name)
			continue

		var asset: Object = ClassDB.instantiate("Terrain3DTextureAsset")
		asset.set("name", name)
		asset.set("id", added)
		asset.set("albedo_texture", load(albedo_path))
		asset.set("normal_texture", load(normal_path))
		asset.set("uv_scale", UV_SCALE.get(category, 0.08))
		asset.set("roughness", ROUGHNESS.get(category, 0.0))
		# Detiling breaks up the repeat by rotating and shifting the tile per
		# region. It costs nothing extra to sample and is the cheapest fix for
		# the grid pattern that makes tiled terrain look like tiled terrain.
		asset.set("detiling_rotation", 0.25)
		asset.set("detiling_shift", 0.15)

		assets.call("set_texture", added, asset)
		added += 1

	var error := ResourceSaver.save(assets, OUT)
	if error != OK:
		print("FAIL: could not save %s (error %d)" % [OUT, error])
		quit(1)
		return

	print("wrote %s with %d textures" % [OUT, added])
	quit(0)

extends Node
## Binds material names carried by the GLBs to real ORMMaterial3D resources.
##
## The Blender exporter writes geometry and material *names* only — textures
## are deliberately left out of the GLBs so the thirteen shared map sets are
## not copied into every asset file. This autoload rebuilds the materials once
## at startup and hands them out by name.

const TEXTURE_DIR := "res://assets/textures/"

## Material name -> tiling in metres per texture repeat. The GLBs carry
## world-scale box-projected UVs, so this is a per-material trim, not a
## coordinate system.
const MATERIALS := {
	"rock_granite": 1.0,
	"cliff_strata": 1.0,
	"ground_rocky": 1.0,
	"grass_highland": 1.0,
	"soil_trench": 1.0,
	"sandbag_burlap": 1.0,
	"wood_plank": 1.0,
	"metal_corrugated": 1.0,
	"concrete_bunker": 1.0,
	"crate_wood": 1.0,
	"uniform_ranger": 1.0,
	"uniform_legion": 1.0,
	"gunmetal": 1.0,
	"skin": 1.0,
	"gear_leather": 1.0,
	"bark": 1.0,
	"moss_rock": 1.0,
	"sand_dry": 1.0,
}

## Alpha-cut foliage. Kept out of MATERIALS because it is not an opaque
## ORMMaterial3D: cards need scissor transparency and no backface culling, or
## every leaf disappears from one side.
const CUTOUT := ["leaf"]

var _cache: Dictionary = {}
var _terrain_material: ShaderMaterial


func _ready() -> void:
	for name: String in MATERIALS:
		var material := _build(name)
		if material != null:
			_cache[name] = material
	for name: String in CUTOUT:
		var material := _build_cutout(name)
		if material != null:
			_cache[name] = material
	print("[MaterialLibrary] built %d materials" % _cache.size())


func _load_texture(name: String, suffix: String, srgb: bool) -> Texture2D:
	var path := "%s%s_%s.png" % [TEXTURE_DIR, name, suffix]
	if not ResourceLoader.exists(path):
		push_warning("[MaterialLibrary] missing texture: %s" % path)
		return null
	var texture := ResourceLoader.load(path) as Texture2D
	if texture == null:
		push_warning("[MaterialLibrary] failed to load: %s" % path)
	return texture


func _build(name: String) -> ORMMaterial3D:
	var albedo := _load_texture(name, "albedo", true)
	if albedo == null:
		return null

	# ORMMaterial3D is the reason the texture generator packs AO/roughness/
	# metallic into one image: it samples all three from a single fetch, which
	# on the Mobile renderer is worth more than any amount of map authoring.
	var material := ORMMaterial3D.new()
	material.resource_name = name
	material.albedo_texture = albedo
	material.orm_texture = _load_texture(name, "orm", false)

	var normal := _load_texture(name, "normal", false)
	if normal != null:
		material.normal_enabled = true
		material.normal_texture = normal
		material.normal_scale = 1.0

	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.texture_repeat = true
	material.specular_mode = BaseMaterial3D.SPECULAR_SCHLICK_GGX
	return material


func _build_cutout(name: String) -> StandardMaterial3D:
	var albedo := _load_texture(name, "albedo", true)
	if albedo == null:
		return null

	var material := StandardMaterial3D.new()
	material.resource_name = name
	material.albedo_texture = albedo
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	material.alpha_scissor_threshold = 0.5
	# Alpha-scissor still needs alpha-to-coverage off on mobile to stay cheap.
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
	material.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	material.roughness = 0.9
	# Foliage lit from both sides reads as translucent leaves rather than
	# black cards whenever the sun is behind them.
	material.backlight_enabled = true
	material.backlight = Color(0.16, 0.22, 0.10)

	var orm := _load_texture(name, "orm", false)
	if orm != null:
		material.ao_enabled = true
		material.ao_texture = orm
		material.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		material.roughness_texture = orm
		material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return material


func get_material(name: String) -> Material:
	return _cache.get(name, null)


func terrain_material() -> ShaderMaterial:
	if _terrain_material != null:
		return _terrain_material

	var shader := ResourceLoader.load("res://shaders/terrain_splat.gdshader") as Shader
	if shader == null:
		push_error("[MaterialLibrary] terrain shader missing")
		return null

	_terrain_material = ShaderMaterial.new()
	_terrain_material.shader = shader
	var layers := {"rock": "rock_granite", "grass": "grass_highland", "gravel": "ground_rocky"}
	for slot: String in layers:
		var source: String = layers[slot]
		_terrain_material.set_shader_parameter("%s_albedo" % slot, _load_texture(source, "albedo", true))
		_terrain_material.set_shader_parameter("%s_normal" % slot, _load_texture(source, "normal", false))
		_terrain_material.set_shader_parameter("%s_orm" % slot, _load_texture(source, "orm", false))
	# The macro breakup layer is sampled at map scale by every terrain pixel;
	# a different material from the three blend layers is what stops it from
	# reinforcing their own tiling period.
	_terrain_material.set_shader_parameter("macro_variation",
		_load_texture("moss_rock", "albedo", true))
	_terrain_material.set_shader_parameter("uv_scale", 1.0)
	return _terrain_material


## Swap every surface of an imported mesh for the library material whose name
## matches the one baked into the GLB.
func apply_to(instance: MeshInstance3D) -> void:
	var mesh := instance.mesh
	if mesh == null:
		return
	for surface in range(mesh.get_surface_count()):
		var source := mesh.surface_get_material(surface)
		if source == null:
			continue
		var replacement := get_material(source.resource_name)
		if replacement != null:
			instance.set_surface_override_material(surface, replacement)

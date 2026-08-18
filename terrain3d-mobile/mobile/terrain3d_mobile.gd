@tool
extends Node
class_name Terrain3DMobile
## Bounds and minimises a Terrain3D node for phones.
##
## Terrain3D ships tuned for desktop open worlds. Out of the box it builds a
## clipmap of 7 LODs — 144 MeshInstances — spanning about 12 km, and fills
## everything outside your data with procedural noise so the world looks
## infinite. On a phone that is the wrong shape of terrain in three separate
## ways, and this node fixes all three:
##
##   1. The clipmap is sized to a world you declare, not to the horizon.
##   2. The instance count follows from that and is reported, not guessed.
##   3. The background is switched off, so terrain exists only where your
##      regions are and the map has a real edge.
##
## Attach this as a child of a Terrain3D node (or set `terrain_path`), pick a
## `world_size_m` and a `tier`, and tick `apply`. It prints exactly what it did.
##
##     Terrain3D
##       └─ Terrain3DMobile   world_size_m = 512, tier = MEDIUM
##
## From code:
##
##     Terrain3DMobile.configure($Terrain3D, 512.0, Terrain3DMobile.Tier.MEDIUM)

## How hard the terrain is allowed to work. Each tier moves vertex density,
## LOD budget, shadows and the shader's optional passes together — they are the
## things that actually cost frames, and moving one without the others just
## shifts the bottleneck.
enum Tier {
	LOW,     ## Cheapest. No terrain shadows, flat normals, coarsest vertices.
	MEDIUM,  ## Default for mid-range phones.
	HIGH,    ## Flagship phones / tablets.
}

## Terrain3D's own enums, restated so this script does not need the extension
## loaded to be parsed by the editor.
const BACKGROUND_NONE := 0
const BACKGROUND_FLAT := 1
const BACKGROUND_NOISE := 2

const FILTER_LINEAR := 0

const SHADOWS_OFF := 0
const SHADOWS_ON := 1

const GI_DISABLED := 0

const COLLISION_DISABLED := 0
const COLLISION_DYNAMIC_GAME := 1

## Pre-generated mobile shader. Terrain3D assembles its shader from the enabled
## features at runtime; this is that output for the mobile feature set, with the
## anisotropic samplers swapped for plain trilinear. Terrain3D has no
## non-anisotropic path of its own — both of its `texture_filtering` options are
## anisotropic — so the only way to get it is an override.
##
## It is baked against world_background NONE, auto_shader off and dual_scaling
## off. Turn any of those back on and this shader will not reflect it:
## regenerate with tools/dump_shader.tscn or set `use_mobile_shader = false`.
const MOBILE_SHADER := "res://mobile/terrain3d_mobile.gdshader"

## Per-tier settings. `mesh_size` is quads per clipmap tile and `spacing` is
## metres per vertex, so the two together set both the vertex density and how
## far a given number of LODs reaches.
const TIERS := {
	Tier.LOW: {
		"mesh_size": 16,
		"spacing": 2.0,
		"max_lods": 3,
		"shadows": false,
		"flat_normals": true,
		"projection": false,
		"macro_variation": false,
		"collision_shape_size": 32,
		"bias_distance": 96.0,
	},
	Tier.MEDIUM: {
		"mesh_size": 24,
		"spacing": 1.5,
		"max_lods": 4,
		"shadows": false,
		"flat_normals": false,
		"projection": false,
		"macro_variation": false,
		"collision_shape_size": 24,
		"bias_distance": 160.0,
	},
	Tier.HIGH: {
		"mesh_size": 32,
		"spacing": 1.0,
		"max_lods": 5,
		"shadows": true,
		"flat_normals": false,
		"projection": true,
		"macro_variation": true,
		"collision_shape_size": 16,
		"bias_distance": 320.0,
	},
}

@export_node_path("Node3D") var terrain_path: NodePath
## The world you actually want, in metres across. The clipmap is sized to cover
## this and no more — that is the whole point of the node.
@export_range(64.0, 8192.0, 16.0) var world_size_m: float = 512.0
@export var tier: Tier = Tier.MEDIUM
## Terrain collision costs CPU on every shape rebuild as the player moves.
## Leave on unless you drive the player height from the heightmap yourself.
@export var collision_enabled: bool = true
## Replace Terrain3D's generated shader with the trilinear mobile build.
@export var use_mobile_shader: bool = true
## Tick to apply. Untick happens automatically; it is a button, not a state.
@export var apply: bool = false:
	set(value):
		if value:
			apply_to_target()
## Apply once on _ready in a running game, so an exported scene does not depend
## on the values having been baked in the editor.
@export var apply_on_ready: bool = true


func _ready() -> void:
	if apply_on_ready and not Engine.is_editor_hint():
		apply_to_target()


func apply_to_target() -> Dictionary:
	var terrain := _find_terrain()
	if terrain == null:
		push_warning("[Terrain3DMobile] no Terrain3D found — set terrain_path or " +
			"make this a child of one")
		return {}
	var report := configure(terrain, world_size_m, tier, collision_enabled,
		use_mobile_shader)
	print(format_report(report))
	return report


func _find_terrain() -> Node:
	if not terrain_path.is_empty():
		var explicit := get_node_or_null(terrain_path)
		if explicit != null and explicit.get_class() == "Terrain3D":
			return explicit
	var parent := get_parent()
	if parent != null and parent.get_class() == "Terrain3D":
		return parent
	return null


## How wide the clipmap reaches, in metres, for a given configuration.
##
## LOD0 lays a 4x4 grid of `mesh_size`-quad tiles, so it spans 4*mesh_size
## quads; every LOD above it doubles the scale. The outermost ring therefore
## reaches 4 * mesh_size * 2^(lods-1) vertices, times the metres per vertex.
static func coverage_m(mesh_size: int, lods: int, spacing: float) -> float:
	return 4.0 * float(mesh_size) * pow(2.0, float(lods - 1)) * spacing


## MeshInstances the clipmap creates. Straight from Terrain3DMesher: LOD0 gets
## 16 tiles + 2 + 2 edges + 2 + 2 trims = 24, and every LOD above it gets
## 12 tiles + 2 + 2 edges + 2 + 2 fills = 20.
static func instance_count(lods: int) -> int:
	return 24 + 20 * maxi(lods - 1, 0)


## Fewest LODs that still cover `world_size_m`, capped by the tier's budget.
static func lods_for(world_size: float, mesh_size: int, spacing: float,
		max_lods: int) -> int:
	var lods := 1
	while lods < max_lods and coverage_m(mesh_size, lods, spacing) < world_size:
		lods += 1
	return lods


## Configure a Terrain3D node. Returns a report describing what it now is.
static func configure(terrain: Node, world_size: float, quality: Tier,
		collision: bool = true, mobile_shader: bool = true) -> Dictionary:
	if terrain == null or terrain.get_class() != "Terrain3D":
		push_error("[Terrain3DMobile] configure() needs a Terrain3D node")
		return {}

	var settings: Dictionary = TIERS[quality]
	var mesh_size: int = settings["mesh_size"]
	var spacing: float = settings["spacing"]
	var lods := lods_for(world_size, mesh_size, spacing, settings["max_lods"])

	# --- the clipmap -------------------------------------------------------
	terrain.set("mesh_size", mesh_size)
	terrain.set("vertex_spacing", spacing)
	terrain.set("mesh_lods", lods)

	# Terrain shadows are a second full pass over a surface that fills the
	# screen. On a phone that is rarely worth it; the objects standing on the
	# terrain still cast onto it either way.
	terrain.set("cast_shadows", SHADOWS_ON if settings["shadows"] else SHADOWS_OFF)
	terrain.set("gi_mode", GI_DISABLED)

	terrain.set("collision_mode",
		COLLISION_DYNAMIC_GAME if collision else COLLISION_DISABLED)
	if collision:
		# Dynamic collision rebuilds shapes around the player as they move.
		# Bigger shapes mean fewer, cheaper rebuilds at the cost of memory.
		terrain.set("collision_shape_size", settings["collision_shape_size"])

	# --- the material ------------------------------------------------------
	var material: Object = terrain.get("material")
	if material != null:
		# THE setting for "stop looking infinite". NOISE fills everything
		# outside your regions with procedural terrain to the horizon, and it
		# compiles a whole extra block of noise into the fragment shader.
		# NONE draws nothing outside your regions, so the map has a real edge.
		material.set("world_background", BACKGROUND_NONE)
		material.set("texture_filtering", FILTER_LINEAR)

		# Both of these multiply texture fetches per pixel over a surface that
		# covers most of the screen, and both are compiled out when off.
		material.set("auto_shader", false)
		material.set("dual_scaling", false)

		if material.has_method("set_shader_param"):
			# Triplanar projection on steep ground triples the fetches there.
			material.call("set_shader_param", "enable_projection",
				settings["projection"])
			# Two extra noise lookups per pixel for large-scale colour drift.
			material.call("set_shader_param", "enable_macro_variation",
				settings["macro_variation"])
			# Flat normals skip the normal reconstruction entirely.
			material.call("set_shader_param", "flat_terrain_normals",
				settings["flat_normals"])
			# Depth blur is a dependent texture read. Never on a phone.
			material.call("set_shader_param", "depth_blur", 0.0)
			# Pull mips in earlier: cheaper sampling, less shimmer at distance.
			material.call("set_shader_param", "mipmap_bias", 1.1)
			# Past this distance the shader biases harder towards small mips.
			# Terrain3D's default is 512 m, which is beyond the entire world on
			# a bounded map — so it never kicked in and distant ground kept
			# sampling large mips it could not resolve.
			material.call("set_shader_param", "bias_distance",
				settings["bias_distance"])

	var shader_applied := false
	if mobile_shader and material != null and ResourceLoader.exists(MOBILE_SHADER):
		var shader: Shader = ResourceLoader.load(MOBILE_SHADER) as Shader
		if shader != null:
			material.set("shader_override", shader)
			if material.has_method("enable_shader_override"):
				material.call("enable_shader_override", true)
			shader_applied = true

	# Terrain3D follows a camera to snap the clipmap. Without one it prints an
	# error from _physics_process and stops processing, so the terrain simply
	# never moves with the player — easy to miss, since it still renders.
	# In 1.0.2 this is a method, not a property: there is no `clipmap_target`
	# until 1.1.
	if terrain.has_method("get_camera") and terrain.call("get_camera") == null:
		push_warning("[Terrain3DMobile] no camera set. Call " +
			"Terrain3D.set_camera(your_camera) or the terrain will not follow " +
			"the player.")

	return {
		"tier": Tier.keys()[quality],
		"requested_size_m": world_size,
		"mesh_size": mesh_size,
		"vertex_spacing": spacing,
		"mesh_lods": lods,
		"max_lods": settings["max_lods"],
		"coverage_m": coverage_m(mesh_size, lods, spacing),
		"mesh_instances": instance_count(lods),
		"default_instances": instance_count(7),
		"default_coverage_m": coverage_m(48, 7, 1.0),
		"shadows": settings["shadows"],
		"collision": collision,
		"world_background": "NONE",
		"mobile_shader": shader_applied,
	}


static func format_report(report: Dictionary) -> String:
	if report.is_empty():
		return "[Terrain3DMobile] nothing configured"
	var lines := PackedStringArray()
	lines.append("[Terrain3DMobile] tier %s" % report["tier"])
	lines.append("  clipmap      %d LODs x %d quads @ %.2f m/vertex" % [
		report["mesh_lods"], report["mesh_size"], report["vertex_spacing"]])
	lines.append("  MeshInstances %d   (stock Terrain3D: %d)" % [
		report["mesh_instances"], report["default_instances"]])
	lines.append("  reaches      %.0f m   (asked for %.0f m, stock reaches %.0f m)" % [
		report["coverage_m"], report["requested_size_m"], report["default_coverage_m"]])
	lines.append("  background   %s — terrain stops at your regions" %
		report["world_background"])
	lines.append("  shadows      %s   collision %s" % [
		"on" if report["shadows"] else "off",
		"on" if report["collision"] else "off"])
	lines.append("  shader       %s" % ("mobile override (trilinear samplers)"
		if report.get("mobile_shader", false) else "Terrain3D stock (anisotropic)"))
	if report["coverage_m"] < report["requested_size_m"]:
		lines.append("  NOTE: capped at %d LODs by the tier budget, so it reaches" %
			report["max_lods"])
		lines.append("        less than you asked. Raise vertex_spacing or the tier.")
	return "\n".join(lines)

shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert, specular_schlick_ggx;

// Three-layer terrain blend driven by the vertex colour mask baked in Blender:
// R = rock, G = grass, B = gravel. Nine samplers is the price of the blend;
// everything else in this shader is kept deliberately cheap for the Mobile
// renderer — Lambert diffuse, no parallax, no triplanar branch.

uniform sampler2D rock_albedo : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D rock_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D rock_orm : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform sampler2D grass_albedo : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_orm : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform sampler2D gravel_albedo : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D gravel_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D gravel_orm : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform float uv_scale = 1.0;
uniform float macro_scale = 0.07;
uniform float macro_strength : hint_range(0.0, 1.0) = 0.16;
uniform float normal_strength : hint_range(0.0, 2.0) = 0.7;

varying vec3 splat;

void vertex() {
	splat = COLOR.rgb;
}

void fragment() {
	vec2 uv = UV * uv_scale;

	// Normalise so the three weights always resolve even if the baked mask
	// drifted slightly during vertex-colour quantisation to 8 bits.
	vec3 w = splat / max(splat.r + splat.g + splat.b, 0.001);

	vec3 albedo =
		texture(rock_albedo, uv).rgb * w.r +
		texture(grass_albedo, uv).rgb * w.g +
		texture(gravel_albedo, uv).rgb * w.b;

	vec3 orm =
		texture(rock_orm, uv).rgb * w.r +
		texture(grass_orm, uv).rgb * w.g +
		texture(gravel_orm, uv).rgb * w.b;

	vec3 nrm =
		texture(rock_normal, uv).rgb * w.r +
		texture(grass_normal, uv).rgb * w.g +
		texture(gravel_normal, uv).rgb * w.b;

	// A second, much larger sample of the dominant layer breaks the visible
	// repeat of a 6 m tile across a 192 m map. One extra fetch, big payoff.
	vec3 macro = texture(gravel_albedo, uv * macro_scale).rgb;
	albedo = mix(albedo, albedo * (macro * 1.6), macro_strength);

	ALBEDO = albedo;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.85;
	ROUGHNESS = clamp(orm.g, 0.05, 1.0);
	METALLIC = orm.b;
	NORMAL_MAP = nrm;
	NORMAL_MAP_DEPTH = normal_strength;
}

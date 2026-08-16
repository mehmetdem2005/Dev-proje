shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert, specular_schlick_ggx;

// Three-layer terrain blend driven by the vertex-colour mask baked in Blender:
// R = rock, G = grass, B = gravel.
//
// The naive version of this sampled all three layers unconditionally — nine
// texture fetches per pixel over a surface that fills most of the screen, which
// is what made the first build stutter on a phone. Almost every texel on the
// map is dominated by one or two layers, so this version:
//
//   * skips any layer whose weight is below CUTOFF entirely,
//   * skips the normal fetch for layers contributing less than NORMAL_CUTOFF,
//   * drops to albedo-only past FAR_DISTANCE, where normals and ORM detail are
//     smaller than a pixel anyway.
//
// Typical cost is now 3-5 fetches near the camera and 1-2 in the distance,
// with no visible change to the material at playable ranges.

uniform sampler2D rock_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_orm : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform sampler2D grass_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_orm : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform sampler2D gravel_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D gravel_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D gravel_orm : hint_default_white, filter_linear_mipmap, repeat_enable;

// Large-scale colour variation, sampled once and reused by every layer. This is
// what kills the "same 3 m tile forever" look without a second full material.
uniform sampler2D macro_variation : source_color, filter_linear_mipmap, repeat_enable;

uniform float uv_scale = 1.0;
uniform float detail_scale = 5.7;          // second, prime-ish tiling rate
uniform float macro_scale = 0.055;
uniform float macro_strength : hint_range(0.0, 1.0) = 0.45;
uniform float detail_strength : hint_range(0.0, 1.0) = 0.35;
uniform float normal_strength : hint_range(0.0, 2.0) = 0.9;
uniform float far_distance = 70.0;
uniform float far_fade = 25.0;

const float CUTOFF = 0.02;
const float NORMAL_CUTOFF = 0.15;

varying vec3 splat;
varying float view_distance;

void vertex() {
	splat = COLOR.rgb;
	view_distance = length((MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).xyz);
}

void fragment() {
	vec2 uv = UV * uv_scale;

	vec3 w = splat / max(splat.r + splat.g + splat.b, 0.001);

	// 0 near the camera, 1 far away. Past this the extra maps are invisible.
	float far = clamp((view_distance - far_distance) / far_fade, 0.0, 1.0);

	vec3 albedo = vec3(0.0);
	vec3 orm = vec3(0.0);
	vec3 nrm = vec3(0.0);
	float normal_weight = 0.0;

	if (w.r > CUTOFF) {
		albedo += texture(rock_albedo, uv).rgb * w.r;
		orm += texture(rock_orm, uv).rgb * w.r;
		if (w.r > NORMAL_CUTOFF && far < 1.0) {
			nrm += texture(rock_normal, uv).rgb * w.r;
			normal_weight += w.r;
		}
	}
	if (w.g > CUTOFF) {
		albedo += texture(grass_albedo, uv).rgb * w.g;
		orm += texture(grass_orm, uv).rgb * w.g;
		if (w.g > NORMAL_CUTOFF && far < 1.0) {
			nrm += texture(grass_normal, uv).rgb * w.g;
			normal_weight += w.g;
		}
	}
	if (w.b > CUTOFF) {
		albedo += texture(gravel_albedo, uv).rgb * w.b;
		orm += texture(gravel_orm, uv).rgb * w.b;
		if (w.b > NORMAL_CUTOFF && far < 1.0) {
			nrm += texture(gravel_normal, uv).rgb * w.b;
			normal_weight += w.b;
		}
	}

	// Detail pass: the dominant layer resampled at a different, non-harmonic
	// rate. Two tiling rates that do not share a period take far longer to
	// visibly repeat than one, for a single extra fetch.
	if (far < 1.0) {
		vec3 detail;
		if (w.r >= w.g && w.r >= w.b) {
			detail = texture(rock_albedo, uv * detail_scale).rgb;
		} else if (w.g >= w.b) {
			detail = texture(grass_albedo, uv * detail_scale).rgb;
		} else {
			detail = texture(gravel_albedo, uv * detail_scale).rgb;
		}
		float amount = detail_strength * (1.0 - far);
		albedo = mix(albedo, albedo * (detail * 2.0), amount);
	}

	// Macro breakup at map scale, always on: it is one fetch and it is the
	// single biggest reason the ground stops looking tiled.
	vec3 macro = texture(macro_variation, uv * macro_scale).rgb;
	albedo = mix(albedo, albedo * (macro * 1.9), macro_strength);

	ALBEDO = albedo;
	AO = mix(orm.r, 1.0, far);
	AO_LIGHT_AFFECT = 0.8;
	ROUGHNESS = clamp(orm.g, 0.06, 1.0);
	METALLIC = orm.b;

	if (normal_weight > 0.001) {
		NORMAL_MAP = nrm / normal_weight;
		NORMAL_MAP_DEPTH = normal_strength * (1.0 - far);
	}
}

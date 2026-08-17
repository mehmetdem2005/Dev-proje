#!/usr/bin/env bash
# Rebuild every Polyfield 2 asset from source, then re-import the Godot project.
#
#   tools/build_all.sh [--size 512] [--skip-textures] [--skip-import]
#
# Everything is deterministic: the same seeds produce the same meshes and the
# same maps, so a rebuild is safe to run at any time.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

BLENDER="${BLENDER:-/opt/blender/blender}"
GODOT="${GODOT:-/opt/godot/Godot_v4.6.3-stable_linux.x86_64}"

TEXTURE_SIZE=512
SKIP_TEXTURES=0
SKIP_IMPORT=0

while [[ $# -gt 0 ]]; do
	case "$1" in
		--size) TEXTURE_SIZE="$2"; shift 2 ;;
		--skip-textures) SKIP_TEXTURES=1; shift ;;
		--skip-import) SKIP_IMPORT=1; shift ;;
		*) echo "unknown option: $1" >&2; exit 2 ;;
	esac
done

if [[ ! -x "$BLENDER" ]]; then
	echo "Blender not found at $BLENDER (set BLENDER=...)" >&2
	exit 1
fi

run_blender() {
	# Blender resolves --python relative to its own cwd, so scripts are always
	# invoked from the directory they live in.
	local script="$1"; shift
	local dir; dir="$(dirname "$script")"
	( cd "$dir" && "$BLENDER" -b --python "$(basename "$script")" "$@" ) \
		| grep -vE '^(Blender |Read prefs|found bundled)|INFO:|WARNING:|^$' || true
}

echo "=== Polyfield 2 asset build ==="

if [[ "$SKIP_TEXTURES" -eq 0 ]]; then
	echo "--- textures (${TEXTURE_SIZE}px) ---"
	# Run under Blender's Python: it ships numpy, the system Python here may not.
	( cd "$ROOT/tools/texgen" && "$BLENDER" -b --python-expr "
import sys, os, runpy
sys.path.insert(0, os.getcwd())
sys.argv = ['build_textures.py', '--size', '${TEXTURE_SIZE}']
runpy.run_path('build_textures.py', run_name='__main__')
" ) | grep -vE '^(Blender |Read prefs|found bundled)|^$' || true

	# The one map that stays procedural: the CC0 libraries ship tiling surfaces,
	# not alpha-masked foliage. gen_trees.py reads its row layout, so the two
	# have to be rebuilt together.
	echo "--- foliage atlas ---"
	run_blender "$ROOT/tools/texgen/leaf_atlas.py"
fi

echo "--- terrain and layout ---"
run_blender "$ROOT/tools/blender/gen_terrain.py"

echo "--- rocks ---"
run_blender "$ROOT/tools/blender/gen_rocks.py"

echo "--- fortifications ---"
run_blender "$ROOT/tools/blender/gen_fortifications.py"

echo "--- props ---"
run_blender "$ROOT/tools/blender/gen_props.py"

echo "--- buildings ---"
run_blender "$ROOT/tools/blender/gen_buildings.py"

echo "--- vegetation ---"
run_blender "$ROOT/tools/blender/gen_trees.py"

echo "--- weapons ---"
run_blender "$ROOT/tools/blender/gen_weapons.py"

echo "--- first-person viewmodel ---"
run_blender "$ROOT/tools/blender/gen_viewmodel.py"

echo "--- soldiers ---"
run_blender "$ROOT/tools/blender/gen_character.py"

if [[ "$SKIP_IMPORT" -eq 0 && -x "$GODOT" ]]; then
	echo "--- godot import ---"
	( cd "$ROOT/game" && "$GODOT" --headless --import ) >/dev/null 2>&1
	echo "  imported"
fi

echo
echo "=== done ==="
du -sh "$ROOT/game/assets"/* 2>/dev/null || true

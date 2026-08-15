#!/usr/bin/env bash
# Export the Android APK.
#
#   tools/export_apk.sh [--release] [--out PATH]
#
# Uses Godot's prebuilt Android template (no Gradle), so the only Android
# toolchain pieces needed are apksigner and zipalign from build-tools.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

GODOT="${GODOT:-/opt/godot/Godot_v4.6.3-stable_linux.x86_64}"
ANDROID_SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/android-sdk}}"
KEYSTORE="${GODOT_ANDROID_KEYSTORE:-$HOME/debug.keystore}"

MODE="debug"
OUT=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--release) MODE="release"; shift ;;
		--out) OUT="$2"; shift 2 ;;
		*) echo "unknown option: $1" >&2; exit 2 ;;
	esac
done

[[ -n "$OUT" ]] || OUT="$ROOT/build/polyfield2-ridgeline${MODE:+-$MODE}.apk"
[[ "$MODE" == "debug" ]] && OUT="${OUT/-debug/}"

# --- preflight ------------------------------------------------------------
fail() { echo "error: $*" >&2; exit 1; }

[[ -x "$GODOT" ]] || fail "Godot not found at $GODOT (set GODOT=...)"

TEMPLATES="$HOME/.local/share/godot/export_templates/4.6.3.stable"
[[ -f "$TEMPLATES/android_${MODE}.apk" ]] \
	|| fail "missing export template $TEMPLATES/android_${MODE}.apk
  download: https://downloads.godotengine.org/?version=4.6.3&flavor=stable&slug=export_templates.tpz&platform=templates"

[[ -d "$ANDROID_SDK/build-tools" ]] \
	|| fail "Android build-tools not found under $ANDROID_SDK
  install: sdkmanager --sdk_root=\$ANDROID_SDK 'build-tools;35.0.0' 'platforms;android-35' platform-tools"

[[ -f "$KEYSTORE" ]] || fail "keystore not found at $KEYSTORE
  create: keytool -keyalg RSA -genkeypair -alias androiddebugkey -keypass android \\
            -keystore $KEYSTORE -storepass android \\
            -dname 'CN=Android Debug,O=Android,C=US' -validity 9999 -deststoretype pkcs12"

# Godot reads the SDK and keystore paths from editor settings, not the project.
SETTINGS="$HOME/.config/godot/editor_settings-4.6.tres"
if [[ -f "$SETTINGS" ]] && ! grep -q "android_sdk_path = \"$ANDROID_SDK\"" "$SETTINGS"; then
	echo "warning: $SETTINGS does not point at $ANDROID_SDK — export may fail" >&2
fi

mkdir -p "$(dirname "$OUT")"

echo "=== exporting $MODE APK ==="
( cd "$ROOT/game" \
	&& GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD="${GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD:-android}" \
	   "$GODOT" --headless "--export-$MODE" "Android" "$OUT" ) \
	| grep -E "DONE|ERROR|error:|Signed" || true

[[ -f "$OUT" ]] || fail "export produced no file"

BUILD_TOOLS="$(ls -d "$ANDROID_SDK"/build-tools/* | sort -V | tail -1)"
echo
echo "=== verifying ==="
"$BUILD_TOOLS/apksigner" verify --print-certs "$OUT" 2>/dev/null \
	| grep -E "^Signer #1 certificate DN|SHA-256" || true
"$BUILD_TOOLS/aapt2" dump badging "$OUT" 2>/dev/null \
	| grep -E "^package:|targetSdkVersion:|native-code:" || true

echo
ls -lh "$OUT"

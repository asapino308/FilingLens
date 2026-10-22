#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
app="${1:?Usage: package_dmg_macos.sh /path/to/FilingLens.app [output-directory]}"
output_dir="${2:-$project_dir/release}"
if [ "$(uname -s)" != Darwin ]; then
  echo "DMG packaging requires macOS." >&2
  exit 1
fi
command -v uv >/dev/null || { echo "Install uv to run the pinned DMG packaging tool." >&2; exit 1; }
app="$(cd "$(dirname "$app")" && pwd)/$(basename "$app")"
test "$(basename "$app")" = FilingLens.app
codesign --verify --deep --strict "$app"
version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist")"
architecture="$(lipo -archs "$app/Contents/MacOS/filinglens-desktop")"
case "$architecture" in arm64|x86_64) ;; *) echo "Expected a single supported Mac architecture." >&2; exit 1 ;; esac
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
image="$output_dir/FilingLens-$version-macOS-$architecture.dmg"
if [ -e "$image" ]; then
  echo "Output already exists: $image" >&2
  exit 1
fi
uv tool run --from dmgbuild==1.6.7 dmgbuild \
  -s "$project_dir/scripts/macos_dmg_settings.py" \
  -D "app=$app" -D "instructions=$project_dir/scripts/macos_installation.txt" \
  "FilingLens $version" "$image"
hdiutil verify "$image"
mount_dir="$(mktemp -d /private/tmp/filinglens-dmg-check.XXXXXX)"
trap 'hdiutil detach "$mount_dir" >/dev/null 2>&1 || true; rmdir "$mount_dir" 2>/dev/null || true' EXIT
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mount_dir" "$image" >/dev/null
codesign --verify --deep --strict "$mount_dir/FilingLens.app"
diff -rq "$app" "$mount_dir/FilingLens.app"
test "$(readlink "$mount_dir/Applications")" = /Applications
hdiutil detach "$mount_dir"
rmdir "$mount_dir"
trap - EXIT
shasum -a 256 "$image"
echo "Drag FilingLens.app to Applications. This packaging does not notarize the app."

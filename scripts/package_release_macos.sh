#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
output_dir="${1:-$project_dir/release}"
python_bin="${PYTHON_BIN:-python3}"

"$python_bin" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"'
if [ -n "$(git -C "$project_dir" status --porcelain)" ]; then
  echo "Commit the release source before packaging it." >&2
  exit 1
fi

stage="$(mktemp -d /private/tmp/filinglens-release.XXXXXX)"
trap 'if [ "${KEEP_STAGE:-0}" = 1 ]; then echo "Build stage retained: $stage"; else rm -rf "$stage"; fi' EXIT
git -C "$project_dir" archive HEAD | tar -x -C "$stage"
test ! -e "$stage/.env"
test ! -e "$stage/data/cache"
"$python_bin" -m venv "$stage/.venv"
(cd "$stage" && ./scripts/build_desktop_macos.sh)

app="$stage/desktop/src-tauri/target/release/bundle/macos/FilingLens.app"
test -d "$app"
xattr -cr "$app"
codesign --force --deep --sign - --timestamp=none "$app"
codesign --verify --deep --strict "$app"
if find "$app" \( -name .env -o -name '*.key' -o -name '*.pem' -o -name 'cache' \) | grep -q .; then
  echo "Release contains a settings, cache, or key path." >&2
  exit 1
fi
if rg -a -l '/Users/' "$app" >/dev/null; then
  echo "Release contains a developer path or identifier." >&2
  exit 1
fi

version="$(cd "$stage" && .venv/bin/python -c 'import json; print(json.load(open("desktop/src-tauri/tauri.conf.json"))["version"])')"
mkdir -p "$output_dir"
archive="$output_dir/FilingLens-${version}-macOS-$(uname -m).zip"
ditto -c -k --sequesterRsrc --keepParent "$app" "$archive"
shasum -a 256 "$archive"
echo "Ad-hoc signed review build: $archive"
echo "Code sign and notarize before making a public download."

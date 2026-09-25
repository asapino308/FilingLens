#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"

if [ ! -x .venv/bin/python ]; then
  echo "FilingLens's Python environment is missing. Run ./scripts/setup_macos.sh --dev first." >&2
  exit 1
fi

.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m PyInstaller --noconfirm --clean --onefile \
  --name filinglens-api \
  --paths src \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  src/filinglens/desktop/api.py

triple="$(rustc -vV | awk '/^host:/ {print $2}')"
mkdir -p desktop/src-tauri/binaries
cp dist/filinglens-api "desktop/src-tauri/binaries/filinglens-api-$triple"
cd desktop
npm ci
npm run build
export RUSTFLAGS="${RUSTFLAGS:+$RUSTFLAGS }--remap-path-prefix=/Users=/build"
npx tauri build --bundles app
echo "Built FilingLens.app in desktop/src-tauri/target/release/bundle/macos/"

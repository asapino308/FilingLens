#!/bin/zsh

set -euo pipefail

PROJECT_DIR="${0:A:h:h}"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_TARGET="."
if [[ "${1:-}" == "--dev" ]]; then
  INSTALL_TARGET=".[dev]"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.11 or newer, then run this script again."
  echo "Official installer: https://www.python.org/downloads/macos/"
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "FilingLens requires Python 3.11 or newer."
  "$PYTHON_BIN" --version
  exit 1
fi

echo "Using $($PYTHON_BIN --version)"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e "$INSTALL_TARGET"

if [[ ! -f .env ]]; then
  install -m 600 .env.example .env
  echo "Created .env from the safe example."
else
  chmod 600 .env
  echo "Kept your existing .env file."
fi

echo
echo "Installation complete."
echo "1. Open .env and replace your-email@example.com with a monitored contact email."
echo "2. Choose an optional AI service: LM Studio, local Ollama, or Ollama Cloud."
echo "3. Run: .venv/bin/python scripts/doctor.py"
echo "4. Launch with: .venv/bin/python -m streamlit run app.py"

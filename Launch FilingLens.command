#!/bin/zsh

# Double-click this file in Finder to launch FilingLens.

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR" || exit 1

# Load the source tree directly. This keeps startup reliable even if macOS
# marks Python's editable-install .pth file as hidden after a restart.
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

if [[ ! -x ".venv/bin/python" ]]; then
  echo "FilingLens could not find its Python virtual environment."
  echo
  echo "Expected: $SCRIPT_DIR/.venv/bin/python"
  echo "Please complete the installation steps in README.md first."
  echo
  read "?Press Return to close this window..."
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "FilingLens could not find its .env configuration file."
  echo
  echo "Copy .env.example to .env and add your SEC contact email."
  echo
  read "?Press Return to close this window..."
  exit 1
fi

if ! ".venv/bin/python" -c "import filinglens" >/dev/null 2>&1; then
  echo "FilingLens's Python package could not be loaded."
  echo
  echo "Try reinstalling the local package with:"
  echo "  .venv/bin/python -m pip install -e '.[dev]'"
  echo
  read "?Press Return to close this window..."
  exit 1
fi

echo "Starting FilingLens..."
echo "Keep this window open while using the application."
echo "Press Control+C here when you want to stop FilingLens."
echo

".venv/bin/python" -m streamlit run app.py
exit_code=$?

if (( exit_code != 0 )); then
  echo
  echo "FilingLens stopped with error code $exit_code."
  read "?Press Return to close this window..."
fi

exit $exit_code

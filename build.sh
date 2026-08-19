#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${1:-.venv}"
PYTHON_BIN="${VENV_DIR}/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install --upgrade "Nuitka[app]" Pillow PySide6

mkdir -p build
"$PYTHON_BIN" -m nuitka --onefile --follow-imports --enable-plugin=pyside6 --include-package=PIL --include-data-dir=src/defaults=src/defaults --output-dir=build --output-file=BBConverter main.py

# Ship an editable config/ folder right next to the compiled binary. The
# onefile bundle only unpacks src/defaults into a throwaway temp dir at
# runtime, so without this the shipped .json overrides are invisible to
# users and impossible to edit/extend after the build.
mkdir -p build/config
cp src/defaults/effect_overrides.json build/config/effect_overrides.json
cp src/defaults/sheet_overrides.json build/config/sheet_overrides.json
if [ -f src/defaults/chart.cfg ]; then
  cp src/defaults/chart.cfg build/config/chart.cfg
fi

echo "Compilation completed, single-file binary generated in ./build/ as BBConverter"
echo "Editable overrides copied to ./build/config/ (keep this folder next to the binary)"

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
"$PYTHON_BIN" -m pip install --upgrade "Nuitka[app]" Pillow

mkdir -p build
"$PYTHON_BIN" -m nuitka --onefile --follow-imports --include-package=PIL --output-dir=build --output-file=BBConverter main.py

echo "Compilation completed, single-file binary generated in ./build/ as BBConverter"

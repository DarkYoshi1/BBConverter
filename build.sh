#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${1:-.venv}"
PYTHON_BIN="${VENV_DIR}/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[build] Creating virtual environment with the selected Python"
  python -m venv "$VENV_DIR"
fi

for config_file in config/effect_overrides.json config/sheet_overrides.json config/chart.cfg; do
  if [ ! -s "$config_file" ]; then
    echo "[build] ERROR: Required configuration file is missing or empty: $config_file" >&2
    exit 1
  fi
done

echo "[build] Python version:"
"$PYTHON_BIN" --version
echo "[build] Installing build dependencies"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install --upgrade "Nuitka[app]" Pillow PySide6

mkdir -p build
echo "[build] Compiling with Nuitka"
"$PYTHON_BIN" -m nuitka --onefile --follow-imports --enable-plugin=pyside6 --include-package=PIL --include-data-dir=src/defaults=src/defaults --output-dir=build --output-file=BBConverter main.py

if [ ! -s build/BBConverter ] || [ ! -x build/BBConverter ]; then
  echo "[build] ERROR: Nuitka did not create an executable at build/BBConverter" >&2
  exit 1
fi

echo "[build] Copying editable configuration"
mkdir -p build/config
cp config/effect_overrides.json build/config/effect_overrides.json
cp config/sheet_overrides.json build/config/sheet_overrides.json
cp config/chart.cfg build/config/chart.cfg

for config_file in build/config/effect_overrides.json build/config/sheet_overrides.json build/config/chart.cfg; do
  if [ ! -s "$config_file" ]; then
    echo "[build] ERROR: Required build output is missing or empty: $config_file" >&2
    exit 1
  fi
done

echo "[build] Compilation and output verification completed successfully"
echo "[build] Executable: build/BBConverter"
echo "[build] Editable configuration: build/config/"

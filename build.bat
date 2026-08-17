@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "VENV_DIR=%~1"
if "%VENV_DIR%"=="" set "VENV_DIR=.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    py -3 -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install --upgrade "Nuitka[app]" Pillow

if not exist "build" mkdir build
python -m nuitka --onefile --follow-imports --include-package=PIL --output-dir=build --output-file=BBConverter main.py

echo Compilation completed, single-file executable generated in .\build\ as BBConverter

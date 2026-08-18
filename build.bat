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
python -m nuitka --onefile --follow-imports --include-package=PIL --include-data-dir=src/defaults=src/defaults --output-dir=build --output-file=BBConverter main.py

if not exist "build\config" mkdir "build\config"
copy /Y "src\defaults\effect_overrides.json" "build\config\effect_overrides.json" >nul
copy /Y "src\defaults\sheet_overrides.json" "build\config\sheet_overrides.json" >nul
if exist "src\defaults\chart.cfg" copy /Y "src\defaults\chart.cfg" "build\config\chart.cfg" >nul

echo Compilation completed, single-file executable generated in .\build\ as BBConverter
echo Editable overrides copied to .\build\config\ (keep this folder next to the binary)

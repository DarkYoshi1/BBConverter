@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || exit /b 1

set "VENV_DIR=%~1"
if "%VENV_DIR%"=="" set "VENV_DIR=.venv"

if not exist "config\effect_overrides.json" (
    echo [build] ERROR: Missing config\effect_overrides.json
    exit /b 1
)
if not exist "config\sheet_overrides.json" (
    echo [build] ERROR: Missing config\sheet_overrides.json
    exit /b 1
)
if not exist "config\chart.cfg" (
    echo [build] ERROR: Missing config\chart.cfg
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [build] Creating virtual environment with the selected Python
    python -m venv "%VENV_DIR%"
    if errorlevel 1 exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat" || exit /b 1
echo [build] Python version:
python --version
if errorlevel 1 exit /b 1

echo [build] Installing build dependencies
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install --upgrade "Nuitka[app]" Pillow PySide6
if errorlevel 1 exit /b 1

if not exist "build" mkdir "build"
if errorlevel 1 exit /b 1

echo [build] Compiling with Nuitka
python -m nuitka --onefile --follow-imports --enable-plugin=pyside6 --include-package=PIL --include-data-dir=src/defaults=src/defaults --assume-yes-for-downloads --output-dir=build --output-file=BBConverter main.py
if errorlevel 1 exit /b 1

if not exist "build\BBConverter.exe" (
    echo [build] ERROR: Nuitka did not create build\BBConverter.exe
    exit /b 1
)

echo [build] Copying editable configuration
if not exist "build\config" mkdir "build\config"
if errorlevel 1 exit /b 1
copy /Y "config\effect_overrides.json" "build\config\effect_overrides.json" >nul
if errorlevel 1 exit /b 1
copy /Y "config\sheet_overrides.json" "build\config\sheet_overrides.json" >nul
if errorlevel 1 exit /b 1
copy /Y "config\chart.cfg" "build\config\chart.cfg" >nul
if errorlevel 1 exit /b 1

for %%F in ("build\BBConverter.exe" "build\config\effect_overrides.json" "build\config\sheet_overrides.json" "build\config\chart.cfg") do (
    if not exist "%%~F" (
        echo [build] ERROR: Expected output was not created: %%~F
        exit /b 1
    )
    if %%~zF EQU 0 (
        echo [build] ERROR: Expected output is empty: %%~F
        exit /b 1
    )
)

echo [build] Compilation and output verification completed successfully
echo [build] Executable: build\BBConverter.exe
echo [build] Editable configuration: build\config\

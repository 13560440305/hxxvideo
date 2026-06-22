@echo off
REM =============================================================================
REM StarVoyage — Vendor Dependency Setup (Windows Batch)
REM =============================================================================
REM Clones ShortGPT & OpenMontage into vendor/ so they live inside the project
REM directory instead of being installed globally.
REM
REM Usage:  scripts\setup-vendor.bat
REM =============================================================================

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "VENDOR_DIR=%PROJECT_DIR%vendor"

echo "==> Setting up vendor dependencies in: %VENDOR_DIR%"
if not exist "%VENDOR_DIR%" mkdir "%VENDOR_DIR%"

REM ── ShortGPT ─────────────────────────────────────────────────────────────────
if exist "%VENDOR_DIR%\ShortGPT" (
    echo "    ShortGPT already exists, updating..."
    cd /d "%VENDOR_DIR%\ShortGPT" && git pull --ff-only
) else (
    echo "    Cloning ShortGPT..."
    git clone --depth 1 https://github.com/RayVentura/ShortGPT.git "%VENDOR_DIR%\ShortGPT"
)

REM ── OpenMontage ──────────────────────────────────────────────────────────────
if exist "%VENDOR_DIR%\OpenMontage" (
    echo "    OpenMontage already exists, updating..."
    cd /d "%VENDOR_DIR%\OpenMontage" && git pull --ff-only
) else (
    echo "    Cloning OpenMontage..."
    git clone --depth 1 https://github.com/calesthio/OpenMontage.git "%VENDOR_DIR%\OpenMontage"
)

REM ── Install their Python dependencies ────────────────────────────────────────
echo.
echo "==> Installing vendor dependency requirements..."
pip install -q -r "%VENDOR_DIR%\ShortGPT\requirements.txt" 2>nul || ver >nul
if exist "%VENDOR_DIR%\OpenMontage\requirements.txt" (
    pip install -q -r "%VENDOR_DIR%\OpenMontage\requirements.txt" 2>nul || ver >nul
)

echo.
echo "✅ Vendor setup complete!"
echo "   ShortGPT:    %VENDOR_DIR%\ShortGPT"
echo "   OpenMontage: %VENDOR_DIR%\OpenMontage"
echo.
echo "   These are now importable because src\__init__.py adds vendor\ to sys.path."
pause

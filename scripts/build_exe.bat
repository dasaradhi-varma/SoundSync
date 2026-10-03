@echo off
title Build SoundSync Standalone Windows Executable
cd /d "%~dp0.."

echo ========================================================
echo   SoundSync Multi-Out - Standalone EXE Builder
echo   Bundles SoundSync into a native Windows .exe
echo ========================================================
echo.

python -m PyInstaller --noconsole --onefile ^
    --name "SoundSync" ^
    --icon "app_icon.ico" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "src;src" ^
    --add-data "app_icon.ico;." ^
    run.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [OK] Build Complete! Standalone executable located at:
echo      dist\SoundSync.exe
echo ========================================================
echo.
pause

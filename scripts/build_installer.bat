@echo off
title Build SoundSync Windows Installer
cd /d "%~dp0.."

echo ========================================================
echo   SoundSync Multi-Out - Setup Installer Builder
echo   Created by Dasaradhi Varma
echo ========================================================
echo.

REM 1. Ensure dist\SoundSync.exe exists first
if not exist "dist\SoundSync.exe" (
    echo [*] Compiling SoundSync.exe first...
    call scripts\build_exe.bat
)

echo [*] Compiling standalone setup installer SoundSync_Setup.exe...

python -m PyInstaller --noconsole --onefile ^
    --name "SoundSync_Setup" ^
    --icon "app_icon.ico" ^
    --add-data "dist/SoundSync.exe;payload" ^
    --add-data "app_icon.ico;payload" ^
    --add-data "app_icon.ico;." ^
    src/installer.py

if errorlevel 1 (
    echo.
    echo [ERROR] Installer build failed.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [OK] Installer Build Complete!
echo      Output: dist\SoundSync_Setup.exe
echo      Created by: Dasaradhi Varma
echo ========================================================
echo.
pause

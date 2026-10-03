@echo off
title Create SoundSync Desktop Shortcut
cd /d "%~dp0"

echo ========================================================
echo   SoundSync Multi-Out - Create Desktop App Shortcut
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
echo You can now launch SoundSync Multi-Out directly from your Desktop!
echo.
pause

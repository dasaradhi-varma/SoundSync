@echo off
title SoundSync Multi-Out
cd /d "%~dp0"
echo ========================================================
echo   SoundSync Multi-Out - Multi-Device Audio Hub
echo   Simultaneous Multi-Bluetooth and Sound Device Router
echo ========================================================
echo.
python run.py
if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause >nul
)

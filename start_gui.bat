@echo off
title SoundSync Multi-Out (Native GUI)
cd /d "%~dp0"
echo Starting SoundSync Native Tkinter GUI...
python run.py --gui
if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause >nul
)

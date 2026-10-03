#!/usr/bin/env python3
"""
SoundSync Multi-Out - macOS Application Bundle (.app) Builder
Assembles a native macOS application bundle: dist/SoundSync.app
Complete with Info.plist, retina icons, launcher, and author metadata.
Created by Dasaradhi Varma
"""

import os
import sys
import shutil
import stat
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
APP_BUNDLE_NAME = "SoundSync.app"
APP_BUNDLE_DIR = os.path.join(DIST_DIR, APP_BUNDLE_NAME)

CONTENTS_DIR = os.path.join(APP_BUNDLE_DIR, "Contents")
MACOS_DIR = os.path.join(CONTENTS_DIR, "MacOS")
RESOURCES_DIR = os.path.join(CONTENTS_DIR, "Resources")
APP_PAYLOAD_DIR = os.path.join(RESOURCES_DIR, "app")

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>SoundSync Multi-Out</string>
    <key>CFBundleExecutable</key>
    <string>SoundSync</string>
    <key>CFBundleIconFile</key>
    <string>app_logo.png</string>
    <key>CFBundleIdentifier</key>
    <string>com.dasaradhivarma.soundsync</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>SoundSync Multi-Out</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>SoundSync requires access to your audio input devices to capture and route system audio to multiple headphones and speakers.</string>
</dict>
</plist>
"""

LAUNCHER_SCRIPT = """#!/usr/bin/env bash
# SoundSync macOS App Launcher
# Created by Dasaradhi Varma

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../Resources/app" && pwd)"
cd "$DIR"

# Locate python3
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
else
    PYTHON_BIN="python"
fi

# Ensure venv exists
if [ ! -d "venv" ]; then
    $PYTHON_BIN -m venv venv || true
fi

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    PY_EXEC="python"
else
    PY_EXEC="$PYTHON_BIN"
fi

# Check requirements
$PY_EXEC -c "import sounddevice, numpy, flask, pywebview" 2>/dev/null || {
    $PY_EXEC -m pip install -r requirements.txt
}

exec $PY_EXEC run.py
"""

def build_mac_app():
    print("=" * 65)
    print("  SoundSync Multi-Out - macOS Application Bundle Builder (.app)")
    print("              Created by Dasaradhi Varma")
    print("=" * 65)

    os.makedirs(MACOS_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)

    # 1. Write Info.plist
    plist_path = os.path.join(CONTENTS_DIR, "Info.plist")
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(INFO_PLIST)
    print(f" [+] Created: {plist_path}")

    # 2. Write MacOS/SoundSync executable launcher
    launcher_path = os.path.join(MACOS_DIR, "SoundSync")
    with open(launcher_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(LAUNCHER_SCRIPT)
    try:
        os.chmod(launcher_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    except Exception:
        pass
    print(f" [+] Created: {launcher_path}")

    # 3. Copy app icon
    logo_src = os.path.join(PROJECT_DIR, "static", "icons", "app_logo.png")
    if os.path.exists(logo_src):
        shutil.copy2(logo_src, os.path.join(RESOURCES_DIR, "app_logo.png"))
        print(f" [+] Copied icon to Resources/app_logo.png")

    # 4. Copy app payload
    if os.path.exists(APP_PAYLOAD_DIR):
        shutil.rmtree(APP_PAYLOAD_DIR)
    os.makedirs(APP_PAYLOAD_DIR, exist_ok=True)

    # Copy files into app payload
    for item in ["src", "static", "templates", "run.py", "requirements.txt", "README.md"]:
        src_path = os.path.join(PROJECT_DIR, item)
        dst_path = os.path.join(APP_PAYLOAD_DIR, item)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif os.path.isfile(src_path):
            shutil.copy2(src_path, dst_path)

    print(f" [+] Application payload bundled into: {APP_PAYLOAD_DIR}")
    print("\n" + "=" * 65)
    print(f" [SUCCESS] Native macOS bundle built: {APP_BUNDLE_DIR}")
    print(" Mac users can drag 'SoundSync.app' into their /Applications folder!")
    print("=" * 65)

if __name__ == "__main__":
    build_mac_app()

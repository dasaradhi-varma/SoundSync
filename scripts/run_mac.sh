#!/usr/bin/env bash
# ==============================================================================
# SoundSync Multi-Out - macOS Application Launcher
# Simultaneous Multi-Bluetooth & Audio Router for macOS (Intel & Apple Silicon)
# Created by Dasaradhi Varma
# ==============================================================================

set -e

# Change to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "       SoundSync Multi-Out - Multi-Device Audio Hub (macOS)"
echo "            Created by Dasaradhi Varma"
echo "================================================================="

# Locate Python 3
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[-] Error: Python 3 was not found on your system."
    echo "[*] Please install Python 3 from https://www.python.org or via: brew install python"
    exit 1
fi

echo "[*] Using Python: $($PYTHON_BIN --version)"

# Check if BlackHole is installed (optional but recommended for macOS system audio loopback)
if ! system_profiler SPAudioDataType 2>/dev/null | grep -qi "BlackHole"; then
    echo ""
    echo "[!] Tip for macOS System Audio Capture:"
    echo "    To capture and duplicate your Mac's full system audio (YouTube, Spotify, Movies),"
    echo "    install BlackHole 2ch (free open-source virtual audio driver):"
    echo "        brew install blackhole-2ch"
    echo "    SoundSync can also capture from your Mac microphone or USB line-in."
    echo ""
fi

# Ensure virtualenv or install dependencies
if [ ! -d "venv" ]; then
    echo "[*] Initializing Python virtual environment..."
    $PYTHON_BIN -m venv venv || true
fi

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    PY_EXEC="python"
else
    PY_EXEC="$PYTHON_BIN"
fi

# Check requirements
echo "[*] Verifying dependencies..."
$PY_EXEC -c "import sounddevice, numpy, flask, pywebview" 2>/dev/null || {
    echo "[*] Installing required packages..."
    $PY_EXEC -m pip install -r requirements.txt
}

echo "[*] Starting SoundSync Desktop Application..."
exec $PY_EXEC run.py "$@"

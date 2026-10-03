#!/usr/bin/env bash
# ==============================================================================
# SoundSync Multi-Out - macOS 1-Click Setup & Installer
# Created by Dasaradhi Varma
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "       SoundSync Multi-Out - macOS Setup & Installer"
echo "              Created by Dasaradhi Varma"
echo "================================================================="
echo ""

# 1. Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "[-] Python 3 not detected. Please install Python 3 or Homebrew:"
    echo "    https://brew.sh or https://www.python.org"
    exit 1
fi

echo "[+] Python 3 detected: $(python3 --version)"

# 2. Check Homebrew and BlackHole (Optional audio loopback driver for macOS)
if command -v brew &>/dev/null; then
    if ! brew list blackhole-2ch &>/dev/null; then
        echo ""
        read -p "[?] Would you like to install BlackHole 2ch for direct macOS system audio capture? (y/n): " INSTALL_BH
        if [[ "$INSTALL_BH" =~ ^[Yy]$ ]]; then
            echo "[*] Installing BlackHole 2ch via Homebrew..."
            brew install blackhole-2ch || echo "[!] Notice: Please grant audio permissions if prompted."
        fi
    else
        echo "[+] BlackHole 2ch is already installed!"
    fi
else
    echo "[!] Tip: Install Homebrew (https://brew.sh) and 'brew install blackhole-2ch' for direct system audio loopback capture."
fi

# 3. Destination folder selection (default: /Applications or ~/Applications)
DEFAULT_DIR="/Applications"
if [ ! -w "/Applications" ]; then
    DEFAULT_DIR="$HOME/Applications"
    mkdir -p "$DEFAULT_DIR"
fi

echo ""
echo "-----------------------------------------------------------------"
echo " Installation Destination"
echo " Created by Dasaradhi Varma"
echo "-----------------------------------------------------------------"
read -p "Enter installation path [default: $DEFAULT_DIR]: " USER_DEST
INSTALL_DIR="${USER_DEST:-$DEFAULT_DIR}"

echo "[*] Target Installation Folder: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# 4. Build or copy SoundSync.app
echo "[*] Building SoundSync.app bundle..."
python3 scripts/build_mac_app.py

echo "[*] Installing SoundSync.app into $INSTALL_DIR/SoundSync.app..."
rm -rf "$INSTALL_DIR/SoundSync.app"
cp -R "dist/SoundSync.app" "$INSTALL_DIR/"

# 5. Create Desktop shortcut
DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    ln -sf "$INSTALL_DIR/SoundSync.app" "$DESKTOP_DIR/SoundSync Multi-Out"
    echo "[+] Created Desktop shortcut: $DESKTOP_DIR/SoundSync Multi-Out"
fi

echo ""
echo "================================================================="
echo " [SUCCESS] SoundSync Multi-Out has been installed successfully!"
echo "           Created by Dasaradhi Varma"
echo " Location: $INSTALL_DIR/SoundSync.app"
echo "================================================================="
echo ""

read -p "Would you like to launch SoundSync now? (y/n): " LAUNCH_NOW
if [[ "$LAUNCH_NOW" =~ ^[Yy]$ ]]; then
    open "$INSTALL_DIR/SoundSync.app"
fi

"""
SoundSync Multi-Out - Universal Application Launcher
Launches the background audio server and opens the application window while keeping the server alive.
"""

import sys
import os
import time
import subprocess
import threading
import webbrowser
import argparse

from server import app
from audio_engine import audio_engine

def find_browser_app_executable():
    """Finds Edge or Chrome for dedicated desktop app window mode."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None

def start_flask(host, port):
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)

def main():
    parser = argparse.ArgumentParser(description="SoundSync Multi-Out - Multi-Device Audio Hub")
    parser.add_argument("--gui", action="store_true", help="Launch native Tkinter desktop GUI instead of Web/App mode")
    parser.add_argument("--browser", action="store_true", help="Force opening in standard web browser")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind server (default: 8765)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.gui:
        print("[*] Launching SoundSync Native Tkinter GUI...")
        from gui_tkinter import run_tkinter
        run_tkinter()
        return

    url = f"http://{args.host}:{args.port}"
    print("=" * 65)
    print("       SoundSync Multi-Out - Multi-Device Audio Hub")
    print("       Connect & stream to multiple Bluetooth devices")
    print("=" * 65)
    print(f"[*] Starting Audio Engine & Server at {url}...")

    # Start Flask in daemon thread
    server_thread = threading.Thread(target=start_flask, args=(args.host, args.port), daemon=True)
    server_thread.start()

    time.sleep(1.2) # Allow server socket to bind

    # Launch desktop window or browser
    browser_exe = find_browser_app_executable()
    opened_app_mode = False

    if browser_exe and not args.browser:
        try:
            print(f"[*] Launching Desktop Application Window ({os.path.basename(browser_exe)})...")
            cmd = [browser_exe, f"--app={url}", "--window-size=1220,860"]
            subprocess.Popen(cmd)
            opened_app_mode = True
        except Exception as e:
            print(f"[*] Could not open app window ({e}), falling back to browser...")

    if not opened_app_mode:
        print(f"[*] Opening in default web browser: {url}")
        webbrowser.open(url)

    print("\n" + "=" * 65)
    print(" [✓] SoundSync Multi-Out is ACTIVE and READY!")
    print(f" [✓] Application URL: {url}")
    print(" [✓] Keep this window open while using multi-device audio.")
    print(" [✓] To exit, press Ctrl+C in this window.")
    print("=" * 65 + "\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down audio engine and server...")
        audio_engine.stop_broadcast()
        sys.exit(0)

if __name__ == '__main__':
    main()

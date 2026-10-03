"""
SoundSync Multi-Out - Universal Desktop Application Launcher
Launches the background audio server and opens the native application window.
"""

import sys
import os
import time
import subprocess
import threading
import webbrowser
import argparse
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(APP_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from src.server import app
    from src.audio_engine import audio_engine
except ImportError:
    from server import app
    from audio_engine import audio_engine

ICON_PATH = os.path.join(APP_DIR, "app_icon.ico")

def find_browser_app_executable():
    """Finds Edge or Chrome for dedicated standalone app window mode as fallback."""
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
    """Starts the Flask audio server in the background."""
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)

def wait_for_server(url, timeout=5.0):
    """Polls the local server until it responds with HTTP 200."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{url}/api/status", timeout=0.5) as res:
                if res.status == 200:
                    return True
        except Exception:
            time.sleep(0.12)
    return False

def launch_native_window(url):
    """Launches the app as a true native desktop application window via pywebview."""
    try:
        import webview
        print("[*] Launching SoundSync Native Desktop App Window...")
        window = webview.create_window(
            title="SoundSync Multi-Out - Multi-Device Audio Hub",
            url=url,
            width=1260,
            height=860,
            min_size=(960, 620),
            background_color="#0b0f19",
            text_select=False
        )
        webview.start()
        return True
    except Exception as e:
        print(f"[*] Native window unavailable ({e}), trying standalone app fallback...")
        return False

def main():
    parser = argparse.ArgumentParser(description="SoundSync Multi-Out - Multi-Device Audio Hub")
    parser.add_argument("--gui", action="store_true", help="Launch native Tkinter desktop GUI instead of Web/App mode")
    parser.add_argument("--browser", action="store_true", help="Force opening in standard web browser tab")
    parser.add_argument("--headless", action="store_true", help="Run server without opening a window")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind server (default: 8765)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.gui:
        print("[*] Launching SoundSync Native Tkinter GUI...")
        try:
            from src.gui_tkinter import run_tkinter
        except ImportError:
            from gui_tkinter import run_tkinter
        run_tkinter()
        return

    url = f"http://{args.host}:{args.port}"
    print("=" * 65)
    print("       SoundSync Multi-Out - Multi-Device Audio Hub")
    print("       Simultaneous Multi-Bluetooth & Audio Router")
    print("=" * 65)
    print(f"[*] Starting Audio Engine & Server at {url}...")

    # Start Flask in daemon thread
    server_thread = threading.Thread(target=start_flask, args=(args.host, args.port), daemon=True)
    server_thread.start()

    # Wait for server readiness
    if not wait_for_server(url):
        time.sleep(1.0)

    print(" [OK] Audio Engine & Server are ONLINE!")

    if args.headless:
        print("[*] Running in headless mode. Press Ctrl+C to terminate.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            audio_engine.stop_broadcast()
            sys.exit(0)

    # If browser mode explicitly requested
    if args.browser:
        print(f"[*] Opening in default web browser: {url}")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            audio_engine.stop_broadcast()
            sys.exit(0)

    # 1. Try Native Desktop App Window (pywebview with WebView2)
    opened_native = launch_native_window(url)
    if opened_native:
        # Window was closed by user
        print("\n[*] Native window closed. Shutting down audio engine...")
        audio_engine.stop_broadcast()
        sys.exit(0)

    # 2. Fallback: Edge or Chrome dedicated standalone App Mode
    browser_exe = find_browser_app_executable()
    opened_app_mode = False
    if browser_exe:
        try:
            print(f"[*] Launching Desktop Application Window ({os.path.basename(browser_exe)})...")
            cmd = [browser_exe, f"--app={url}", "--window-size=1260,860"]
            subprocess.Popen(cmd)
            opened_app_mode = True
        except Exception as e:
            print(f"[*] Could not open app window ({e}), falling back to browser...")

    # 3. Final Fallback: Standard browser
    if not opened_app_mode:
        print(f"[*] Opening in default web browser: {url}")
        webbrowser.open(url)

    print("\n" + "=" * 65)
    print(" [OK] SoundSync Multi-Out is ACTIVE and READY!")
    print(f" [OK] Application URL: {url}")
    print(" [OK] Keep this console open while using multi-device audio.")
    print(" [OK] To exit, press Ctrl+C in this window.")
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

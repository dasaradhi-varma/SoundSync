# 🎵 SoundSync Multi-Out

> **Simultaneous Multi-Bluetooth & Sound Device Controller for Windows**  
> Play YouTube, Spotify, games, movies, and system sounds to **multiple Bluetooth headphones/speakers simultaneously** with independent volume control, latency delay sync, and real-time audio visualizers.

---

## 🌟 Features

- **Multi-Device Simultaneous Playback**: Connect 2, 3, or more Bluetooth headsets/speakers (e.g., AirPods, OnePlus Buds, boAt, Sony, JBL) plus laptop speakers, and broadcast audio to all of them at once.
- **Zero-Latency WASAPI Loopback Capture**: Captures 32-bit digital audio directly from Windows Audio Engine without distortion or external cables.
- **Independent Volume Faders**: Adjust volume independently for each listener (0% to 150% with software boost).
- **Bluetooth Latency Sync (Delay Compensation)**: Different Bluetooth codecs/chips have different latencies. Use the micro-adjustable **Sync Delay slider (0 to 500 ms)** to eliminate any echo between different Bluetooth headphones.
- **Real-Time VU Visualizers**: High-speed peak and RMS audio level meters for both master capture and each active output endpoint.
- **Instant Test Tone**: One-click harmonic chime to verify each headset/speaker is active and audible without needing to play music first.
- **Dynamic Device Hot-Plug**: Turn on a new Bluetooth headset while streaming? Click **Refresh Devices** to detect and route to it on the fly without stopping music.
- **Dual Interface**:
  - **Sleek Desktop App Window**: Launches as a frameless, dark glassmorphism desktop app via Edge/Chrome app mode.
  - **Native Tkinter Desktop GUI**: Complete standalone native Python desktop window (`python run.py --gui`).

---

## 🚀 Quick Start

### 1. Launch the Application

Double-click either launcher in the folder:
- **`start.bat`**: Launches the modern Studio Web/Desktop application window.
- **`start_gui.bat`**: Launches the lightweight native Tkinter desktop window.

Or run from terminal:
```powershell
python run.py         # Desktop / Web Studio App
python run.py --gui   # Native Tkinter Desktop Window
```

---

## 🎧 How to Connect 3 Bluetooth Devices on Windows

Windows 10 and Windows 11 hardware natively supports maintaining multiple concurrent Bluetooth audio connections. Follow these steps:

1. **Pair Device 1**:
   - Press <kbd>Win</kbd> + <kbd>I</kbd> to open **Windows Settings**.
   - Navigate to **Bluetooth & devices**.
   - Turn on your 1st Bluetooth headphones in pairing mode, click **Add device** ➔ **Bluetooth**, and connect.
2. **Pair Device 2**:
   - Turn on your 2nd Bluetooth headphones/speaker in pairing mode.
   - Click **Add device** ➔ **Bluetooth**, and connect it too. Windows will show both as *Connected audio*.
3. **Pair Device 3**:
   - Turn on your 3rd Bluetooth headphones/speaker in pairing mode.
   - Click **Add device** ➔ **Bluetooth**, and connect it. Windows will now show all 3 devices connected.
4. **Open SoundSync Multi-Out**:
   - Click **Refresh Devices** (or restart the app).
   - You will see all 3 Bluetooth devices listed with their custom names and Bluetooth badges (ᛒ).
   - Ensure the toggle switches are **ON** for all 3 devices.
5. **Start Broadcasting**:
   - Click **START BROADCASTING**.
   - Play any audio on your laptop (YouTube, Spotify, Netflix, games). Sound will play across all 3 devices simultaneously!
6. **Fine-Tune Sync and Volume**:
   - If one Bluetooth headset has a slight wireless delay compared to another, adjust its **Bluetooth Latency Sync (Delay)** slider until they match in phase.
   - Set individual volume sliders to each listener's preferred level.

---

## 📁 Project Structure

```
sound/
├── audio_engine.py       # WASAPI loopback capture & multi-worker streaming engine
├── server.py             # Flask API & Server-Sent Events (SSE) meter stream
├── gui_tkinter.py        # Complete native desktop Tkinter GUI
├── run.py                # Universal launcher (app window / browser / native GUI)
├── start.bat             # 1-Click Windows launch script
├── requirements.txt      # Python dependencies
├── static/
│   ├── css/style.css     # Dark glassmorphism studio UI styling
│   └── js/app.js         # Frontend controller & live VU meter animations
└── templates/
    └── index.html        # Main HTML5 application interface
```

---

## 🎛️ Audio Engine Architecture

```
[ Windows Audio Output (YouTube, Spotify, Games) ]
                      │
                      ▼
          [ WASAPI Loopback Capture ]
           (32-bit Float, 48kHz Stereo)
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   [ Worker 1 ]  [ Worker 2 ]  [ Worker 3 ]
  (Delay + Vol) (Delay + Vol) (Delay + Vol)
        │             │             │
        ▼             ▼             ▼
  [ Bluetooth 1 ] [ Bluetooth 2] [ Bluetooth 3 ]
   (OnePlus Buds)  (boAt Headset)  (JBL Speaker)
```

- Each device stream runs in an independent high-priority thread with a drop-oldest ring buffer to prevent stutter or buffer underrun.
- Fast vectorized delay lines allow sub-millisecond audio synchronization across different wireless headphones.

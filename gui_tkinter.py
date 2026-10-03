"""
SoundSync Multi-Out - Native Tkinter GUI
Self-contained desktop application interface for multi-device audio routing.
Runs directly in Python without requiring any browser.
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from audio_engine import audio_engine

class SoundSyncTkinterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SoundSync Multi-Out | Multi-Device Audio Hub")
        self.geometry("960x720")
        self.minsize(800, 600)
        self.configure(bg="#0f172a")

        self.device_widgets = {} # dev_id -> dict of widgets
        self.running_meters = True

        self._apply_dark_theme()
        self._build_header()
        self._build_master_deck()
        self._build_devices_section()
        self._build_footer()

        self.refresh_devices()
        self._start_meter_updater()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_dark_theme(self):
        style = ttk.Style(self)
        style.theme_use('clam')

        # Global styles
        style.configure(".", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 10))
        style.configure("TFrame", background="#0f172a")
        style.configure("Card.TFrame", background="#1e293b", relief="flat")
        style.configure("TLabel", background="#0f172a", foreground="#f8fafc")
        style.configure("Card.TLabel", background="#1e293b", foreground="#f8fafc")
        style.configure("Muted.TLabel", background="#1e293b", foreground="#94a3b8", font=("Segoe UI", 9))
        
        style.configure("Title.TLabel", background="#0f172a", foreground="#38bdf8", font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel", background="#0f172a", foreground="#94a3b8", font=("Segoe UI", 9))
        
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), background="#0284c7", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#0369a1")])

        style.configure("Stop.TButton", font=("Segoe UI", 11, "bold"), background="#dc2626", foreground="#ffffff")
        style.map("Stop.TButton", background=[("active", "#b91c1c")])

        style.configure("Secondary.TButton", font=("Segoe UI", 9), background="#334155", foreground="#ffffff")
        style.map("Secondary.TButton", background=[("active", "#475569")])

        style.configure("Horizontal.TProgressbar", background="#10b981", troughcolor="#0f172a", thickness=8)

    def _build_header(self):
        header_frame = ttk.Frame(self, padding=(20, 16, 20, 10))
        header_frame.pack(fill=tk.X)

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text="SoundSync Multi-Out", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Simultaneous Multi-Bluetooth & Sound Device Router", style="Subtitle.TLabel").pack(anchor="w")

        btn_box = ttk.Frame(header_frame)
        btn_box.pack(side=tk.RIGHT)
        ttk.Button(btn_box, text="🔄 Refresh Devices", style="Secondary.TButton", command=self.refresh_devices).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_box, text="🔊 Test All", style="Secondary.TButton", command=lambda: audio_engine.play_test_tone(None)).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_box, text="ℹ️ Bluetooth Guide", style="Secondary.TButton", command=self.show_guide).pack(side=tk.LEFT, padx=6)

    def _build_master_deck(self):
        deck = ttk.Frame(self, style="Card.TFrame", padding=16)
        deck.pack(fill=tk.X, padx=20, pady=10)

        top_row = ttk.Frame(deck, style="Card.TFrame")
        top_row.pack(fill=tk.X, pady=(0, 10))

        info_box = ttk.Frame(top_row, style="Card.TFrame")
        info_box.pack(side=tk.LEFT)
        self.master_title_lbl = ttk.Label(info_box, text="Master Broadcast Deck (Standby)", font=("Segoe UI", 12, "bold"), style="Card.TLabel")
        self.master_title_lbl.pack(anchor="w")
        self.master_src_lbl = ttk.Label(info_box, text="Capture Source: Initializing...", style="Muted.TLabel")
        self.master_src_lbl.pack(anchor="w")

        self.btn_broadcast = ttk.Button(top_row, text="▶ START BROADCASTING", style="Primary.TButton", command=self.toggle_broadcast)
        self.btn_broadcast.pack(side=tk.RIGHT, padx=10, ipady=6, ipadx=12)

        # Controls row
        ctrl_row = ttk.Frame(deck, style="Card.TFrame")
        ctrl_row.pack(fill=tk.X, pady=4)

        ttk.Label(ctrl_row, text="Master Volume:", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        self.master_vol_val = ttk.Label(ctrl_row, text="100%", width=5, style="Card.TLabel", font=("Consolas", 10, "bold"))
        self.master_vol_val.pack(side=tk.LEFT)

        self.master_slider = ttk.Scale(ctrl_row, from_=0, to=150, value=100, command=self._on_master_slider)
        self.master_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12)

        self.btn_master_mute = ttk.Button(ctrl_row, text="Mute", style="Secondary.TButton", command=self._toggle_master_mute)
        self.btn_master_mute.pack(side=tk.LEFT, padx=6)

        # Master VU Meter
        meter_row = ttk.Frame(deck, style="Card.TFrame")
        meter_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(meter_row, text="Master Audio Level:", style="Muted.TLabel", width=18).pack(side=tk.LEFT)
        self.master_meter = ttk.Progressbar(meter_row, orient=tk.HORIZONTAL, length=100, mode='determinate', style="Horizontal.TProgressbar")
        self.master_meter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

    def _build_devices_section(self):
        container = ttk.Frame(self, padding=(20, 10, 20, 10))
        container.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(container)
        header.pack(fill=tk.X, pady=(0, 8))
        self.devices_count_lbl = ttk.Label(header, text="Connected Audio Endpoints (0)", font=("Segoe UI", 12, "bold"))
        self.devices_count_lbl.pack(side=tk.LEFT)

        # Scrollable device canvas
        self.canvas = tk.Canvas(container, bg="#0f172a", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=910)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_footer(self):
        footer = ttk.Frame(self, padding=(20, 8, 20, 12))
        footer.pack(fill=tk.X)
        self.status_bar = ttk.Label(footer, text="Ready. Connect your Bluetooth headphones/speakers and start broadcast.", foreground="#64748b", font=("Segoe UI", 9))
        self.status_bar.pack(side=tk.LEFT)

    def refresh_devices(self):
        status = audio_engine.get_status()
        devices = status['devices']

        # Update capture info
        def_out = status.get('default_output') or 'None'
        self.master_src_lbl.config(text=f"Loopback Source: {def_out} (48kHz Stereo)")
        self.devices_count_lbl.config(text=f"Connected Audio Endpoints ({len(devices)})")

        # Clear existing cards
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.device_widgets.clear()

        # Render device cards
        for dev in devices:
            self._render_device_card(dev)

    def _render_device_card(self, dev):
        idx = dev['index']
        is_bt = dev['category'] == 'bluetooth'
        icon = "ᛒ " if is_bt else ("🔊 " if dev['category'] == 'speaker' else "🎛️ ")

        card = ttk.Frame(self.scrollable_frame, style="Card.TFrame", padding=12)
        card.pack(fill=tk.X, pady=6)

        # Header row
        hdr = ttk.Frame(card, style="Card.TFrame")
        hdr.pack(fill=tk.X)

        title_text = f"{icon}{dev['name']}"
        if dev['is_default']:
            title_text += "  [DEFAULT OUTPUT]"
        if is_bt:
            title_text += "  [BLUETOOTH]"

        title_lbl = ttk.Label(hdr, text=title_text, font=("Segoe UI", 10, "bold"), style="Card.TLabel")
        title_lbl.pack(side=tk.LEFT)

        # Enable checkbox
        enable_var = tk.BooleanVar(value=dev['enabled'])
        chk = tk.Checkbutton(
            hdr, text="Output Enabled", variable=enable_var,
            bg="#1e293b", fg="#38bdf8", selectcolor="#0f172a",
            activebackground="#1e293b", activeforeground="#38bdf8",
            command=lambda i=idx, v=enable_var: audio_engine.set_device_config(i, enabled=v.get())
        )
        chk.pack(side=tk.RIGHT)

        # Level meter
        meter_box = ttk.Frame(card, style="Card.TFrame")
        meter_box.pack(fill=tk.X, pady=4)
        prog = ttk.Progressbar(meter_box, orient=tk.HORIZONTAL, length=100, mode='determinate', style="Horizontal.TProgressbar")
        prog.pack(fill=tk.X)

        # Sliders row
        sliders_box = ttk.Frame(card, style="Card.TFrame")
        sliders_box.pack(fill=tk.X, pady=6)

        # Volume slider
        ttk.Label(sliders_box, text="Vol:", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=4)
        vol_val_lbl = ttk.Label(sliders_box, text=f"{int(dev['volume']*100)}%", width=5, style="Card.TLabel", font=("Consolas", 9))
        vol_val_lbl.grid(row=0, column=1, padx=4)
        vol_slider = ttk.Scale(
            sliders_box, from_=0, to=150, value=int(dev['volume']*100),
            command=lambda val, i=idx, l=vol_val_lbl: self._on_device_vol(i, val, l)
        )
        vol_slider.grid(row=0, column=2, sticky="ew", padx=8)

        # Delay slider (Bluetooth sync)
        ttk.Label(sliders_box, text="Sync Delay:", style="Card.TLabel").grid(row=0, column=3, sticky="w", padx=(12, 4))
        delay_val_lbl = ttk.Label(sliders_box, text=f"{int(dev['delay_ms'])}ms", width=6, style="Card.TLabel", font=("Consolas", 9))
        delay_val_lbl.grid(row=0, column=4, padx=4)
        delay_slider = ttk.Scale(
            sliders_box, from_=0, to=500, value=dev['delay_ms'],
            command=lambda val, i=idx, l=delay_val_lbl: self._on_device_delay(i, val, l)
        )
        delay_slider.grid(row=0, column=5, sticky="ew", padx=8)

        # Action buttons
        actions_box = ttk.Frame(card, style="Card.TFrame")
        actions_box.pack(fill=tk.X, pady=(4, 0))

        test_btn = ttk.Button(actions_box, text="🎵 Test Tone", style="Secondary.TButton", command=lambda i=idx: audio_engine.play_test_tone(i))
        test_btn.pack(side=tk.LEFT, padx=(0, 8))

        mute_var = tk.BooleanVar(value=dev['muted'])
        mute_chk = tk.Checkbutton(
            actions_box, text="Mute", variable=mute_var,
            bg="#1e293b", fg="#f87171", selectcolor="#0f172a",
            activebackground="#1e293b", activeforeground="#f87171",
            command=lambda i=idx, v=mute_var: audio_engine.set_device_config(i, muted=v.get())
        )
        mute_chk.pack(side=tk.LEFT)

        sliders_box.columnconfigure(2, weight=1)
        sliders_box.columnconfigure(5, weight=1)

        self.device_widgets[idx] = {
            'meter': prog,
            'vol_label': vol_val_lbl,
            'delay_label': delay_val_lbl
        }

    def _on_master_slider(self, val):
        v = int(float(val))
        self.master_vol_val.config(text=f"{v}%")
        audio_engine.set_master_config(volume=v / 100.0)

    def _toggle_master_mute(self):
        cur = audio_engine.master_muted
        audio_engine.set_master_config(muted=not cur)
        self.btn_master_mute.config(text="Unmute" if not cur else "Mute")

    def _on_device_vol(self, idx, val, lbl):
        v = int(float(val))
        lbl.config(text=f"{v}%")
        audio_engine.set_device_config(idx, volume=v / 100.0)

    def _on_device_delay(self, idx, val, lbl):
        d = int(float(val))
        lbl.config(text=f"{d}ms")
        audio_engine.set_device_config(idx, delay_ms=d)

    def toggle_broadcast(self):
        if audio_engine.is_broadcasting:
            audio_engine.stop_broadcast()
            self.btn_broadcast.config(text="▶ START BROADCASTING", style="Primary.TButton")
            self.master_title_lbl.config(text="Master Broadcast Deck (Standby)")
            self.status_bar.config(text="Broadcast stopped.")
        else:
            success = audio_engine.start_broadcast()
            if success:
                self.btn_broadcast.config(text="⏹ STOP BROADCASTING", style="Stop.TButton")
                self.master_title_lbl.config(text="Master Broadcast Deck (BROADCASTING LIVE 🟢)")
                self.status_bar.config(text="Streaming live system audio to all enabled outputs.")
            else:
                messagebox.showerror("Error", "Failed to start broadcast loopback. Please verify audio output devices.")

    def _start_meter_updater(self):
        def _update():
            if not self.running_meters:
                return
            try:
                meters = audio_engine.get_meter_levels()
                # Master level
                m_lvl = meters.get('master_level', 0.0)
                self.master_meter['value'] = min(100, int(m_lvl * 100))

                # Per-device level
                dev_lvls = meters.get('device_levels', {})
                for dev_id, lvl in dev_lvls.items():
                    if dev_id in self.device_widgets:
                        self.device_widgets[dev_id]['meter']['value'] = min(100, int(lvl * 100))
            except Exception:
                pass
            self.after(50, _update)

        self.after(50, _update)

    def show_guide(self):
        msg = (
            "How to connect 3 Bluetooth Devices on Windows:\n\n"
            "1. Press Win + I to open Windows Settings -> Bluetooth & devices.\n"
            "2. Put Device 1 into pairing mode, click 'Add device' and connect.\n"
            "3. Put Device 2 into pairing mode, click 'Add device' and connect.\n"
            "4. Put Device 3 into pairing mode, click 'Add device' and connect.\n"
            "   (Windows can maintain multiple active Bluetooth audio connections!)\n\n"
            "5. In SoundSync Multi-Out, click 'Refresh Devices'.\n"
            "6. Make sure 'Output Enabled' is checked for all 3 devices.\n"
            "7. Click 'START BROADCASTING' to play sound to all 3 simultaneously!\n\n"
            "Tip: Use 'Sync Delay' sliders to fine-tune lip sync and eliminate Bluetooth echo."
        )
        messagebox.showinfo("Bluetooth Setup Guide", msg)

    def on_close(self):
        self.running_meters = False
        try:
            audio_engine.stop_broadcast()
        except Exception:
            pass
        self.destroy()


def run_tkinter():
    app = SoundSyncTkinterApp()
    app.mainloop()


if __name__ == '__main__':
    run_tkinter()

"""
SoundSync Multi-Out - macOS Setup Wizard GUI
Interactive installation wizard for macOS.
Features custom folder browsing, default /Applications path,
author credit ('Created by Dasaradhi Varma'), and desktop shortcut creation.
Created by Dasaradhi Varma
"""

import sys
import os
import shutil
import stat
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

# Base paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_INSTALL_DIR = "/Applications/SoundSync.app" if os.access("/Applications", os.W_OK) else os.path.expanduser("~/Applications/SoundSync.app")

class SoundSyncMacInstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SoundSync Multi-Out Setup (macOS)")
        self.geometry("640x520")
        self.resizable(False, False)
        self.configure(bg="#0b0f19")

        # Variables
        self.install_path_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.desktop_shortcut_var = tk.BooleanVar(value=True)
        self.launch_after_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready to install SoundSync Multi-Out for macOS.")

        self._init_styles()
        self._build_ui()

    def _init_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure(".", background="#0b0f19", foreground="#f8fafc", font=("-apple-system", "Helvetica Neue", 10))
        self.style.configure("TFrame", background="#0b0f19")
        self.style.configure("Card.TFrame", background="#151d30", relief="flat")
        self.style.configure("TLabel", background="#0b0f19", foreground="#f8fafc")
        self.style.configure("Card.TLabel", background="#151d30", foreground="#f8fafc")
        
        self.style.configure("Title.TLabel", font=("-apple-system", "Helvetica Neue", 18, "bold"), foreground="#38bdf8")
        self.style.configure("Subtitle.TLabel", font=("-apple-system", "Helvetica Neue", 10), foreground="#94a3b8")
        self.style.configure("Author.TLabel", font=("-apple-system", "Helvetica Neue", 11, "bold"), foreground="#00f2fe", background="#151d30")
        self.style.configure("Muted.TLabel", font=("-apple-system", "Helvetica Neue", 9), foreground="#64748b")
        
        self.style.configure("Primary.TButton", font=("-apple-system", "Helvetica Neue", 11, "bold"), background="#0284c7", foreground="#ffffff")
        self.style.map("Primary.TButton", background=[("active", "#0369a1")])

        self.style.configure("Browse.TButton", font=("-apple-system", "Helvetica Neue", 10), background="#334155", foreground="#ffffff")
        self.style.map("Browse.TButton", background=[("active", "#475569")])

        self.style.configure("TCheckbutton", background="#0b0f19", foreground="#f8fafc", font=("-apple-system", "Helvetica Neue", 10))
        self.style.map("TCheckbutton", background=[("active", "#0b0f19")])

        self.style.configure("Horizontal.TProgressbar", background="#00f2fe", troughcolor="#070a12", thickness=10)

    def _build_ui(self):
        # 1. Header with logo and branding
        header = ttk.Frame(self, padding=(24, 20, 24, 12))
        header.pack(fill=tk.X)

        # Try to load app logo
        logo_path = os.path.join(PROJECT_DIR, "static", "icons", "icon-192.png")
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path).resize((64, 64), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                lbl_logo = ttk.Label(header, image=self.logo_img)
                lbl_logo.pack(side=tk.LEFT, padx=(0, 16))
            except Exception:
                pass

        header_text = ttk.Frame(header)
        header_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(header_text, text="SoundSync Multi-Out", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header_text, text="Simultaneous Multi-Bluetooth & Audio Router for macOS", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

        # 2. Author Credit Card (Prominently displaying "Created by Dasaradhi Varma")
        author_card = ttk.Frame(self, style="Card.TFrame", padding=(16, 12))
        author_card.pack(fill=tk.X, padx=24, pady=8)

        ttk.Label(author_card, text="✦ DEVELOPER & AUTHOR ATTRIBUTION", font=("-apple-system", "Helvetica Neue", 9, "bold"), foreground="#38bdf8", style="Card.TLabel").pack(anchor="w")
        ttk.Label(author_card, text="Created by Dasaradhi Varma", style="Author.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Label(author_card, text="High-Performance Low-Latency Audio Streaming Hub for macOS & Windows", style="Muted.TLabel").pack(anchor="w")

        # 3. Destination Directory Picker
        dest_card = ttk.Frame(self, style="Card.TFrame", padding=(16, 14))
        dest_card.pack(fill=tk.X, padx=24, pady=8)

        ttk.Label(dest_card, text="Choose Installation Destination:", font=("-apple-system", "Helvetica Neue", 10, "bold"), style="Card.TLabel").pack(anchor="w")
        ttk.Label(dest_card, text="SoundSync.app will be installed into this application directory:", style="Muted.TLabel").pack(anchor="w", pady=(2, 6))

        path_box = ttk.Frame(dest_card, style="Card.TFrame")
        path_box.pack(fill=tk.X)

        self.path_entry = tk.Entry(path_box, textvariable=self.install_path_var, font=("-apple-system", "Helvetica Neue", 10), bg="#070a12", fg="#38bdf8", insertbackground="#38bdf8", relief="flat", highlightthickness=1, highlightbackground="#334155")
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))

        ttk.Button(path_box, text="Browse...", style="Browse.TButton", command=self._browse_folder).pack(side=tk.RIGHT)

        ttk.Label(dest_card, text="Space required: ~65 MB  |  Platform: macOS 10.15+ (Intel & Apple Silicon)", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

        # 4. Options
        opts_frame = ttk.Frame(self, padding=(24, 4))
        opts_frame.pack(fill=tk.X)

        ttk.Checkbutton(opts_frame, text="Create Desktop shortcut (SoundSync Multi-Out)", variable=self.desktop_shortcut_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(opts_frame, text="Launch SoundSync immediately after installation completes", variable=self.launch_after_var).pack(anchor="w", pady=2)

        # 5. Progress and Status
        progress_box = ttk.Frame(self, padding=(24, 8))
        progress_box.pack(fill=tk.X)

        self.progress_bar = ttk.Progressbar(progress_box, mode="determinate", style="Horizontal.TProgressbar")
        self.progress_bar.pack(fill=tk.X)

        self.status_lbl = ttk.Label(progress_box, textvariable=self.status_var, style="Muted.TLabel")
        self.status_lbl.pack(anchor="w", pady=(4, 0))

        # 6. Bottom action buttons
        footer = ttk.Frame(self, padding=(24, 10, 24, 16))
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_install = ttk.Button(footer, text="Install SoundSync", style="Primary.TButton", command=self._start_install)
        self.btn_install.pack(side=tk.RIGHT, ipadx=12, ipady=6)

        ttk.Button(footer, text="Cancel", style="Browse.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=8, ipady=6)

    def _browse_folder(self):
        curr = os.path.dirname(self.install_path_var.get())
        chosen = filedialog.askdirectory(initialdir=curr, title="Select Installation Directory")
        if chosen:
            if not chosen.endswith(".app"):
                target = os.path.join(chosen, "SoundSync.app")
            else:
                target = chosen
            self.install_path_var.set(target)

    def _start_install(self):
        self.btn_install.config(state="disabled")
        threading.Thread(target=self._run_install_worker, daemon=True).start()

    def _run_install_worker(self):
        try:
            target_app_path = self.install_path_var.get().strip()
            if not target_app_path.endswith(".app"):
                target_app_path = os.path.join(target_app_path, "SoundSync.app")

            target_parent = os.path.dirname(target_app_path)
            os.makedirs(target_parent, exist_ok=True)

            self.status_var.set("Assembling macOS Application Bundle (.app)...")
            self.progress_bar['value'] = 20
            self.update_idletasks()

            # Build bundle
            builder_py = os.path.join(PROJECT_DIR, "scripts", "build_mac_app.py")
            subprocess.run([sys.executable, builder_py], check=True, cwd=PROJECT_DIR)

            self.progress_bar['value'] = 50
            self.status_var.set(f"Copying bundle to {target_app_path}...")
            self.update_idletasks()

            dist_app = os.path.join(PROJECT_DIR, "dist", "SoundSync.app")
            if os.path.exists(target_app_path):
                shutil.rmtree(target_app_path)
            shutil.copytree(dist_app, target_app_path)

            self.progress_bar['value'] = 80
            self.status_var.set("Creating shortcuts and launcher...")
            self.update_idletasks()

            # Desktop shortcut
            if self.desktop_shortcut_var.get():
                desktop = os.path.expanduser("~/Desktop")
                if os.path.exists(desktop):
                    shortcut_path = os.path.join(desktop, "SoundSync Multi-Out")
                    try:
                        if os.path.exists(shortcut_path):
                            os.remove(shortcut_path)
                        os.symlink(target_app_path, shortcut_path)
                    except Exception:
                        pass

            self.progress_bar['value'] = 100
            self.status_var.set("Installation complete! Created by Dasaradhi Varma.")
            self.update_idletasks()
            time.sleep(0.5)

            messagebox.showinfo(
                "Installation Successful",
                f"SoundSync Multi-Out has been successfully installed!\n\n"
                f"Location: {target_app_path}\n"
                f"Created by Dasaradhi Varma"
            )

            if self.launch_after_var.get():
                try:
                    subprocess.Popen(["open", target_app_path])
                except Exception:
                    launcher = os.path.join(target_app_path, "Contents", "MacOS", "SoundSync")
                    if os.path.exists(launcher):
                        subprocess.Popen([launcher])

            self.destroy()

        except Exception as e:
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Installation Error", f"Installation failed:\n{e}")
            self.btn_install.config(state="normal")


def run_mac_installer():
    app = SoundSyncMacInstaller()
    app.mainloop()

if __name__ == "__main__":
    run_mac_installer()

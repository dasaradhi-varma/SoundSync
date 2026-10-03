"""
SoundSync Multi-Out - Professional Windows Installer
Created by Dasaradhi Varma
"""

import sys
import os
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "SoundSync Multi-Out"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Dasaradhi Varma"
DEFAULT_INSTALL_SUBDIR = "SoundSync Multi-Out"

def get_bundle_dir():
    """Returns the resource path whether running from source or frozen executable."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_default_program_files():
    """Returns default 64-bit Program Files directory."""
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    return os.path.join(pf, DEFAULT_INSTALL_SUBDIR)

def create_windows_shortcut(target_exe, shortcut_path, working_dir, icon_path):
    """Creates a Windows .lnk shortcut using WScript.Shell."""
    try:
        ps_cmd = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{shortcut_path}')
$s.TargetPath = '{target_exe}'
$s.WorkingDirectory = '{working_dir}'
if (Test-Path '{icon_path}') {{
    $s.IconLocation = '{icon_path},0'
}}
$s.Description = 'SoundSync Multi-Out - Created by Dasaradhi Varma'
$s.Save()
"""
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        return True
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False


class SoundSyncInstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Setup - {APP_NAME}")
        self.geometry("640x480")
        self.resizable(False, False)

        # Set window icon if available
        bundle_dir = get_bundle_dir()
        icon_candidate = os.path.join(bundle_dir, "app_icon.ico")
        if not os.path.exists(icon_candidate):
            icon_candidate = os.path.join(bundle_dir, "payload", "app_icon.ico")
        if os.path.exists(icon_candidate):
            try:
                self.iconbitmap(icon_candidate)
            except Exception:
                pass

        self.configure(bg="#0b0f19")
        self.target_dir_var = tk.StringVar(value=get_default_program_files())
        self.desktop_shortcut_var = tk.BooleanVar(value=True)
        self.startmenu_shortcut_var = tk.BooleanVar(value=True)
        self.launch_app_var = tk.BooleanVar(value=True)

        self.current_step = 1
        self._setup_styles()
        self._build_header()

        self.content_container = tk.Frame(self, bg="#0f172a")
        self.content_container.pack(fill=tk.BOTH, expand=True)

        self._build_footer()
        self._show_step_1_directory()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Installer.Horizontal.TProgressbar',
                        troughcolor='#1e293b',
                        background='#00f2fe',
                        lightcolor='#00f2fe',
                        darkcolor='#4facfe',
                        bordercolor='#1e293b')

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#070a12", height=85)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        top_accent = tk.Frame(header_frame, bg="#00f2fe", height=3)
        top_accent.pack(fill=tk.X, side=tk.TOP)

        info_box = tk.Frame(header_frame, bg="#070a12", padx=20, pady=10)
        info_box.pack(fill=tk.BOTH, expand=True)

        title_lbl = tk.Label(
            info_box,
            text=f"Setup - {APP_NAME}",
            font=("Segoe UI", 13, "bold"),
            fg="#f8fafc",
            bg="#070a12"
        )
        title_lbl.pack(anchor="w")

        author_lbl = tk.Label(
            info_box,
            text=f"Created by {APP_AUTHOR} | Multi-Bluetooth & Sound Endpoint Matrix",
            font=("Segoe UI", 9, "bold"),
            fg="#00f2fe",
            bg="#070a12"
        )
        author_lbl.pack(anchor="w", pady=(2, 0))

        sep = tk.Frame(self, bg="#1e293b", height=1)
        sep.pack(fill=tk.X, side=tk.TOP)

    def _build_footer(self):
        sep = tk.Frame(self, bg="#1e293b", height=1)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

        self.footer_frame = tk.Frame(self, bg="#070a12", height=60, padx=20)
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer_frame.pack_propagate(False)

        author_badge = tk.Label(
            self.footer_frame,
            text=f"Author: {APP_AUTHOR}",
            font=("Segoe UI", 8, "italic"),
            fg="#64748b",
            bg="#070a12"
        )
        author_badge.pack(side=tk.LEFT)

        self.btn_cancel = tk.Button(
            self.footer_frame,
            text="Cancel",
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#cbd5e1",
            activebackground="#334155",
            activeforeground="#ffffff",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.destroy
        )
        self.btn_cancel.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_next = tk.Button(
            self.footer_frame,
            text="Install",
            font=("Segoe UI", 9, "bold"),
            bg="#00f2fe",
            fg="#070a12",
            activebackground="#4facfe",
            activeforeground="#070a12",
            bd=0,
            padx=20,
            pady=6,
            cursor="hand2",
            command=self._on_primary_action
        )
        self.btn_next.pack(side=tk.RIGHT)

    def _clear_content(self):
        for widget in self.content_container.winfo_children():
            widget.destroy()

    def _show_step_1_directory(self):
        self._clear_content()

        container = tk.Frame(self.content_container, bg="#0f172a", padx=28, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        heading = tk.Label(
            container,
            text="Select Destination Location",
            font=("Segoe UI", 12, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        )
        heading.pack(anchor="w")

        sub = tk.Label(
            container,
            text="Where should SoundSync Multi-Out be installed?",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a"
        )
        sub.pack(anchor="w", pady=(2, 10))

        # Prominent Author Credit Banner on Directory Page as requested
        credit_box = tk.Frame(container, bg="#131e33", bd=1, relief="solid", padx=12, pady=8)
        credit_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            credit_box,
            text="★ Developed & Created by Dasaradhi Varma",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#131e33"
        ).pack(anchor="w")

        tk.Label(
            credit_box,
            text="Setup will install the standalone multi-device audio router and system drivers.",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#131e33"
        ).pack(anchor="w")

        # Destination input
        tk.Label(
            container,
            text="Setup will install SoundSync Multi-Out into the following folder:",
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#0f172a"
        ).pack(anchor="w", pady=(4, 6))

        dir_row = tk.Frame(container, bg="#0f172a")
        dir_row.pack(fill=tk.X)

        self.dir_entry = tk.Entry(
            dir_row,
            textvariable=self.target_dir_var,
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#f8fafc",
            insertbackground="#00f2fe",
            relief="flat",
            bd=6
        )
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        browse_btn = tk.Button(
            dir_row,
            text="Browse...",
            font=("Segoe UI", 9),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._on_browse
        )
        browse_btn.pack(side=tk.RIGHT)

        space_lbl = tk.Label(
            container,
            text="At least 40 MB of free disk space is required.",
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#0f172a"
        )
        space_lbl.pack(anchor="w", pady=(4, 16))

        # Shortcuts Options
        tk.Label(
            container,
            text="Select Additional Tasks:",
            font=("Segoe UI", 9, "bold"),
            fg="#e2e8f0",
            bg="#0f172a"
        ).pack(anchor="w", pady=(0, 6))

        cb1 = tk.Checkbutton(
            container,
            text="Create a Desktop shortcut",
            variable=self.desktop_shortcut_var,
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#0f172a",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#38bdf8"
        )
        cb1.pack(anchor="w")

        cb2 = tk.Checkbutton(
            container,
            text="Create a Start Menu program shortcut",
            variable=self.startmenu_shortcut_var,
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#0f172a",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#38bdf8"
        )
        cb2.pack(anchor="w", pady=(2, 0))

    def _on_browse(self):
        current = self.target_dir_var.get()
        init_dir = current if os.path.isdir(current) else r"C:\Program Files"
        chosen = filedialog.askdirectory(
            parent=self,
            title="Select Destination Folder",
            initialdir=init_dir
        )
        if chosen:
            # If user picked a root or parent, append app name
            if not chosen.lower().endswith(DEFAULT_INSTALL_SUBDIR.lower()):
                chosen = os.path.join(chosen, DEFAULT_INSTALL_SUBDIR)
            self.target_dir_var.set(chosen)

    def _on_primary_action(self):
        if self.current_step == 1:
            target_dir = self.target_dir_var.get().strip()
            if not target_dir:
                messagebox.showwarning("Invalid Path", "Please specify a destination folder.")
                return

            # Test permission or fallback to LocalAppData if running un-elevated
            try:
                os.makedirs(target_dir, exist_ok=True)
                test_file = os.path.join(target_dir, ".perm_test")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
            except PermissionError:
                # Offer to install in LocalAppData or run as administrator
                fallback = os.path.join(os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local"), "Programs", DEFAULT_INSTALL_SUBDIR)
                resp = messagebox.askyesno(
                    "Administrator Permission Required",
                    f"Writing to '{target_dir}' requires administrator permissions.\n\n"
                    f"Would you like to install for the current user into:\n{fallback}?"
                )
                if resp:
                    self.target_dir_var.set(fallback)
                    target_dir = fallback
                    os.makedirs(target_dir, exist_ok=True)
                else:
                    return

            self._show_step_2_progress()
            threading.Thread(target=self._perform_installation, daemon=True).start()

        elif self.current_step == 3:
            # Finish & Launch
            if self.launch_app_var.get():
                target_exe = os.path.join(self.target_dir_var.get(), "SoundSync.exe")
                if os.path.exists(target_exe):
                    subprocess.Popen([target_exe], cwd=self.target_dir_var.get())
            self.destroy()

    def _show_step_2_progress(self):
        self.current_step = 2
        self._clear_content()
        self.btn_next.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.DISABLED)

        container = tk.Frame(self.content_container, bg="#0f172a", padx=28, pady=28)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            container,
            text="Installing SoundSync Multi-Out...",
            font=("Segoe UI", 12, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        ).pack(anchor="w")

        self.status_lbl = tk.Label(
            container,
            text="Extracting application files...",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a"
        )
        self.status_lbl.pack(anchor="w", pady=(6, 14))

        self.progress = ttk.Progressbar(container, style='Installer.Horizontal.TProgressbar', mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 20))

        tk.Label(
            container,
            text="★ Created by Dasaradhi Varma",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#0f172a"
        ).pack(anchor="w")

    def _perform_installation(self):
        target_dir = self.target_dir_var.get()
        bundle_dir = get_bundle_dir()

        steps = [
            ("Creating destination directories...", 15),
            ("Copying SoundSync application executable...", 40),
            ("Installing audio icons & metadata...", 65),
            ("Configuring Windows shortcuts...", 85),
            ("Finalizing installation...", 100)
        ]

        try:
            os.makedirs(target_dir, exist_ok=True)
            self._update_prog(steps[0][0], steps[0][1])
            time.sleep(0.3)

            # Determine payload executable source
            exe_src = os.path.join(bundle_dir, "dist", "SoundSync.exe")
            if not os.path.exists(exe_src):
                exe_src = os.path.join(bundle_dir, "payload", "SoundSync.exe")
            if not os.path.exists(exe_src):
                exe_src = os.path.join(bundle_dir, "SoundSync.exe")

            icon_src = os.path.join(bundle_dir, "app_icon.ico")
            if not os.path.exists(icon_src):
                icon_src = os.path.join(bundle_dir, "payload", "app_icon.ico")

            dest_exe = os.path.join(target_dir, "SoundSync.exe")
            dest_icon = os.path.join(target_dir, "app_icon.ico")

            self._update_prog(steps[1][0], steps[1][1])
            if os.path.exists(exe_src):
                shutil.copy2(exe_src, dest_exe)
            else:
                # If building from raw source folder
                shutil.copy2(sys.executable, dest_exe)

            time.sleep(0.3)
            self._update_prog(steps[2][0], steps[2][1])
            if os.path.exists(icon_src):
                shutil.copy2(icon_src, dest_icon)

            time.sleep(0.3)
            self._update_prog(steps[3][0], steps[3][1])

            # Desktop Shortcut
            if self.desktop_shortcut_var.get():
                desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
                # Also check OneDrive desktop
                od_desktop = os.path.join(os.environ["USERPROFILE"], "OneDrive", "Desktop")
                target_desktops = [desktop]
                if os.path.exists(od_desktop):
                    target_desktops.append(od_desktop)

                for d in target_desktops:
                    lnk = os.path.join(d, "SoundSync Multi-Out.lnk")
                    create_windows_shortcut(dest_exe, lnk, target_dir, dest_icon)

            # Start Menu Shortcut
            if self.startmenu_shortcut_var.get():
                appdata = os.environ.get("APPDATA", r"C:\Users\Default\AppData\Roaming")
                programs = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs", APP_NAME)
                os.makedirs(programs, exist_ok=True)
                lnk = os.path.join(programs, "SoundSync Multi-Out.lnk")
                create_windows_shortcut(dest_exe, lnk, target_dir, dest_icon)

            time.sleep(0.3)
            self._update_prog(steps[4][0], steps[4][1])
            time.sleep(0.4)

            self.after(0, self._show_step_3_finish)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Installation Error", f"An error occurred during setup:\n{e}"))
            self.after(0, self.destroy)

    def _update_prog(self, text, val):
        def _set():
            self.status_lbl.config(text=text)
            self.progress['value'] = val
        self.after(0, _set)

    def _show_step_3_finish(self):
        self.current_step = 3
        self._clear_content()

        self.btn_next.config(text="Finish", state=tk.NORMAL)
        self.btn_cancel.pack_forget()

        container = tk.Frame(self.content_container, bg="#0f172a", padx=28, pady=28)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            container,
            text="Installation Completed Successfully! 🎉",
            font=("Segoe UI", 13, "bold"),
            fg="#4ade80",
            bg="#0f172a"
        ).pack(anchor="w")

        tk.Label(
            container,
            text="SoundSync Multi-Out has been installed on your computer.",
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#0f172a"
        ).pack(anchor="w", pady=(4, 14))

        # Destination info box
        info_box = tk.Frame(container, bg="#131e33", bd=1, relief="solid", padx=14, pady=10)
        info_box.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            info_box,
            text=f"Installed Location:\n{self.target_dir_var.get()}",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#131e33",
            justify=tk.LEFT
        ).pack(anchor="w")

        tk.Label(
            info_box,
            text=f"Created by: {APP_AUTHOR}",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#131e33"
        ).pack(anchor="w", pady=(4, 0))

        tk.Checkbutton(
            container,
            text="Launch SoundSync Multi-Out now",
            variable=self.launch_app_var,
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#00f2fe"
        ).pack(anchor="w", pady=(10, 0))


def main():
    app = SoundSyncInstallerApp()
    app.mainloop()

if __name__ == '__main__':
    main()

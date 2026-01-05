"""
SysMon PowerBar Pro v2.0 - Desktop-Integrated System Monitor
Cel Systems 2025

Features:
- Transparente Bar über der Taskleiste
- FIXED MODE: Echte Desktop-Integration (AppBar)
- Fenster überlappen NICHT mehr!
- Einstellungsmenü mit allen Optionen
- Windows Autostart
- Open Source Ready!
"""

import tkinter as tk
from tkinter import ttk, colorchooser
import threading
import time
import sys
import os
import json
import ctypes
from ctypes import wintypes, Structure, POINTER, byref, sizeof, windll, WINFUNCTYPE, c_int, c_uint, c_void_p
from pathlib import Path
import winreg

import psutil

# ============================================================
# Windows AppBar API - Für echte Desktop-Integration!
# ============================================================

# AppBar Messages
ABM_NEW = 0x00000000
ABM_REMOVE = 0x00000001
ABM_QUERYPOS = 0x00000002
ABM_SETPOS = 0x00000003
ABM_GETSTATE = 0x00000004
ABM_GETTASKBARPOS = 0x00000005
ABM_ACTIVATE = 0x00000006
ABM_GETAUTOHIDEBAR = 0x00000007
ABM_SETAUTOHIDEBAR = 0x00000008
ABM_WINDOWPOSCHANGED = 0x00000009
ABM_SETSTATE = 0x0000000a

# AppBar Edges
ABE_LEFT = 0
ABE_TOP = 1
ABE_RIGHT = 2
ABE_BOTTOM = 3

# AppBar Notifications
ABN_STATECHANGE = 0x00000000
ABN_POSCHANGED = 0x00000001
ABN_FULLSCREENAPP = 0x00000002
ABN_WINDOWARRANGE = 0x00000003

# Window Messages
WM_USER = 0x0400
WM_APPBAR_CALLBACK = WM_USER + 1


class RECT(Structure):
    _fields_ = [
        ('left', ctypes.c_long),
        ('top', ctypes.c_long),
        ('right', ctypes.c_long),
        ('bottom', ctypes.c_long)
    ]


class APPBARDATA(Structure):
    _fields_ = [
        ('cbSize', ctypes.c_ulong),
        ('hWnd', ctypes.c_void_p),
        ('uCallbackMessage', ctypes.c_uint),
        ('uEdge', ctypes.c_uint),
        ('rc', RECT),
        ('lParam', ctypes.c_long)
    ]


# Shell32 function
shell32 = ctypes.windll.shell32
SHAppBarMessage = shell32.SHAppBarMessage
SHAppBarMessage.argtypes = [ctypes.c_ulong, POINTER(APPBARDATA)]
SHAppBarMessage.restype = ctypes.c_ulong


class AppBarManager:
    """Manages Windows AppBar registration for desktop integration"""
    
    def __init__(self, hwnd, edge=ABE_BOTTOM, height=26):
        self.hwnd = hwnd
        self.edge = edge
        self.height = height
        self.registered = False
        self.abd = APPBARDATA()
        self.abd.cbSize = sizeof(APPBARDATA)
        self.abd.hWnd = hwnd
    
    def register(self) -> bool:
        """Register as AppBar - Windows will now reserve space for us!"""
        if self.registered:
            return True
        
        self.abd.uCallbackMessage = WM_APPBAR_CALLBACK
        
        result = SHAppBarMessage(ABM_NEW, byref(self.abd))
        if result:
            self.registered = True
            self._set_position()
            print("✅ AppBar registered - Desktop space reserved!")
            return True
        else:
            print("❌ AppBar registration failed")
            return False
    
    def unregister(self) -> bool:
        """Unregister AppBar - release desktop space"""
        if not self.registered:
            return True
        
        result = SHAppBarMessage(ABM_REMOVE, byref(self.abd))
        self.registered = False
        print("✅ AppBar unregistered - Desktop space released")
        return True
    
    def _set_position(self):
        """Set the AppBar position and size"""
        if not self.registered:
            return
        
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
        
        # Get taskbar position first
        taskbar_abd = APPBARDATA()
        taskbar_abd.cbSize = sizeof(APPBARDATA)
        SHAppBarMessage(ABM_GETTASKBARPOS, byref(taskbar_abd))
        
        taskbar_height = taskbar_abd.rc.bottom - taskbar_abd.rc.top
        if taskbar_height < 30:
            taskbar_height = 48  # Default if detection fails
        
        # Set our position
        self.abd.uEdge = self.edge
        
        if self.edge == ABE_BOTTOM:
            self.abd.rc.left = 0
            self.abd.rc.right = screen_width
            self.abd.rc.bottom = screen_height - taskbar_height
            self.abd.rc.top = self.abd.rc.bottom - self.height
        elif self.edge == ABE_TOP:
            self.abd.rc.left = 0
            self.abd.rc.right = screen_width
            self.abd.rc.top = 0
            self.abd.rc.bottom = self.height
        
        # Query position (Windows may adjust)
        SHAppBarMessage(ABM_QUERYPOS, byref(self.abd))
        
        # Adjust based on edge
        if self.edge == ABE_BOTTOM:
            self.abd.rc.top = self.abd.rc.bottom - self.height
        elif self.edge == ABE_TOP:
            self.abd.rc.bottom = self.abd.rc.top + self.height
        
        # Set final position - This reserves the screen space!
        SHAppBarMessage(ABM_SETPOS, byref(self.abd))
        
        return (self.abd.rc.left, self.abd.rc.top, 
                self.abd.rc.right - self.abd.rc.left, 
                self.abd.rc.bottom - self.abd.rc.top)
    
    def get_position(self):
        """Get the current AppBar position"""
        return (self.abd.rc.left, self.abd.rc.top,
                self.abd.rc.right - self.abd.rc.left,
                self.abd.rc.bottom - self.abd.rc.top)
    
    def set_height(self, height):
        """Update AppBar height"""
        self.height = height
        if self.registered:
            self._set_position()
    
    def set_edge(self, edge):
        """Change AppBar edge (top/bottom)"""
        self.edge = edge
        if self.registered:
            self._set_position()


# ============================================================
# NVIDIA Support
# ============================================================

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    GPU_NAME = pynvml.nvmlDeviceGetName(GPU_HANDLE)
    NVIDIA_AVAILABLE = True
    print(f"✅ NVIDIA GPU: {GPU_NAME}")
except Exception as e:
    NVIDIA_AVAILABLE = False
    GPU_HANDLE = None
    GPU_NAME = "N/A"
    print(f"⚠️ No NVIDIA GPU: {e}")


# ============================================================
# Configuration
# ============================================================

CONFIG_DIR = Path.home() / ".sysmon"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "version": "2.0",
    "opacity": 0.90,
    "bar_height": 26,
    "font_size": 9,
    "font_family": "Consolas",
    "bg_color": "#0d0d0d",
    "colors": {
        "cpu": "#00D4FF",
        "ram": "#9B59B6",
        "gpu": "#2ECC71",
        "net": "#F39C12",
        "disk": "#E74C3C",
        "separator": "#2a2a2a",
        "text_dim": "#555555"
    },
    "show_cpu": True,
    "show_ram": True,
    "show_gpu": True,
    "show_net": True,
    "show_disk": True,
    "use_celsius": False,  # Fahrenheit as default
    "autostart": False,
    "dock_position": "bottom",
    "update_interval": 1.0,
    "fixed_mode": False,  # NEW: AppBar mode
    "show_labels": True,  # Show "CPU:", "RAM:" etc.
}


def load_config():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(saved)
                if "colors" in saved:
                    config["colors"] = DEFAULT_CONFIG["colors"].copy()
                    config["colors"].update(saved["colors"])
                return config
    except Exception as e:
        print(f"⚠️ Config load error: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ Config saved")
    except Exception as e:
        print(f"❌ Config save error: {e}")


def get_taskbar_height():
    try:
        work_area = RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, byref(work_area), 0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
        return max(screen_height - work_area.bottom, 48)
    except:
        return 48


def set_autostart(enable: bool):
    app_path = os.path.abspath(sys.argv[0])
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            batch_path = CONFIG_DIR / "autostart_powerbar.bat"
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(batch_path, 'w') as f:
                venv_path = Path(app_path).parent / "venv" / "Scripts" / "pythonw.exe"
                if venv_path.exists():
                    f.write(f'@echo off\nstart "" "{venv_path}" "{app_path}"\n')
                else:
                    f.write(f'@echo off\nstart "" pythonw "{app_path}"\n')
            
            winreg.SetValueEx(key, "SysMonPowerBar", 0, winreg.REG_SZ, str(batch_path))
        else:
            try:
                winreg.DeleteValue(key, "SysMonPowerBar")
            except FileNotFoundError:
                pass
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"❌ Autostart error: {e}")
        return False


def check_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, "SysMonPowerBar")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except:
        return False


# ============================================================
# Settings Window
# ============================================================

class SettingsWindow(tk.Toplevel):
    """Settings window"""
    
    def __init__(self, parent, config, on_save_callback):
        super().__init__(parent)
        
        self.parent = parent
        self.config = config.copy()
        self.config["colors"] = config["colors"].copy()
        self.on_save = on_save_callback
        
        self.title("⚙ SysMon PowerBar Pro - Settings")
        self.geometry("480x650")
        self.resizable(False, False)
        self.configure(bg="#1a1a1a")
        
        self.transient(parent)
        self.grab_set()
        
        self._create_ui()
        
        # Position
        self.update_idletasks()
        x = parent.winfo_x() + 50
        y = parent.winfo_y() - self.winfo_height() - 10
        if y < 0:
            y = 50
        self.geometry(f"+{x}+{y}")
    
    def _create_ui(self):
        main = tk.Frame(self, bg="#1a1a1a", padx=20, pady=15)
        main.pack(fill="both", expand=True)
        
        # Title
        title_frame = tk.Frame(main, bg="#1a1a1a")
        title_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(title_frame, text="⚙", font=("Segoe UI", 20),
                fg="#00D4FF", bg="#1a1a1a").pack(side="left")
        tk.Label(title_frame, text=" PowerBar Pro Settings", font=("Segoe UI", 16, "bold"),
                fg="white", bg="#1a1a1a").pack(side="left")
        
        # Notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background="#1a1a1a", borderwidth=0)
        style.configure("TNotebook.Tab", background="#2a2a2a", foreground="white",
                       padding=[15, 8], font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", "#00D4FF")],
                 foreground=[("selected", "black")])
        
        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True, pady=(0, 15))
        
        # === Appearance Tab ===
        appearance = tk.Frame(notebook, bg="#1a1a1a", padx=15, pady=15)
        notebook.add(appearance, text=" 🎨 Appearance ")
        
        self._create_slider(appearance, "Transparency:", "opacity", 0.5, 1.0)
        self._create_slider(appearance, "Height (px):", "bar_height", 20, 40)
        self._create_slider(appearance, "Font Size:", "font_size", 8, 14)
        self._create_color_picker(appearance, "Background:", "bg_color")
        
        # === Colors Tab ===
        colors = tk.Frame(notebook, bg="#1a1a1a", padx=15, pady=15)
        notebook.add(colors, text=" 🌈 Colors ")
        
        for label, key in [("CPU:", "cpu"), ("RAM:", "ram"), ("GPU:", "gpu"),
                          ("Network:", "net"), ("Disk:", "disk")]:
            self._create_color_picker(colors, label, f"colors.{key}")
        
        # === Display Tab ===
        display = tk.Frame(notebook, bg="#1a1a1a", padx=15, pady=15)
        notebook.add(display, text=" 📊 Display ")
        
        self.show_vars = {}
        for label, key in [("Show CPU", "show_cpu"), ("Show RAM", "show_ram"),
                          ("Show GPU", "show_gpu"), ("Show Network", "show_net"),
                          ("Show Disk", "show_disk"),
                          ("Show Labels (CPU:, RAM:, ...)", "show_labels"),
                          ("Temperature in Celsius", "use_celsius")]:
            var = tk.BooleanVar(value=self.config.get(key, True))
            self.show_vars[key] = var
            cb = tk.Checkbutton(display, text=label, variable=var,
                               bg="#1a1a1a", fg="white", selectcolor="#2a2a2a",
                               activebackground="#1a1a1a", activeforeground="white",
                               font=("Segoe UI", 10))
            cb.pack(anchor="w", pady=3)
        
        # Update interval
        interval_frame = tk.Frame(display, bg="#1a1a1a")
        interval_frame.pack(fill="x", pady=(15, 0))
        tk.Label(interval_frame, text="Update Interval (sec):",
                fg="white", bg="#1a1a1a", font=("Segoe UI", 10)).pack(side="left")
        self.interval_var = tk.DoubleVar(value=self.config.get("update_interval", 1.0))
        tk.Spinbox(interval_frame, from_=0.5, to=5.0, increment=0.5,
                  textvariable=self.interval_var, width=5,
                  bg="#2a2a2a", fg="white", font=("Segoe UI", 10)).pack(side="right")
        
        # === System Tab ===
        system = tk.Frame(notebook, bg="#1a1a1a", padx=15, pady=15)
        notebook.add(system, text=" ⚡ System ")
        
        # FIXED MODE - The star feature!
        fixed_frame = tk.Frame(system, bg="#252525", padx=15, pady=15)
        fixed_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(fixed_frame, text="🔒 Fixed Mode", font=("Segoe UI", 11, "bold"),
                fg="#00D4FF", bg="#252525").pack(anchor="w")
        tk.Label(fixed_frame, text="Reserves screen space - windows won't overlap anymore!",
                font=("Segoe UI", 9), fg="#888888", bg="#252525").pack(anchor="w", pady=(2, 8))
        
        self.fixed_var = tk.BooleanVar(value=self.config.get("fixed_mode", False))
        fixed_cb = tk.Checkbutton(fixed_frame, text="Enable Fixed Mode",
                                  variable=self.fixed_var,
                                  bg="#252525", fg="white", selectcolor="#333333",
                                  activebackground="#252525", activeforeground="white",
                                  font=("Segoe UI", 10, "bold"))
        fixed_cb.pack(anchor="w")
        
        # Autostart
        self.autostart_var = tk.BooleanVar(value=check_autostart())
        tk.Checkbutton(system, text="Start with Windows", variable=self.autostart_var,
                      bg="#1a1a1a", fg="white", selectcolor="#2a2a2a",
                      activebackground="#1a1a1a", activeforeground="white",
                      font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))
        
        # Dock position
        dock_frame = tk.Frame(system, bg="#1a1a1a")
        dock_frame.pack(fill="x", pady=(5, 0))
        tk.Label(dock_frame, text="Position:", fg="white", bg="#1a1a1a",
                font=("Segoe UI", 10)).pack(side="left")
        
        self.dock_var = tk.StringVar(value=self.config.get("dock_position", "bottom"))
        for text, value in [("⬇ Bottom", "bottom"), ("⬆ Top", "top")]:
            tk.Radiobutton(dock_frame, text=text, variable=self.dock_var, value=value,
                          bg="#1a1a1a", fg="white", selectcolor="#2a2a2a",
                          activebackground="#1a1a1a", activeforeground="white",
                          font=("Segoe UI", 10)).pack(side="left", padx=(15, 0))
        
        # Info box
        info = tk.Frame(system, bg="#1e3a4a", padx=15, pady=12)
        info.pack(fill="x", pady=(20, 0))
        
        tk.Label(info, text="SysMon PowerBar Pro v2.0", font=("Segoe UI", 11, "bold"),
                fg="#00D4FF", bg="#1e3a4a").pack(anchor="w")
        tk.Label(info, text="bitmagix © 2025 | Open Source", font=("Segoe UI", 9),
                fg="#88ccee", bg="#1e3a4a").pack(anchor="w")
        tk.Label(info, text=f"GPU: {GPU_NAME}", font=("Segoe UI", 9),
                fg="#668899", bg="#1e3a4a").pack(anchor="w", pady=(5, 0))
        
        # === Buttons ===
        btn_frame = tk.Frame(main, bg="#1a1a1a")
        btn_frame.pack(fill="x", pady=(10, 0))
        
        tk.Button(btn_frame, text="Reset", command=self._reset,
                 bg="#333333", fg="white", font=("Segoe UI", 10),
                 relief="flat", padx=15, pady=8, cursor="hand2").pack(side="left")
        
        tk.Button(btn_frame, text="Cancel", command=self.destroy,
                 bg="#333333", fg="white", font=("Segoe UI", 10),
                 relief="flat", padx=15, pady=8, cursor="hand2").pack(side="right", padx=(10, 0))
        
        tk.Button(btn_frame, text="💾 Save", command=self._save,
                 bg="#00D4FF", fg="black", font=("Segoe UI", 10, "bold"),
                 relief="flat", padx=20, pady=8, cursor="hand2").pack(side="right")
    
    def _create_slider(self, parent, label, key, min_val, max_val):
        frame = tk.Frame(parent, bg="#1a1a1a")
        frame.pack(fill="x", pady=8)
        
        tk.Label(frame, text=label, fg="white", bg="#1a1a1a",
                font=("Segoe UI", 10), width=15, anchor="w").pack(side="left")
        
        val = self.config.get(key, min_val)
        var = tk.DoubleVar(value=val)
        setattr(self, f"{key}_var", var)
        
        resolution = 0.05 if max_val <= 1 else 1
        tk.Scale(frame, from_=min_val, to=max_val, orient="horizontal",
                variable=var, bg="#2a2a2a", fg="white", troughcolor="#333333",
                highlightthickness=0, length=220, resolution=resolution,
                font=("Segoe UI", 8)).pack(side="right")
    
    def _create_color_picker(self, parent, label, key):
        frame = tk.Frame(parent, bg="#1a1a1a")
        frame.pack(fill="x", pady=6)
        
        tk.Label(frame, text=label, fg="white", bg="#1a1a1a",
                font=("Segoe UI", 10), width=15, anchor="w").pack(side="left")
        
        if "." in key:
            parts = key.split(".")
            color = self.config[parts[0]][parts[1]]
        else:
            color = self.config.get(key, "#ffffff")
        
        btn = tk.Button(frame, text="", bg=color, width=10, height=1,
                       relief="flat", cursor="hand2")
        btn.pack(side="right")
        
        def pick():
            result = colorchooser.askcolor(color=color, title=f"Farbe: {label}")
            if result[1]:
                btn.configure(bg=result[1])
                if "." in key:
                    parts = key.split(".")
                    self.config[parts[0]][parts[1]] = result[1]
                else:
                    self.config[key] = result[1]
        
        btn.configure(command=pick)
    
    def _reset(self):
        self.config = DEFAULT_CONFIG.copy()
        self.config["colors"] = DEFAULT_CONFIG["colors"].copy()
        self.destroy()
        SettingsWindow(self.parent, self.config, self.on_save)
    
    def _save(self):
        self.config["opacity"] = self.opacity_var.get()
        self.config["bar_height"] = int(self.bar_height_var.get())
        self.config["font_size"] = int(self.font_size_var.get())
        self.config["update_interval"] = self.interval_var.get()
        self.config["dock_position"] = self.dock_var.get()
        self.config["fixed_mode"] = self.fixed_var.get()
        
        for key, var in self.show_vars.items():
            self.config[key] = var.get()
        
        set_autostart(self.autostart_var.get())
        self.config["autostart"] = self.autostart_var.get()
        
        save_config(self.config)
        self.on_save(self.config)
        self.destroy()


# ============================================================
# Main PowerBar
# ============================================================

class PowerBar(tk.Tk):
    """PowerBar Pro with AppBar support"""
    
    def __init__(self):
        super().__init__()
        
        self.config = load_config()
        
        # Stats
        self.cpu_percent = 0.0
        self.ram_percent = 0.0
        self.ram_used = 0.0
        self.ram_total = 0.0
        self.gpu_percent = 0.0
        self.gpu_temp = None
        self.vram_used = 0.0
        self.vram_total = 0.0
        self.net_up = 0.0
        self.net_down = 0.0
        self.disk_read = 0.0
        self.disk_write = 0.0
        
        self._last_net = psutil.net_io_counters()
        self._last_disk = psutil.disk_io_counters()
        self._last_time = time.time()
        
        # State
        self.is_collapsed = False
        self.running = True
        self.settings_window = None
        self.appbar = None
        
        # Setup
        self._setup_window()
        self._create_ui()
        
        # Apply fixed mode if enabled
        if self.config.get("fixed_mode", False):
            self.after(500, self._enable_fixed_mode)
        
        # Start updates
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        
        # Bindings
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Button-3>", self._show_menu)
        self.bind("<Double-Button-1>", self._toggle_collapse)
        
        # Drag (only if not fixed)
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
    
    def _get_hwnd(self):
        """Get native window handle"""
        return int(self.wm_frame(), 16)
    
    def _enable_fixed_mode(self):
        """Enable AppBar fixed mode"""
        if self.appbar and self.appbar.registered:
            return
        
        hwnd = self._get_hwnd()
        edge = ABE_TOP if self.config.get("dock_position") == "top" else ABE_BOTTOM
        height = self.config.get("bar_height", 26)
        
        self.appbar = AppBarManager(hwnd, edge, height)
        
        if self.appbar.register():
            # Move window to AppBar position
            pos = self.appbar.get_position()
            self.geometry(f"{pos[2]}x{pos[3]}+{pos[0]}+{pos[1]}")
            print("🔒 Fixed Mode ENABLED - Windows won't overlap!")
    
    def _disable_fixed_mode(self):
        """Disable AppBar fixed mode"""
        if self.appbar:
            self.appbar.unregister()
            self.appbar = None
            print("🔓 Fixed Mode DISABLED")
    
    def _setup_window(self):
        self.overrideredirect(True)
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        taskbar_height = get_taskbar_height()
        
        self.bar_height = self.config.get("bar_height", 26)
        self.bar_width = screen_width
        
        # Wenn Fixed Mode aktiv, übernimmt AppBar die Positionierung
        if self.config.get("fixed_mode") and self.appbar and self.appbar.registered:
            pos = self.appbar.get_position()
            self.geometry(f"{pos[2]}x{pos[3]}+{pos[0]}+{pos[1]}")
        else:
            # Normal mode - Position berechnen
            if self.config.get("dock_position") == "top":
                y = 0
            else:
                y = screen_height - taskbar_height - self.bar_height
            
            self.geometry(f"{self.bar_width}x{self.bar_height}+0+{y}")
        
        self.attributes("-topmost", True)
        self.attributes("-alpha", self.config.get("opacity", 0.90))
        self.configure(bg=self.config.get("bg_color", "#0d0d0d"))
    
    def _create_ui(self):
        colors = self.config.get("colors", DEFAULT_CONFIG["colors"])
        font_size = self.config.get("font_size", 9)
        bg = self.config.get("bg_color", "#0d0d0d")
        show_labels = self.config.get("show_labels", True)
        
        self.container = tk.Frame(self, bg=bg)
        self.container.pack(fill="both", expand=True)
        
        # Collapse button
        self.collapse_btn = tk.Label(self.container, text="◀", font=("Segoe UI", 9),
                                     fg=colors["text_dim"], bg=bg, cursor="hand2")
        self.collapse_btn.pack(side="left", padx=(8, 12))
        self.collapse_btn.bind("<Button-1>", self._toggle_collapse)
        
        # Fixed mode indicator
        if self.config.get("fixed_mode"):
            tk.Label(self.container, text="🔒", font=("Segoe UI", 8),
                    fg="#00D4FF", bg=bg).pack(side="left", padx=(0, 8))
        
        # Stats frame
        self.stats_frame = tk.Frame(self.container, bg=bg)
        self.stats_frame.pack(side="left", fill="both", expand=True)
        
        font = ("Consolas", font_size)
        sep = colors["separator"]
        
        def add_sep():
            tk.Label(self.stats_frame, text="│", fg=sep, bg=bg, font=font).pack(side="left", padx=6)
        
        # CPU
        if self.config.get("show_cpu", True):
            lbl = "CPU: " if show_labels else ""
            self.cpu_label = tk.Label(self.stats_frame, text=f"{lbl}--%", font=font,
                                      fg=colors["cpu"], bg=bg)
            self.cpu_label.pack(side="left")
            add_sep()
        
        # RAM
        if self.config.get("show_ram", True):
            lbl = "RAM: " if show_labels else ""
            self.ram_label = tk.Label(self.stats_frame, text=f"{lbl}--%", font=font,
                                      fg=colors["ram"], bg=bg)
            self.ram_label.pack(side="left")
            add_sep()
        
        # GPU
        if self.config.get("show_gpu", True) and NVIDIA_AVAILABLE:
            lbl = "GPU: " if show_labels else ""
            self.gpu_label = tk.Label(self.stats_frame, text=f"{lbl}--% │ VRAM: --/--GB │ --°C",
                                      font=font, fg=colors["gpu"], bg=bg)
            self.gpu_label.pack(side="left")
            add_sep()
        
        # Network
        if self.config.get("show_net", True):
            lbl = "NET: " if show_labels else ""
            self.net_label = tk.Label(self.stats_frame, text=f"{lbl}↓-- ↑--", font=font,
                                      fg=colors["net"], bg=bg)
            self.net_label.pack(side="left")
            add_sep()
        
        # Disk
        if self.config.get("show_disk", True):
            lbl = "DISK: " if show_labels else ""
            self.disk_label = tk.Label(self.stats_frame, text=f"{lbl}R:-- W:--", font=font,
                                       fg=colors["disk"], bg=bg)
            self.disk_label.pack(side="left")
        
        # Right buttons
        dim = colors["text_dim"]
        
        self.close_btn = tk.Label(self.container, text="✕", font=("Segoe UI", 11),
                                  fg=dim, bg=bg, cursor="hand2")
        self.close_btn.pack(side="right", padx=(5, 10))
        self.close_btn.bind("<Button-1>", lambda e: self._on_close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(fg="#FF4444"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(fg=dim))
        
        self.settings_btn = tk.Label(self.container, text="⚙", font=("Segoe UI", 11),
                                     fg=dim, bg=bg, cursor="hand2")
        self.settings_btn.pack(side="right", padx=5)
        self.settings_btn.bind("<Button-1>", self._open_settings)
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.config(fg="#00D4FF"))
        self.settings_btn.bind("<Leave>", lambda e: self.settings_btn.config(fg=dim))
    
    def _start_drag(self, event):
        if not self.config.get("fixed_mode"):
            self._drag_x = event.x
            self._drag_y = event.y
    
    def _on_drag(self, event):
        if not self.config.get("fixed_mode"):
            x = self.winfo_x() + (event.x - self._drag_x)
            y = self.winfo_y() + (event.y - self._drag_y)
            self.geometry(f"+{x}+{y}")
    
    def _toggle_collapse(self, event=None):
        self.is_collapsed = not self.is_collapsed
        
        if self.is_collapsed:
            self.stats_frame.pack_forget()
            self.collapse_btn.config(text="▶")
            self.geometry(f"100x{self.bar_height}")
        else:
            self.stats_frame.pack(side="left", fill="both", expand=True)
            self.collapse_btn.config(text="◀")
            self.geometry(f"{self.bar_width}x{self.bar_height}")
    
    def _open_settings(self, event=None):
        if not self.settings_window or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self, self.config, self._apply_settings)
    
    def _apply_settings(self, new_config):
        old_fixed = self.config.get("fixed_mode", False)
        new_fixed = new_config.get("fixed_mode", False)
        
        self.config = new_config
        
        # Recreate UI first
        self.container.destroy()
        self._setup_window()
        self._create_ui()
        
        # Handle fixed mode change AFTER window setup
        if new_fixed and not old_fixed:
            self.after(100, self._enable_fixed_mode)
        elif not new_fixed and old_fixed:
            self._disable_fixed_mode()
        elif new_fixed and self.appbar:
            # Update AppBar position/height
            edge = ABE_TOP if new_config.get("dock_position") == "top" else ABE_BOTTOM
            self.appbar.set_edge(edge)
            self.appbar.set_height(new_config.get("bar_height", 26))
            pos = self.appbar.get_position()
            self.geometry(f"{pos[2]}x{pos[3]}+{pos[0]}+{pos[1]}")
    
    def _show_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg="#2a2a2a", fg="white",
                      activebackground="#00D4FF", activeforeground="black")
        
        menu.add_command(label="⚙ Settings", command=self._open_settings)
        menu.add_separator()
        
        fixed = self.config.get("fixed_mode", False)
        menu.add_command(
            label="🔓 Disable Fixed Mode" if fixed else "🔒 Enable Fixed Mode",
            command=self._toggle_fixed_mode
        )
        menu.add_separator()
        menu.add_command(label="✕ Exit", command=self._on_close)
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _toggle_fixed_mode(self):
        self.config["fixed_mode"] = not self.config.get("fixed_mode", False)
        
        if self.config["fixed_mode"]:
            self._enable_fixed_mode()
        else:
            self._disable_fixed_mode()
        
        save_config(self.config)
        
        # Recreate UI to show/hide lock icon
        self.container.destroy()
        self._create_ui()
    
    def _format_temp(self, temp):
        if temp is None:
            return "--"
        if self.config.get("use_celsius", True):
            return f"{temp:.0f}°C"
        return f"{temp * 9/5 + 32:.0f}°F"
    
    def _get_color(self, value, key):
        if value > 90:
            return "#FF4444"
        elif value > 75:
            return "#FFAA00"
        return self.config.get("colors", {}).get(key, "#FFFFFF")
    
    def _update_stats(self):
        current = time.time()
        delta = max(current - self._last_time, 0.1)
        
        self.cpu_percent = psutil.cpu_percent(interval=None)
        
        mem = psutil.virtual_memory()
        self.ram_percent = mem.percent
        self.ram_used = mem.used / (1024**3)
        self.ram_total = mem.total / (1024**3)
        
        if NVIDIA_AVAILABLE and GPU_HANDLE:
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE)
                self.gpu_percent = util.gpu
                self.gpu_temp = pynvml.nvmlDeviceGetTemperature(GPU_HANDLE, pynvml.NVML_TEMPERATURE_GPU)
                info = pynvml.nvmlDeviceGetMemoryInfo(GPU_HANDLE)
                self.vram_used = info.used / (1024**3)
                self.vram_total = info.total / (1024**3)
            except:
                pass
        
        try:
            net = psutil.net_io_counters()
            self.net_down = (net.bytes_recv - self._last_net.bytes_recv) / delta / 1024
            self.net_up = (net.bytes_sent - self._last_net.bytes_sent) / delta / 1024
            self._last_net = net
        except:
            pass
        
        try:
            disk = psutil.disk_io_counters()
            self.disk_read = (disk.read_bytes - self._last_disk.read_bytes) / delta / (1024**2)
            self.disk_write = (disk.write_bytes - self._last_disk.write_bytes) / delta / (1024**2)
            self._last_disk = disk
        except:
            pass
        
        self._last_time = current
    
    def _update_ui(self):
        if self.is_collapsed:
            return
        
        show_labels = self.config.get("show_labels", True)
        
        if hasattr(self, 'cpu_label'):
            lbl = "CPU: " if show_labels else ""
            self.cpu_label.config(text=f"{lbl}{self.cpu_percent:4.0f}%",
                                 fg=self._get_color(self.cpu_percent, "cpu"))
        
        if hasattr(self, 'ram_label'):
            lbl = "RAM: " if show_labels else ""
            self.ram_label.config(text=f"{lbl}{self.ram_percent:4.0f}% ({self.ram_used:.0f}/{self.ram_total:.0f}GB)",
                                 fg=self._get_color(self.ram_percent, "ram"))
        
        if hasattr(self, 'gpu_label') and NVIDIA_AVAILABLE:
            lbl = "GPU: " if show_labels else ""
            vram_pct = (self.vram_used / self.vram_total * 100) if self.vram_total > 0 else 0
            self.gpu_label.config(
                text=f"{lbl}{self.gpu_percent:3.0f}% │ VRAM: {self.vram_used:.1f}/{self.vram_total:.0f}GB │ {self._format_temp(self.gpu_temp)}",
                fg=self._get_color(max(self.gpu_percent, vram_pct), "gpu"))
        
        if hasattr(self, 'net_label'):
            lbl = "NET: " if show_labels else ""
            self.net_label.config(text=f"{lbl}↓{self.net_down:5.0f} ↑{self.net_up:5.0f} KB/s")
        
        if hasattr(self, 'disk_label'):
            lbl = "DISK: " if show_labels else ""
            self.disk_label.config(text=f"{lbl}R:{self.disk_read:4.1f} W:{self.disk_write:4.1f} MB/s")
    
    def _update_loop(self):
        while self.running:
            try:
                self._update_stats()
                self.after(0, self._update_ui)
            except:
                pass
            time.sleep(self.config.get("update_interval", 1.0))
    
    def _on_close(self):
        print("👋 PowerBar closed")
        self.running = False
        
        # Unregister AppBar
        if self.appbar:
            self.appbar.unregister()
        
        save_config(self.config)
        
        if NVIDIA_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
        
        self.destroy()


def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ███████╗██╗   ██╗███████╗███╗   ███╗ ██████╗ ███╗   ██╗    ║
║   ██╔════╝╚██╗ ██╔╝██╔════╝████╗ ████║██╔═══██╗████╗  ██║    ║
║   ███████╗ ╚████╔╝ ███████╗██╔████╔██║██║   ██║██╔██╗ ██║    ║
║   ╚════██║  ╚██╔╝  ╚════██║██║╚██╔╝██║██║   ██║██║╚██╗██║    ║
║   ███████║   ██║   ███████║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║    ║
║   ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝    ║
║                                                               ║
║   PowerBar Pro v2.0 - bitmagix 2025                          ║
║   Desktop-Integrated System Monitor for Windows 11            ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║   🔒 Fixed Mode - Windows auto-resize, no overlap!           ║
║   ⚙  Click gear icon for Settings                             ║
║   🖱  Right-click for quick menu                               ║
║   ✋  Drag to move (when not fixed)                            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    app = PowerBar()
    app.mainloop()


if __name__ == "__main__":
    main()

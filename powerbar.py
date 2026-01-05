"""
SysMon PowerBar - Angedockte System-Statusleiste
Cel Systems 2025

Eine schlanke Statusbar die sich direkt über die Windows Taskbar legt!
"""

import tkinter as tk
from tkinter import font as tkfont
import threading
import time
import sys
import ctypes
from ctypes import wintypes

import psutil

# NVIDIA support
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


# Windows API für Taskbar-Höhe
def get_taskbar_height():
    """Get Windows taskbar height"""
    try:
        user32 = ctypes.windll.user32
        
        # Get work area (screen minus taskbar)
        class RECT(ctypes.Structure):
            _fields_ = [
                ('left', ctypes.c_long),
                ('top', ctypes.c_long),
                ('right', ctypes.c_long),
                ('bottom', ctypes.c_long)
            ]
        
        work_area = RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(work_area), 0)  # SPI_GETWORKAREA
        
        screen_height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        taskbar_height = screen_height - work_area.bottom
        
        return max(taskbar_height, 48)  # Minimum 48px
    except:
        return 48


class PowerBar(tk.Tk):
    """Angedockte System-Statusleiste"""
    
    def __init__(self):
        super().__init__()
        
        # Stats
        self.cpu_percent = 0.0
        self.cpu_temp = None
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
        
        # Settings
        self.use_celsius = True
        self.is_collapsed = False
        self.running = True
        
        # Window setup
        self._setup_window()
        self._create_ui()
        
        # Start update thread
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        
        # Bind events
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Button-3>", self._show_context_menu)  # Right click
        self.bind("<Double-Button-1>", self._toggle_collapse)  # Double click to collapse
    
    def _setup_window(self):
        """Configure window properties"""
        # Remove window decorations
        self.overrideredirect(True)
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        taskbar_height = get_taskbar_height()
        
        # Bar dimensions
        self.bar_height = 24
        self.bar_width = screen_width
        
        # Position directly above taskbar
        x = 0
        y = screen_height - taskbar_height - self.bar_height
        
        self.geometry(f"{self.bar_width}x{self.bar_height}+{x}+{y}")
        
        # Always on top
        self.attributes("-topmost", True)
        
        # Slight transparency
        self.attributes("-alpha", 0.95)
        
        # Dark background
        self.configure(bg="#1a1a1a")
        
        # Make window click-through for areas without widgets? No, we want interaction
        # But we do want to be able to drag it
        self._drag_data = {"x": 0, "y": 0, "dragging": False}
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._stop_drag)
    
    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["dragging"] = True
    
    def _on_drag(self, event):
        if self._drag_data["dragging"]:
            x = self.winfo_x() + (event.x - self._drag_data["x"])
            y = self.winfo_y() + (event.y - self._drag_data["y"])
            self.geometry(f"+{x}+{y}")
    
    def _stop_drag(self, event):
        self._drag_data["dragging"] = False
    
    def _create_ui(self):
        """Create the status bar UI"""
        # Main container
        self.container = tk.Frame(self, bg="#1a1a1a", height=self.bar_height)
        self.container.pack(fill="both", expand=True)
        
        # Left side: Collapse button
        self.collapse_btn = tk.Label(
            self.container,
            text="◀",
            font=("Segoe UI", 9),
            fg="#666666",
            bg="#1a1a1a",
            cursor="hand2"
        )
        self.collapse_btn.pack(side="left", padx=(5, 10))
        self.collapse_btn.bind("<Button-1>", self._toggle_collapse)
        
        # Stats frame
        self.stats_frame = tk.Frame(self.container, bg="#1a1a1a")
        self.stats_frame.pack(side="left", fill="both", expand=True)
        
        # Create stat labels with colors
        label_font = ("Consolas", 9)
        
        # CPU
        self.cpu_label = tk.Label(
            self.stats_frame,
            text="CPU: --% | --°C",
            font=label_font,
            fg="#00D4FF",
            bg="#1a1a1a"
        )
        self.cpu_label.pack(side="left", padx=(0, 15))
        
        # Separator
        tk.Label(self.stats_frame, text="|", fg="#333333", bg="#1a1a1a", font=label_font).pack(side="left", padx=5)
        
        # RAM
        self.ram_label = tk.Label(
            self.stats_frame,
            text="RAM: --%",
            font=label_font,
            fg="#9B59B6",
            bg="#1a1a1a"
        )
        self.ram_label.pack(side="left", padx=(0, 15))
        
        # Separator
        tk.Label(self.stats_frame, text="|", fg="#333333", bg="#1a1a1a", font=label_font).pack(side="left", padx=5)
        
        # GPU
        self.gpu_label = tk.Label(
            self.stats_frame,
            text="GPU: --% | VRAM: --/--GB | --°C",
            font=label_font,
            fg="#2ECC71",
            bg="#1a1a1a"
        )
        self.gpu_label.pack(side="left", padx=(0, 15))
        
        # Separator
        tk.Label(self.stats_frame, text="|", fg="#333333", bg="#1a1a1a", font=label_font).pack(side="left", padx=5)
        
        # Network
        self.net_label = tk.Label(
            self.stats_frame,
            text="NET: ↓-- ↑-- KB/s",
            font=label_font,
            fg="#F39C12",
            bg="#1a1a1a"
        )
        self.net_label.pack(side="left", padx=(0, 15))
        
        # Separator
        tk.Label(self.stats_frame, text="|", fg="#333333", bg="#1a1a1a", font=label_font).pack(side="left", padx=5)
        
        # Disk
        self.disk_label = tk.Label(
            self.stats_frame,
            text="DISK: R:-- W:-- MB/s",
            font=label_font,
            fg="#E74C3C",
            bg="#1a1a1a"
        )
        self.disk_label.pack(side="left", padx=(0, 15))
        
        # Right side: Close button
        self.close_btn = tk.Label(
            self.container,
            text="✕",
            font=("Segoe UI", 10),
            fg="#666666",
            bg="#1a1a1a",
            cursor="hand2"
        )
        self.close_btn.pack(side="right", padx=(10, 5))
        self.close_btn.bind("<Button-1>", lambda e: self._on_close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(fg="#FF4444"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(fg="#666666"))
        
        # Settings button
        self.settings_btn = tk.Label(
            self.container,
            text="⚙",
            font=("Segoe UI", 10),
            fg="#666666",
            bg="#1a1a1a",
            cursor="hand2"
        )
        self.settings_btn.pack(side="right", padx=5)
        self.settings_btn.bind("<Button-1>", self._toggle_temp_unit)
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.config(fg="#00D4FF"))
        self.settings_btn.bind("<Leave>", lambda e: self.settings_btn.config(fg="#666666"))
        
        # Temp unit indicator
        self.temp_unit_label = tk.Label(
            self.container,
            text="°C",
            font=("Segoe UI", 8),
            fg="#444444",
            bg="#1a1a1a"
        )
        self.temp_unit_label.pack(side="right", padx=(0, 5))
    
    def _toggle_collapse(self, event=None):
        """Toggle collapsed state"""
        self.is_collapsed = not self.is_collapsed
        
        if self.is_collapsed:
            # Collapse to small width
            self.stats_frame.pack_forget()
            self.collapse_btn.config(text="▶")
            self.geometry(f"80x{self.bar_height}")
        else:
            # Expand
            self.stats_frame.pack(side="left", fill="both", expand=True)
            self.collapse_btn.config(text="◀")
            self.geometry(f"{self.bar_width}x{self.bar_height}")
    
    def _toggle_temp_unit(self, event=None):
        """Toggle temperature unit"""
        self.use_celsius = not self.use_celsius
        self.temp_unit_label.config(text="°C" if self.use_celsius else "°F")
    
    def _show_context_menu(self, event):
        """Show right-click context menu"""
        menu = tk.Menu(self, tearoff=0, bg="#2a2a2a", fg="white", 
                      activebackground="#00D4FF", activeforeground="black")
        menu.add_command(label="Toggle °C/°F", command=self._toggle_temp_unit)
        menu.add_separator()
        menu.add_command(label="Dock to Bottom", command=self._dock_bottom)
        menu.add_command(label="Dock to Top", command=self._dock_top)
        menu.add_separator()
        menu.add_command(label="Exit", command=self._on_close)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _dock_bottom(self):
        """Dock bar to bottom of screen"""
        screen_height = self.winfo_screenheight()
        taskbar_height = get_taskbar_height()
        y = screen_height - taskbar_height - self.bar_height
        self.geometry(f"+0+{y}")
    
    def _dock_top(self):
        """Dock bar to top of screen"""
        self.geometry(f"+0+0")
    
    def _format_temp(self, temp):
        """Format temperature"""
        if temp is None:
            return "--"
        if self.use_celsius:
            return f"{temp:.0f}°C"
        else:
            return f"{temp * 9/5 + 32:.0f}°F"
    
    def _get_color_for_value(self, value, base_color):
        """Get color based on value (changes to warning colors at high usage)"""
        if value > 90:
            return "#FF4444"  # Red
        elif value > 75:
            return "#FFAA00"  # Orange
        return base_color
    
    def _update_stats(self):
        """Update system statistics"""
        current_time = time.time()
        time_delta = max(current_time - self._last_time, 0.1)
        
        # CPU
        self.cpu_percent = psutil.cpu_percent(interval=None)
        
        # RAM
        mem = psutil.virtual_memory()
        self.ram_percent = mem.percent
        self.ram_used = mem.used / (1024**3)
        self.ram_total = mem.total / (1024**3)
        
        # GPU
        if NVIDIA_AVAILABLE and GPU_HANDLE:
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE)
                self.gpu_percent = util.gpu
                self.gpu_temp = pynvml.nvmlDeviceGetTemperature(GPU_HANDLE, pynvml.NVML_TEMPERATURE_GPU)
                
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(GPU_HANDLE)
                self.vram_used = mem_info.used / (1024**3)
                self.vram_total = mem_info.total / (1024**3)
            except:
                pass
        
        # Network
        try:
            net = psutil.net_io_counters()
            self.net_down = (net.bytes_recv - self._last_net.bytes_recv) / time_delta / 1024  # KB/s
            self.net_up = (net.bytes_sent - self._last_net.bytes_sent) / time_delta / 1024
            self._last_net = net
        except:
            pass
        
        # Disk
        try:
            disk = psutil.disk_io_counters()
            self.disk_read = (disk.read_bytes - self._last_disk.read_bytes) / time_delta / (1024**2)  # MB/s
            self.disk_write = (disk.write_bytes - self._last_disk.write_bytes) / time_delta / (1024**2)
            self._last_disk = disk
        except:
            pass
        
        self._last_time = current_time
    
    def _update_ui(self):
        """Update UI labels"""
        if self.is_collapsed:
            return
        
        # CPU
        cpu_color = self._get_color_for_value(self.cpu_percent, "#00D4FF")
        cpu_text = f"CPU: {self.cpu_percent:4.0f}%"
        if self.cpu_temp:
            cpu_text += f" | {self._format_temp(self.cpu_temp)}"
        self.cpu_label.config(text=cpu_text, fg=cpu_color)
        
        # RAM
        ram_color = self._get_color_for_value(self.ram_percent, "#9B59B6")
        self.ram_label.config(
            text=f"RAM: {self.ram_percent:4.0f}% ({self.ram_used:.0f}/{self.ram_total:.0f}GB)",
            fg=ram_color
        )
        
        # GPU
        if NVIDIA_AVAILABLE:
            vram_percent = (self.vram_used / self.vram_total * 100) if self.vram_total > 0 else 0
            gpu_color = self._get_color_for_value(max(self.gpu_percent, vram_percent), "#2ECC71")
            self.gpu_label.config(
                text=f"GPU: {self.gpu_percent:3.0f}% | VRAM: {self.vram_used:.1f}/{self.vram_total:.0f}GB | {self._format_temp(self.gpu_temp)}",
                fg=gpu_color
            )
        else:
            self.gpu_label.config(text="GPU: N/A", fg="#666666")
        
        # Network
        self.net_label.config(
            text=f"NET: ↓{self.net_down:6.0f} ↑{self.net_up:6.0f} KB/s"
        )
        
        # Disk
        self.disk_label.config(
            text=f"DISK: R:{self.disk_read:5.1f} W:{self.disk_write:5.1f} MB/s"
        )
    
    def _update_loop(self):
        """Background update loop"""
        while self.running:
            try:
                self._update_stats()
                self.after(0, self._update_ui)
            except Exception as e:
                print(f"Update error: {e}")
            time.sleep(1.0)
    
    def _on_close(self):
        """Handle close"""
        print("👋 Closing PowerBar...")
        self.running = False
        
        if NVIDIA_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
        
        self.destroy()


def main():
    print("""
╔═══════════════════════════════════════════════════╗
║   SysMon PowerBar - Cel Systems 2025              ║
║   Angedockte System-Statusleiste für Windows 11   ║
╚═══════════════════════════════════════════════════╝
    """)
    print("💡 Tipps:")
    print("   • Doppelklick: Ein-/Ausklappen")
    print("   • Rechtsklick: Menü (Dock oben/unten, °C/°F)")
    print("   • Ziehen: Bar verschieben")
    print("   • ⚙ Button: Temperatur-Einheit wechseln")
    print("   • ✕ Button: Schließen")
    print()
    
    app = PowerBar()
    app.mainloop()


if __name__ == "__main__":
    main()

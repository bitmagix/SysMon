"""
SysMon - Modern System Monitor Widget
Cel Systems 2025

A sleek, always-on-top system monitoring widget for Windows 11
Monitors: CPU, RAM, GPU (NVIDIA), Disk, Network
"""

import customtkinter as ctk
import psutil
import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
import sys

# Try to import NVIDIA monitoring
try:
    import pynvml
    NVIDIA_AVAILABLE = True
except ImportError:
    NVIDIA_AVAILABLE = False
    print("⚠️ nvidia-ml-py not installed - GPU monitoring disabled")

# Try to import hardware monitoring for CPU temp
try:
    from HardwareMonitor.Hardware import Computer, IVisitor, IComputer, IHardware, ISensor, IParameter, SensorType
    HWMON_AVAILABLE = True
except ImportError:
    HWMON_AVAILABLE = False
    print("⚠️ PyHardwareMonitor not installed - CPU temperature disabled")


@dataclass
class SystemStats:
    """Data class for system statistics"""
    # CPU
    cpu_percent: float = 0.0
    cpu_temp_celsius: Optional[float] = None
    
    # RAM
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    
    # GPU (NVIDIA)
    gpu_percent: float = 0.0
    gpu_temp_celsius: Optional[float] = None
    gpu_vram_used_gb: float = 0.0
    gpu_vram_total_gb: float = 0.0
    gpu_name: str = "N/A"
    
    # Disk
    disk_percent: float = 0.0
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    
    # Network
    net_sent_mb: float = 0.0
    net_recv_mb: float = 0.0
    net_speed_up: float = 0.0
    net_speed_down: float = 0.0


class HardwareVisitor(IVisitor if HWMON_AVAILABLE else object):
    """Visitor pattern for LibreHardwareMonitor"""
    if HWMON_AVAILABLE:
        __namespace__ = "SysMonVisitor"
        
        def VisitComputer(self, computer: IComputer):
            computer.Traverse(self)
        
        def VisitHardware(self, hardware: IHardware):
            hardware.Update()
            for sub in hardware.SubHardware:
                sub.Update()
        
        def VisitParameter(self, parameter: IParameter):
            pass
        
        def VisitSensor(self, sensor: ISensor):
            pass


class SystemMonitor:
    """Collects system statistics"""
    
    def __init__(self):
        self.stats = SystemStats()
        self._last_net_io = psutil.net_io_counters()
        self._last_disk_io = psutil.disk_io_counters()
        self._last_time = time.time()
        
        # Initialize NVIDIA
        if NVIDIA_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self.stats.gpu_name = pynvml.nvmlDeviceGetName(self._gpu_handle)
            except Exception as e:
                print(f"⚠️ NVIDIA init failed: {e}")
                self._gpu_handle = None
        else:
            self._gpu_handle = None
        
        # Initialize CPU temperature monitoring
        self._hw_computer = None
        if HWMON_AVAILABLE:
            try:
                self._hw_computer = Computer()
                self._hw_computer.IsCpuEnabled = True
                self._hw_computer.Open()
                self._hw_visitor = HardwareVisitor()
            except Exception as e:
                print(f"⚠️ Hardware Monitor init failed: {e}")
                self._hw_computer = None
    
    def update(self) -> SystemStats:
        """Update all system statistics"""
        current_time = time.time()
        time_delta = current_time - self._last_time
        
        # CPU
        self.stats.cpu_percent = psutil.cpu_percent(interval=None)
        self._update_cpu_temp()
        
        # RAM
        mem = psutil.virtual_memory()
        self.stats.ram_percent = mem.percent
        self.stats.ram_used_gb = mem.used / (1024**3)
        self.stats.ram_total_gb = mem.total / (1024**3)
        
        # GPU
        self._update_gpu_stats()
        
        # Disk
        self._update_disk_stats(time_delta)
        
        # Network
        self._update_net_stats(time_delta)
        
        self._last_time = current_time
        return self.stats
    
    def _update_cpu_temp(self):
        """Update CPU temperature using LibreHardwareMonitor"""
        if self._hw_computer:
            try:
                self._hw_computer.Accept(self._hw_visitor)
                for hardware in self._hw_computer.Hardware:
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature:
                            if "Package" in str(sensor.Name) or "CPU" in str(sensor.Name):
                                self.stats.cpu_temp_celsius = float(sensor.Value)
                                return
            except Exception as e:
                pass
    
    def _update_gpu_stats(self):
        """Update NVIDIA GPU statistics"""
        if self._gpu_handle:
            try:
                # Utilization
                util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                self.stats.gpu_percent = util.gpu
                
                # Temperature
                self.stats.gpu_temp_celsius = pynvml.nvmlDeviceGetTemperature(
                    self._gpu_handle, pynvml.NVML_TEMPERATURE_GPU
                )
                
                # VRAM
                mem = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                self.stats.gpu_vram_used_gb = mem.used / (1024**3)
                self.stats.gpu_vram_total_gb = mem.total / (1024**3)
            except Exception as e:
                pass
    
    def _update_disk_stats(self, time_delta: float):
        """Update disk statistics"""
        try:
            disk = psutil.disk_usage('/')
            self.stats.disk_percent = disk.percent
            
            disk_io = psutil.disk_io_counters()
            if time_delta > 0:
                read_bytes = disk_io.read_bytes - self._last_disk_io.read_bytes
                write_bytes = disk_io.write_bytes - self._last_disk_io.write_bytes
                self.stats.disk_read_mb = (read_bytes / time_delta) / (1024**2)
                self.stats.disk_write_mb = (write_bytes / time_delta) / (1024**2)
            self._last_disk_io = disk_io
        except Exception:
            pass
    
    def _update_net_stats(self, time_delta: float):
        """Update network statistics"""
        try:
            net_io = psutil.net_io_counters()
            self.stats.net_sent_mb = net_io.bytes_sent / (1024**2)
            self.stats.net_recv_mb = net_io.bytes_recv / (1024**2)
            
            if time_delta > 0:
                sent_delta = net_io.bytes_sent - self._last_net_io.bytes_sent
                recv_delta = net_io.bytes_recv - self._last_net_io.bytes_recv
                self.stats.net_speed_up = (sent_delta / time_delta) / 1024  # KB/s
                self.stats.net_speed_down = (recv_delta / time_delta) / 1024  # KB/s
            
            self._last_net_io = net_io
        except Exception:
            pass
    
    def cleanup(self):
        """Cleanup resources"""
        if NVIDIA_AVAILABLE and self._gpu_handle:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
        if self._hw_computer:
            try:
                self._hw_computer.Close()
            except:
                pass


class MetricWidget(ctk.CTkFrame):
    """A single metric display widget"""
    
    def __init__(self, parent, title: str, icon: str = "●", color: str = "#00D4FF"):
        super().__init__(parent, fg_color="transparent")
        
        self.color = color
        
        # Icon and title
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=5, pady=(5, 0))
        
        self.icon_label = ctk.CTkLabel(
            self.header, 
            text=icon, 
            font=("Segoe UI", 12),
            text_color=color
        )
        self.icon_label.pack(side="left")
        
        self.title_label = ctk.CTkLabel(
            self.header, 
            text=title, 
            font=("Segoe UI", 11, "bold"),
            text_color="#FFFFFF"
        )
        self.title_label.pack(side="left", padx=(5, 0))
        
        # Value
        self.value_label = ctk.CTkLabel(
            self, 
            text="--", 
            font=("Segoe UI Semibold", 18),
            text_color=color
        )
        self.value_label.pack(anchor="w", padx=10)
        
        # Sub-info
        self.sub_label = ctk.CTkLabel(
            self, 
            text="", 
            font=("Segoe UI", 9),
            text_color="#888888"
        )
        self.sub_label.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(
            self, 
            width=140, 
            height=4,
            progress_color=color,
            fg_color="#2A2A2A"
        )
        self.progress.pack(padx=10, pady=(0, 8))
        self.progress.set(0)
    
    def update_value(self, value: str, sub: str = "", progress: float = 0.0):
        """Update the displayed values"""
        self.value_label.configure(text=value)
        self.sub_label.configure(text=sub)
        self.progress.set(min(1.0, max(0.0, progress)))
        
        # Color coding based on usage
        if progress > 0.9:
            self.progress.configure(progress_color="#FF4444")
        elif progress > 0.7:
            self.progress.configure(progress_color="#FFAA00")
        else:
            self.progress.configure(progress_color=self.color)


class SysMonApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.title("SysMon")
        self.geometry("180x520")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.95)
        
        # Dark theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Configure window
        self.configure(fg_color="#1A1A1A")
        
        # Make window draggable
        self._drag_data = {"x": 0, "y": 0}
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
        
        # Temperature unit (True = Celsius, False = Fahrenheit)
        self.use_celsius = True
        
        # Initialize monitor
        self.monitor = SystemMonitor()
        
        # Create UI
        self._create_ui()
        
        # Start update loop
        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        
        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_ui(self):
        """Create the user interface"""
        # Header
        header = ctk.CTkFrame(self, fg_color="#252525", corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        
        title = ctk.CTkLabel(
            header, 
            text="⚡ SysMon", 
            font=("Segoe UI Semibold", 14),
            text_color="#00D4FF"
        )
        title.pack(side="left", padx=10, pady=8)
        
        # Settings button
        self.temp_btn = ctk.CTkButton(
            header,
            text="°C",
            width=30,
            height=24,
            font=("Segoe UI", 10),
            fg_color="#333333",
            hover_color="#444444",
            command=self._toggle_temp_unit
        )
        self.temp_btn.pack(side="right", padx=5, pady=5)
        
        # Close button
        close_btn = ctk.CTkButton(
            header,
            text="✕",
            width=30,
            height=24,
            font=("Segoe UI", 12),
            fg_color="#333333",
            hover_color="#FF4444",
            command=self._on_close
        )
        close_btn.pack(side="right", padx=(0, 5), pady=5)
        
        # Scrollable container for metrics
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # CPU Widget
        self.cpu_widget = MetricWidget(container, "CPU", "⬢", "#00D4FF")
        self.cpu_widget.pack(fill="x", pady=2)
        
        # RAM Widget
        self.ram_widget = MetricWidget(container, "RAM", "◼", "#9B59B6")
        self.ram_widget.pack(fill="x", pady=2)
        
        # GPU Widget
        self.gpu_widget = MetricWidget(container, "GPU", "◆", "#2ECC71")
        self.gpu_widget.pack(fill="x", pady=2)
        
        # Disk Widget
        self.disk_widget = MetricWidget(container, "DISK", "●", "#E74C3C")
        self.disk_widget.pack(fill="x", pady=2)
        
        # Network Widget
        self.net_widget = MetricWidget(container, "NET", "◉", "#F39C12")
        self.net_widget.pack(fill="x", pady=2)
        
        # Footer
        footer = ctk.CTkLabel(
            self,
            text="Cel Systems © 2025",
            font=("Segoe UI", 8),
            text_color="#555555"
        )
        footer.pack(pady=(0, 5))
    
    def _toggle_temp_unit(self):
        """Toggle between Celsius and Fahrenheit"""
        self.use_celsius = not self.use_celsius
        self.temp_btn.configure(text="°C" if self.use_celsius else "°F")
    
    def _format_temp(self, celsius: Optional[float]) -> str:
        """Format temperature based on current unit"""
        if celsius is None:
            return "--"
        if self.use_celsius:
            return f"{celsius:.0f}°C"
        else:
            fahrenheit = (celsius * 9/5) + 32
            return f"{fahrenheit:.0f}°F"
    
    def _start_drag(self, event):
        """Start window drag"""
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
    
    def _on_drag(self, event):
        """Handle window drag"""
        x = self.winfo_x() + (event.x - self._drag_data["x"])
        y = self.winfo_y() + (event.y - self._drag_data["y"])
        self.geometry(f"+{x}+{y}")
    
    def _update_loop(self):
        """Background update loop"""
        while self._running:
            try:
                stats = self.monitor.update()
                self.after(0, self._update_ui, stats)
            except Exception as e:
                print(f"Update error: {e}")
            time.sleep(1.0)
    
    def _update_ui(self, stats: SystemStats):
        """Update UI with new statistics"""
        # CPU
        cpu_temp = self._format_temp(stats.cpu_temp_celsius)
        self.cpu_widget.update_value(
            f"{stats.cpu_percent:.0f}%",
            f"Temp: {cpu_temp}",
            stats.cpu_percent / 100
        )
        
        # RAM
        self.ram_widget.update_value(
            f"{stats.ram_percent:.0f}%",
            f"{stats.ram_used_gb:.1f} / {stats.ram_total_gb:.0f} GB",
            stats.ram_percent / 100
        )
        
        # GPU
        if stats.gpu_vram_total_gb > 0:
            gpu_temp = self._format_temp(stats.gpu_temp_celsius)
            vram_percent = (stats.gpu_vram_used_gb / stats.gpu_vram_total_gb)
            self.gpu_widget.update_value(
                f"{stats.gpu_percent:.0f}%",
                f"VRAM: {stats.gpu_vram_used_gb:.1f}/{stats.gpu_vram_total_gb:.0f}GB • {gpu_temp}",
                vram_percent
            )
        else:
            self.gpu_widget.update_value("N/A", "No NVIDIA GPU", 0)
        
        # Disk
        self.disk_widget.update_value(
            f"{stats.disk_percent:.0f}%",
            f"R: {stats.disk_read_mb:.1f} W: {stats.disk_write_mb:.1f} MB/s",
            stats.disk_percent / 100
        )
        
        # Network
        self.net_widget.update_value(
            f"↓{stats.net_speed_down:.0f} KB/s",
            f"↑{stats.net_speed_up:.0f} KB/s",
            min(1.0, (stats.net_speed_down + stats.net_speed_up) / 10000)  # Scale to 10MB/s
        )
    
    def _on_close(self):
        """Handle application close"""
        self._running = False
        self.monitor.cleanup()
        self.destroy()


def main():
    print("🚀 Starting SysMon...")
    print("=" * 40)
    print(f"NVIDIA Support: {'✅' if NVIDIA_AVAILABLE else '❌'}")
    print(f"CPU Temp Support: {'✅' if HWMON_AVAILABLE else '❌'}")
    print("=" * 40)
    
    app = SysMonApp()
    app.mainloop()


if __name__ == "__main__":
    main()

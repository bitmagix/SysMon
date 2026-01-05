"""
SysMon Tray - System Monitor in der Taskleiste
Cel Systems 2025

Zeigt CPU/GPU/RAM Stats direkt im System Tray als dynamische Icons!
"""

import threading
import time
import sys
from typing import Optional
from dataclasses import dataclass

# Core dependencies
try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Run: pip install pystray Pillow")
    sys.exit(1)

import psutil

# NVIDIA support
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    GPU_NAME = pynvml.nvmlDeviceGetName(GPU_HANDLE)
    NVIDIA_AVAILABLE = True
    print(f"✅ NVIDIA GPU detected: {GPU_NAME}")
except Exception as e:
    NVIDIA_AVAILABLE = False
    GPU_HANDLE = None
    GPU_NAME = "N/A"
    print(f"⚠️ No NVIDIA GPU: {e}")


@dataclass
class Stats:
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    gpu_percent: float = 0.0
    gpu_temp: float = 0.0
    vram_used_gb: float = 0.0
    vram_total_gb: float = 0.0


class SysMonTray:
    """System Monitor with multiple tray icons"""
    
    def __init__(self):
        self.stats = Stats()
        self.running = True
        self.icons = {}
        self.use_celsius = True
        
        # Font for text in icons (we'll create simple text)
        try:
            # Try to use a nice font
            self.font_large = ImageFont.truetype("arial.ttf", 11)
            self.font_small = ImageFont.truetype("arial.ttf", 9)
        except:
            self.font_large = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
    
    def create_icon_image(self, text: str, color: str = "#00D4FF", bg_color: str = "#1a1a1a") -> Image.Image:
        """Create a 16x16 icon with text"""
        size = 16
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Background with rounded corners effect
        draw.rectangle([0, 0, size-1, size-1], fill=bg_color, outline=color)
        
        # Parse color
        if color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            text_color = (r, g, b, 255)
        else:
            text_color = (0, 212, 255, 255)
        
        # Draw text centered
        bbox = draw.textbbox((0, 0), text, font=self.font_small)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - 1
        draw.text((x, y), text, fill=text_color, font=self.font_small)
        
        return img
    
    def create_bar_icon(self, value: float, label: str, color: str = "#00D4FF") -> Image.Image:
        """Create a 16x16 icon with mini bar graph"""
        size = 16
        img = Image.new('RGBA', (size, size), (26, 26, 26, 255))
        draw = ImageDraw.Draw(img)
        
        # Parse color
        if color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            bar_color = (r, g, b, 255)
        else:
            bar_color = (0, 212, 255, 255)
        
        # Color based on value
        if value > 90:
            bar_color = (255, 68, 68, 255)  # Red
        elif value > 70:
            bar_color = (255, 170, 0, 255)  # Orange
        
        # Draw label at top (2 chars max)
        draw.text((1, 0), label[:2], fill=(150, 150, 150, 255), font=self.font_small)
        
        # Draw bar at bottom
        bar_height = 5
        bar_width = int((size - 2) * (value / 100))
        draw.rectangle([1, size - bar_height - 1, size - 2, size - 2], fill=(50, 50, 50, 255))
        draw.rectangle([1, size - bar_height - 1, 1 + bar_width, size - 2], fill=bar_color)
        
        return img
    
    def create_dual_icon(self, val1: float, val2: float, label: str, color: str = "#00D4FF") -> Image.Image:
        """Create icon showing two values (e.g., GPU % and VRAM %)"""
        size = 16
        img = Image.new('RGBA', (size, size), (26, 26, 26, 255))
        draw = ImageDraw.Draw(img)
        
        # Color coding
        def get_color(v):
            if v > 90:
                return (255, 68, 68, 255)
            elif v > 70:
                return (255, 170, 0, 255)
            if color.startswith('#'):
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                return (r, g, b, 255)
            return (0, 212, 255, 255)
        
        # Two small bars side by side
        bar_width = 6
        bar_max_height = 12
        
        # Left bar (val1)
        h1 = int(bar_max_height * (val1 / 100))
        draw.rectangle([1, size - h1 - 2, 1 + bar_width, size - 2], fill=get_color(val1))
        
        # Right bar (val2)  
        h2 = int(bar_max_height * (val2 / 100))
        draw.rectangle([size - bar_width - 2, size - h2 - 2, size - 2, size - 2], fill=get_color(val2))
        
        # Label at top
        draw.text((2, -1), label[:2], fill=(100, 100, 100, 255), font=self.font_small)
        
        return img
    
    def update_stats(self):
        """Update system statistics"""
        # CPU
        self.stats.cpu_percent = psutil.cpu_percent(interval=None)
        
        # RAM
        mem = psutil.virtual_memory()
        self.stats.ram_percent = mem.percent
        self.stats.ram_used_gb = mem.used / (1024**3)
        self.stats.ram_total_gb = mem.total / (1024**3)
        
        # GPU
        if NVIDIA_AVAILABLE and GPU_HANDLE:
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(GPU_HANDLE)
                self.stats.gpu_percent = util.gpu
                
                self.stats.gpu_temp = pynvml.nvmlDeviceGetTemperature(
                    GPU_HANDLE, pynvml.NVML_TEMPERATURE_GPU
                )
                
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(GPU_HANDLE)
                self.stats.vram_used_gb = mem_info.used / (1024**3)
                self.stats.vram_total_gb = mem_info.total / (1024**3)
            except Exception as e:
                pass
    
    def update_icons(self):
        """Update all tray icons with current stats"""
        try:
            # CPU Icon
            if 'cpu' in self.icons:
                cpu_img = self.create_bar_icon(self.stats.cpu_percent, "CP", "#00D4FF")
                self.icons['cpu'].icon = cpu_img
                self.icons['cpu'].title = f"CPU: {self.stats.cpu_percent:.0f}%"
            
            # RAM Icon
            if 'ram' in self.icons:
                ram_img = self.create_bar_icon(self.stats.ram_percent, "RM", "#9B59B6")
                self.icons['ram'].icon = ram_img
                self.icons['ram'].title = f"RAM: {self.stats.ram_used_gb:.1f}/{self.stats.ram_total_gb:.0f} GB ({self.stats.ram_percent:.0f}%)"
            
            # GPU Icon (shows both GPU% and VRAM%)
            if 'gpu' in self.icons and NVIDIA_AVAILABLE:
                vram_percent = (self.stats.vram_used_gb / self.stats.vram_total_gb * 100) if self.stats.vram_total_gb > 0 else 0
                gpu_img = self.create_dual_icon(self.stats.gpu_percent, vram_percent, "GP", "#2ECC71")
                self.icons['gpu'].icon = gpu_img
                
                temp_str = f"{self.stats.gpu_temp:.0f}°C" if self.use_celsius else f"{self.stats.gpu_temp * 9/5 + 32:.0f}°F"
                self.icons['gpu'].title = f"GPU: {self.stats.gpu_percent:.0f}% | VRAM: {self.stats.vram_used_gb:.1f}/{self.stats.vram_total_gb:.0f}GB | {temp_str}"
                
        except Exception as e:
            print(f"Icon update error: {e}")
    
    def update_loop(self):
        """Background update loop"""
        # Wait for icons to be ready
        time.sleep(2)
        
        while self.running:
            try:
                self.update_stats()
                self.update_icons()
            except Exception as e:
                print(f"Update error: {e}")
            time.sleep(1.5)
    
    def toggle_celsius(self, icon, item):
        """Toggle temperature unit"""
        self.use_celsius = not self.use_celsius
        print(f"Temperature unit: {'Celsius' if self.use_celsius else 'Fahrenheit'}")
    
    def quit_app(self, icon, item):
        """Quit the application"""
        print("👋 Shutting down SysMon...")
        self.running = False
        
        # Stop all icons
        for name, ic in self.icons.items():
            try:
                ic.stop()
            except:
                pass
        
        if NVIDIA_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
    
    def run(self):
        """Start the system tray application"""
        print("🚀 Starting SysMon Tray...")
        print("=" * 40)
        print(f"GPU: {GPU_NAME}")
        print("=" * 40)
        print("\n📌 Look for the icons in your System Tray!")
        print("   (Click the ^ arrow if you don't see them)")
        print("\n💡 Right-click any icon for options")
        
        # Create menu
        menu = pystray.Menu(
            item('Toggle °C/°F', self.toggle_celsius),
            item('Quit SysMon', self.quit_app)
        )
        
        # Create initial icons
        cpu_img = self.create_bar_icon(0, "CP", "#00D4FF")
        ram_img = self.create_bar_icon(0, "RM", "#9B59B6")
        gpu_img = self.create_dual_icon(0, 0, "GP", "#2ECC71")
        
        # CPU Icon
        self.icons['cpu'] = pystray.Icon(
            "SysMon_CPU",
            cpu_img,
            "CPU: Loading...",
            menu
        )
        
        # RAM Icon
        self.icons['ram'] = pystray.Icon(
            "SysMon_RAM", 
            ram_img,
            "RAM: Loading...",
            menu
        )
        
        # GPU Icon (if available)
        if NVIDIA_AVAILABLE:
            self.icons['gpu'] = pystray.Icon(
                "SysMon_GPU",
                gpu_img,
                "GPU: Loading...",
                menu
            )
        
        # Start update thread
        update_thread = threading.Thread(target=self.update_loop, daemon=True)
        update_thread.start()
        
        # Run icons in separate threads
        icon_threads = []
        for name, icon in self.icons.items():
            t = threading.Thread(target=icon.run, daemon=True)
            t.start()
            icon_threads.append(t)
            time.sleep(0.3)  # Small delay between icons
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n⚡ Interrupted by user")
            self.quit_app(None, None)


def main():
    print("""
╔═══════════════════════════════════════╗
║     SysMon Tray - Cel Systems 2025    ║
║   System Monitor in der Taskleiste    ║
╚═══════════════════════════════════════╝
    """)
    
    app = SysMonTray()
    app.run()


if __name__ == "__main__":
    main()

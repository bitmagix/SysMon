@echo off
echo ========================================
echo   SysMon - System Monitor Widget
echo   Cel Systems 2025
echo ========================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.10+
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/3] Installing dependencies...
pip install --upgrade pip
pip install customtkinter psutil nvidia-ml-py Pillow pywin32

REM Try to install PyHardwareMonitor (might need admin)
echo [INFO] Attempting to install PyHardwareMonitor for CPU temps...
pip install PyHardwareMonitor 2>nul
if errorlevel 1 (
    echo [WARN] PyHardwareMonitor failed - CPU temperature will be unavailable
    echo [WARN] Try running this script as Administrator
)

echo [3/3] Setup complete!
echo.
echo ========================================
echo   To run SysMon:
echo   1. Open PowerShell/CMD as Administrator
echo   2. cd C:\Projekte\SysMon
echo   3. venv\Scripts\activate
echo   4. python sysmon.py
echo ========================================
pause

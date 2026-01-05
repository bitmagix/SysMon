@echo off
echo Starting SysMon Tray...
cd /d %~dp0
call venv\Scripts\activate.bat
python sysmon_tray.py
pause

@echo off
echo Starting SysMon...
cd /d %~dp0
call venv\Scripts\activate.bat
python sysmon.py

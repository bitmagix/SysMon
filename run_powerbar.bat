@echo off
echo Starting SysMon PowerBar...
cd /d %~dp0
call venv\Scripts\activate.bat
python powerbar.py

@echo off
echo ========================================
echo   SysMon PowerBar Pro
echo   Cel Systems 2025
echo ========================================
echo.
cd /d %~dp0
call venv\Scripts\activate.bat
python powerbar_pro.py

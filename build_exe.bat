@echo off
echo ========================================
echo   SysMon PowerBar Pro - Build EXE
echo   Cel Systems 2025
echo ========================================
echo.

cd /d %~dp0
call venv\Scripts\activate.bat

echo [1/3] Installiere PyInstaller...
pip install pyinstaller --quiet

echo.
echo [2/3] Erstelle Standalone EXE...
echo        (Das dauert 1-2 Minuten)
echo.

pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "SysMonPowerBar" ^
    --hidden-import pynvml ^
    --hidden-import psutil ^
    --hidden-import tkinter ^
    --clean ^
    powerbar_pro.py

echo.
if exist "dist\SysMonPowerBar.exe" (
    echo ========================================
    echo   BUILD ERFOLGREICH!
    echo ========================================
    echo.
    echo   EXE erstellt: dist\SysMonPowerBar.exe
    echo.
    echo   Diese Datei kann jeder nutzen!
    echo   Kein Python noetig, einfach starten.
    echo.
    
    REM Kopiere in Hauptordner für einfachen Zugriff
    copy "dist\SysMonPowerBar.exe" "SysMonPowerBar.exe" >nul
    echo   Kopiert nach: SysMonPowerBar.exe
    echo.
) else (
    echo BUILD FEHLGESCHLAGEN!
    echo Pruefe die Fehlermeldungen oben.
)

pause

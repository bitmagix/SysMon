# SysMon PowerBar Pro - Build Script
# Creates standalone .exe with PyInstaller

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SysMon PowerBar Pro - Build System" -ForegroundColor Cyan
Write-Host "  Cel Systems 2025" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = $PSScriptRoot
$VenvPath = "$ProjectDir\venv"
$DistDir = "$ProjectDir\dist"
$BuildDir = "$ProjectDir\build"

# Activate venv
Write-Host "[1/4] Aktiviere Virtual Environment..." -ForegroundColor Yellow
& "$VenvPath\Scripts\Activate.ps1"

# Install PyInstaller if needed
Write-Host "[2/4] Installiere PyInstaller..." -ForegroundColor Yellow
pip install pyinstaller --quiet

# Build the executable
Write-Host "[3/4] Erstelle Executable..." -ForegroundColor Yellow
Write-Host "       Das kann ein paar Minuten dauern..." -ForegroundColor Gray

pyinstaller --noconfirm `
    --onefile `
    --windowed `
    --name "SysMon PowerBar" `
    --icon "$ProjectDir\assets\icon.ico" `
    --add-data "$ProjectDir\assets;assets" `
    --hidden-import pynvml `
    --hidden-import psutil `
    --clean `
    "$ProjectDir\powerbar_pro.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[4/4] BUILD ERFOLGREICH!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Executable: $DistDir\SysMon PowerBar.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Naechster Schritt: Installer erstellen mit Inno Setup" -ForegroundColor Yellow
    Write-Host "  Fuehre 'build_installer.bat' aus (benoetigt Inno Setup)" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "BUILD FEHLGESCHLAGEN!" -ForegroundColor Red
    Write-Host "Pruefe die Fehlermeldungen oben." -ForegroundColor Red
}

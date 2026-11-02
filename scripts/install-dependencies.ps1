$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
Write-Host "Checking for Python 3.11 (64-bit)..." -ForegroundColor Cyan
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python Launcher not found. Install Python 3.11 x64 from https://www.python.org/downloads/release/python-3119/ and enable the Python Launcher, then run this script again."
    exit 1
}
& py -3.11 --version
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python 3.11 was not found. Install Python 3.11 x64, then retry."
    exit 1
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create virtual environment." }
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip tools." }
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check the terminal output and README troubleshooting section." }
Write-Host "Dependencies installed. Connect your USB camera and use the Start Traffic Enforcement shortcut." -ForegroundColor Green
Read-Host "Press Enter to close"

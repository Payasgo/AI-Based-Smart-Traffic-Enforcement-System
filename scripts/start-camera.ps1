$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Python dependencies are not installed yet. Choose 'Install Python Dependencies' from the Start Menu first." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}
& $python main.py --source 0
if ($LASTEXITCODE -ne 0) {
    Write-Host "Application exited with an error. Review the output above and README troubleshooting." -ForegroundColor Red
    Read-Host "Press Enter to close"
}

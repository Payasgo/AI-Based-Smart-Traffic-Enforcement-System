param(
    [int]$CameraIndex = 0,
    [string]$PythonPath = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$python = Join-Path $root $PythonPath
if (-not (Test-Path $python)) { throw "Python environment not found at $python. Follow docs/WINDOWS_LOCAL_DEPLOYMENT.md." }
& $python -c "import cv2, numpy, scipy, ultralytics"
if ($LASTEXITCODE -ne 0) { throw "Required Python packages are missing. Prepare .venv using the Windows deployment guide." }

$logs = Join-Path $root "logs"
$evidence = Join-Path $root "evidence"
New-Item -ItemType Directory -Force -Path $logs, $evidence | Out-Null
$pidFile = Join-Path $logs "traffic-enforcement.pid"
$stdout = Join-Path $logs "application.stdout.log"
$stderr = Join-Path $logs "application.stderr.log"

# Stop only the process previously started by this deployment script.
if (Test-Path $pidFile) {
    $oldPid = 0
    $oldPidText = (Get-Content $pidFile -Raw).Trim()
    if ([int]::TryParse($oldPidText, [ref]$oldPid)) {
        $oldProcess = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($oldProcess -and $oldProcess.ProcessName -match '^python(w)?$') {
            Stop-Process -Id $oldPid -Force
            Start-Sleep -Seconds 2
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Run natively on Windows so OpenCV can access the USB webcam.
$process = Start-Process -FilePath $python `
    -ArgumentList @("main.py", "--source", "$CameraIndex", "--no-display") `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru
Start-Sleep -Seconds 5
$process.Refresh()
if ($process.HasExited) { throw "Application exited during startup (exit code $($process.ExitCode)). Check $stderr and verify the webcam." }
Set-Content -Path $pidFile -Value $process.Id -NoNewline
Write-Host "Traffic enforcement application started. PID=$($process.Id)"
Write-Host "Stdout: $stdout"
Write-Host "Stderr: $stderr"

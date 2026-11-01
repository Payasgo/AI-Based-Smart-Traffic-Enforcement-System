# Windows 10 local deployment (USB webcam)

This deployment runs the camera application natively on Windows using a self-hosted GitHub Actions runner. Docker Desktop's normal Linux-container mode does not provide straightforward USB webcam passthrough for this OpenCV application. Docker can still be used for headless tests, but do not put the live USB-camera process in a Linux container on this Windows host.

## 1. Prepare Windows

Install Git for Windows and Python 3.11 (64-bit). Docker Desktop is optional for this webcam deployment.

Open PowerShell in the cloned repository:

```powershell
git clone https://github.com/Payasgo/AI-Based-Smart-Traffic-Enforcement-System.git
cd AI-Based-Smart-Traffic-Enforcement-System
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Some dependencies, especially dlib and PyAudio, may need Windows build tools or compatible wheels. Resolve installation errors before registering the runner. The workflow checks core imports; it does not install packages on every push.

Download the facial landmark model if required:

```powershell
.\.venv\Scripts\python.exe models\download_models.py
```

Test USB camera access:

```powershell
.\.venv\Scripts\python.exe -c "import cv2; c=cv2.VideoCapture(0); print('camera opened:', c.isOpened()); c.release()"
```

If camera opened is False, close other camera applications, check Windows Camera privacy permissions, and try camera index 1.

## 2. Configure the GitHub self-hosted runner

Open repository Settings > Actions > Runners > New self-hosted runner, select Windows and x64, and follow GitHub's displayed download/configuration steps.

Run the commands in PowerShell as the Windows account that owns the webcam. Add labels self-hosted,windows,x64 if prompted:

```powershell
.\config.cmd --url https://github.com/Payasgo/AI-Based-Smart-Traffic-Enforcement-System --token <ONE_TIME_TOKEN> --labels self-hosted,windows,x64
```

Use the one-time token displayed by GitHub only in your local terminal. Never paste it into chat or commit it.

Important: start the runner interactively with .\run.cmd while that Windows user is logged in. Do not install it as a Windows service for the first webcam deployment; services run in a different session and may not have the user's webcam/device permissions. Keep the runner console open.

## 3. Deploy

The workflow runs on pushes to master and can also be started manually from Actions > CD - Deploy to Local Windows Camera Host > Run workflow.

It validates .venv and starts main.py --source 0 --no-display as a native Windows process. Logs are written to logs/application.stdout.log and logs/application.stderr.log; the process ID is stored in logs/traffic-enforcement.pid.

The workflow does not require SERVER_IP, SERVER_USER, SERVER_SSH_KEY, DOCKER_USERNAME, or DOCKER_PASSWORD for local-only deployment.

## 4. Stop and troubleshoot

Stop the deployed process from PowerShell in the repository:

```powershell
$pidFile = "logs\traffic-enforcement.pid"
if (Test-Path $pidFile) {
  $appPid = [int](Get-Content $pidFile)
  Stop-Process -Id $appPid -Force -ErrorAction SilentlyContinue
  Remove-Item $pidFile -Force
}
```

If startup fails, inspect logs/application.stderr.log. Test the camera with the OpenCV command above.

## 5. Operational safety

- Protect master and restrict who can push workflow changes. A self-hosted runner executes repository code on your computer.
- Keep the runner online and the Windows user logged in for automatic deployments.
- Prevent Windows sleep while operating; schedule updates/reboots for maintenance.
- Validate using recorded footage and controlled camera tests before continuous operation.
- This deployment does not validate speed calibration, legal evidence quality, or fine schedules. Require authorised human review.
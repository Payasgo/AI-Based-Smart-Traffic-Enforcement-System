<h1 align="center">Smarter Roads, Safer Lives</h1>
<h3 align="center">AI-Powered Real-Time Traffic Enforcement System</h3>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/YOLOv8-Ultralytics-8A2BE2?style=flat-square" />
  <img src="https://img.shields.io/badge/OpenCV-4.8%2B-5C3EE8?style=flat-square&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/dlib-19.24%2B-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-22c55e?style=flat-square" />
</p>

<p align="center">
  Automatically monitors speeding, drunk/drowsy driving, and illegal honking — 24/7, in real time,<br/>
  with photographic evidence and instant alerts to traffic authorities.
</p>

---

## Author

| Field | Detail |
|-------|--------|
| Name | Kranthi Kumar Yarlagadda |
| Focus | Artificial Intelligence & Computer Vision |
| Contact | payasgo55@gmail.com · kranthikumar.yarli@gmail.com |

---

## Inspiration

This project grew from a real observation: every day, vehicles race through junctions, weave between lanes, drive head-on into oncoming traffic, and drivers park roadside to drink before rejoining traffic with zero accountability. Manual enforcement cannot scale to this problem.

The answer is an intelligent camera system that watches continuously, identifies violations the moment they occur, captures irrefutable evidence, and sends it to the control room instantly — no human fatigue, no blind spots, no delays.

> Wide-scale deployment of this system has the potential to cut road accidents by **at least 30%**.

---

## What the system detects

| Module | Violation | Method |
|--------|-----------|--------|
| Speed detector | Speeding | Virtual line timing — measures elapsed time between two fixed lines to compute km/h |
| Drowsy/drunk detector | Drowsy driving | Eye Aspect Ratio (EAR) via 68-point dlib facial landmarks |
| Drunk detector | Erratic/drunk driving | Centroid swerve analysis — excessive lateral movement across frames |
| Honk detector | Illegal honking | Real-time FFT — identifies horn frequency bursts (300–3000 Hz) per audio chunk |
| All modules | Every violation | JPEG evidence snapshot + CSV log row + optional REST API alert |

---

## Project layout

```
traffic_enforcement/
│
├── main.py                           ← Orchestrator — run this to start the system
│
├── config/
│   └── settings.py                   ← Every tunable parameter lives here
│
├── detectors/
│   ├── vehicle_tracker.py            ← YOLOv8 inference + centroid tracker (persistent IDs)
│   ├── speed_detector.py             ← Virtual-line speed measurement
│   ├── drunk_driver_detector.py      ← EAR drowsiness + lane-swerve detector
│   └── honk_detector.py              ← FFT audio horn detector (runs on its own thread)
│
├── utils/
│   ├── evidence_logger.py            ← Saves JPEG snapshots and appends CSV rows
│   ├── alert_system.py               ← Fires REST API POST on each violation (optional)
│   ├── license_plate_ocr.py          ← Tesseract OCR helper for plate reading
│   ├── calibration.py                ← Camera intrinsic calibration via chessboard images
│   └── visualizer.py                 ← Matplotlib violation summary dashboard
│
├── models/
│   └── download_models.py            ← Downloads the dlib landmark model (~99 MB)
│
├── simulator/
│   └── index.html                    ← Browser-based visual simulator (no Python needed)
│
├── tests/
│   └── test_detectors.py             ← pytest unit tests for EAR and centroid tracker
│
├── logs/                             ← violations.csv is written here at runtime
├── evidence/                         ← Evidence JPEG snapshots saved here at runtime
├── requirements.txt
└── setup.py
```

---

## Step-by-step setup

Follow these steps exactly, in order. Each step builds on the previous one. Do not skip steps even if you think a dependency is already installed — version mismatches are the most common source of startup failures.

---

### Step 1 — Check your Python version

The system requires Python **3.9 or higher**. Earlier versions are missing typing features used throughout the codebase.

```bash
python --version
# Expected: Python 3.9.x, 3.10.x, 3.11.x, or 3.12.x
```

If you are below 3.9, download the latest stable release from https://www.python.org/downloads/ and restart your terminal before continuing.

> **Windows users:** during installation, tick _"Add Python to PATH"_. Without this, none of the commands below will work.

---

### Step 2 — Clone the repository

```bash
git clone https://github.com/your-username/traffic-enforcement-ai.git
cd traffic-enforcement-ai
```

If you downloaded a ZIP instead of cloning, unzip it and `cd` into the folder.

---

### Step 3 — Create a virtual environment

Always work inside a virtual environment. This keeps project dependencies completely isolated from your system Python installation and prevents version conflicts with other projects.

```bash
# Create the environment (run once)
python -m venv venv

# Activate it — pick the line that matches your OS and shell:
source venv/bin/activate            # macOS or Linux (bash/zsh)
venv\Scripts\activate               # Windows — Command Prompt
venv\Scripts\Activate.ps1           # Windows — PowerShell
```

You should now see `(venv)` at the start of your terminal prompt. **Every command from this point onward must be run with this environment active.** If you open a new terminal window you will need to re-run the activate line.

---

### Step 4 — Install system-level dependencies

Two external binaries must be installed before you install any Python packages. The Python wrappers (`pytesseract`, `pyaudio`) will silently fail at runtime — not at install time — if these are missing, which makes them hard to debug later.

#### 4a — Tesseract OCR (license plate text extraction)

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install tesseract-ocr -y

# macOS
brew install tesseract

# Windows
# 1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
# 2. Run the installer, choosing the default install path C:\Program Files\Tesseract-OCR
# 3. Open System Properties → Environment Variables → Path → Add:
#    C:\Program Files\Tesseract-OCR
```

Verify Tesseract is on your PATH:

```bash
tesseract --version
# Expected: tesseract 5.x.x  (4.x also works)
```

If this command is not found, Tesseract is not on your PATH. Fix the PATH before continuing.

#### 4b — PortAudio (microphone access for honk detection)

```bash
# Ubuntu / Debian
sudo apt install portaudio19-dev python3-dev -y

# macOS
brew install portaudio

# Windows
# PortAudio is bundled inside the PyAudio pre-built wheel.
# No separate installation is needed on Windows.
```

---

### Step 5 — Install Python packages

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

This installs: OpenCV, NumPy, SciPy, Pandas, PyTorch, Ultralytics (YOLOv8), dlib, PyAudio, pytesseract, and Matplotlib. Expect this to take 3–8 minutes depending on your internet speed.

#### Common install errors and fixes

**dlib fails to compile on Windows**

dlib builds from source and requires CMake and a C++ build toolchain. The fastest fix:

```bash
# Step 1 — install cmake via pip
pip install cmake

# Step 2 — try dlib again
pip install dlib

# If it still fails, install a pre-built wheel from:
# https://github.com/z-mahmud22/Dlib_Windows_Python3.x
# Then:
pip install path\to\dlib-19.24.x-cpXXX-win_amd64.whl
```

**PyAudio fails on Linux**

```bash
# Make sure the dev headers are installed (Step 4b), then:
pip install pyaudio
```

**torch install is very slow or times out**

PyTorch is large (~2 GB with CUDA). If the default install times out, install it manually from the official wheel index first:

```bash
# CPU-only (smaller, slower inference):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# CUDA 11.8 (NVIDIA GPU, recommended for real-time use):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

Then re-run `pip install -r requirements.txt` — it will skip torch and install the rest.

---

### Step 6 — Download AI models

Run the included download helper. It fetches the dlib 68-point facial landmark predictor (~99 MB compressed). YOLOv8n (~6 MB) is auto-downloaded by Ultralytics the first time `main.py` runs.

```bash
python models/download_models.py
```

Expected output:

```
=== Downloading model files ===
[DOWNLOAD] Fetching http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 ...
  100%
[EXTRACT] Decompressing...
[OK] Saved to models/shape_predictor_68_face_landmarks.dat
[INFO] YOLOv8n will be auto-downloaded by ultralytics on first run.
=== Done ===
```

**If the download hangs or fails** (slow connection or the dlib server is temporarily unavailable):

1. Visit http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 in your browser to download manually.
2. Decompress the `.bz2` file using 7-Zip (Windows) or `bunzip2` (macOS/Linux).
3. Move the `.dat` file into the `models/` folder.

After this step, your `models/` directory should contain:

```
models/
├── shape_predictor_68_face_landmarks.dat   ← ~100 MB, required for EAR detection
└── download_models.py
```

---

### Step 7 — (Optional but recommended) Calibrate your camera

Accurate speed measurement requires knowing how many pixels correspond to one real-world metre. Without calibration, the default `PIXELS_PER_METER = 8.0` in `settings.py` is a rough estimate that will be inaccurate for your specific camera and mounting angle.

To calibrate:

1. Print a 9×6 inner-corner chessboard (search "OpenCV chessboard pattern PDF").
2. Hold it in front of the camera at various angles and distances and capture around 20 photos.
3. Save the photos into a folder called `calib_images/`.
4. Run:

```bash
python utils/calibration.py --images calib_images/ --cols 9 --rows 6 --square 25
```

The script prints a camera matrix and distortion coefficients. Copy the values into `config/settings.py` under `CAMERA_MATRIX` and `DIST_COEFFS`.

---

### Step 8 — Run the system

```bash
# Default: webcam at index 0, 60 km/h speed limit, live display window
python main.py

# Use a recorded video file instead of a live camera
python main.py --source road_footage.mp4

# Change the speed limit (km/h)
python main.py --speed-limit 80

# Headless mode — no display window (servers, Raspberry Pi, SSH sessions)
python main.py --no-display

# Custom log and evidence directories
python main.py --log-dir /data/logs --evidence-dir /data/evidence

# Combine flags freely
python main.py --source 1 --speed-limit 50 --no-display --log-dir logs/session1
```

Press `q` in the display window, or `Ctrl+C` in the terminal, to stop the system cleanly.

---

### Step 9 — View the violation dashboard

After a session, generate a summary chart from the recorded violations:

```bash
# Display interactively
python utils/visualizer.py --log logs/violations.csv

# Save to a PNG file instead
python utils/visualizer.py --log logs/violations.csv --output report.png
```

The dashboard shows violations by type, speed distribution, violations per hour, and the top repeat-offender plates.

---

## Configuration reference (`config/settings.py`)

All parameters are in one place. You should not need to edit any other file for normal deployments.

### Video and display

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `VIDEO_SOURCE` | `0` | Camera index (integer) or path to a video file (string) |
| `SHOW_DISPLAY` | `True` | Show a live video window. Set `False` for headless deployments |
| `FRAME_WIDTH` | `1280` | Capture resolution width |
| `FRAME_HEIGHT` | `720` | Capture resolution height |

### Speed detection

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `SPEED_LIMIT_KMH` | `60.0` | Vehicles above this speed are flagged |
| `PIXELS_PER_METER` | `8.0` | **Must be calibrated per camera** — see Step 7 |
| `LINE_DISTANCE_METERS` | `10.0` | Real-world distance between the two virtual lines (metres) |
| `SPEED_LINE_1_Y` | `0.4` | Line 1 position as a fraction of frame height (0.0–1.0) |
| `SPEED_LINE_2_Y` | `0.6` | Line 2 position as a fraction of frame height |
| `SPEED_MEASUREMENT_FPS` | `30` | FPS used in speed calculations — should match your camera's actual FPS |

### Drowsiness detection

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `EYE_AR_THRESHOLD` | `0.25` | EAR below this = eye considered closed. Raise slightly if getting false positives |
| `EYE_AR_CONSEC_FRAMES` | `20` | Consecutive frames below threshold before a drowsy alert fires |
| `SWERVE_PIXEL_THRESHOLD` | `80` | Maximum lateral centroid drift (pixels) before a swerve alert fires |
| `SWERVE_CONSEC_FRAMES` | `15` | Frames of swerve above threshold to confirm erratic driving |
| `DLIB_LANDMARK_MODEL` | `models/shape_predictor_68_face_landmarks.dat` | Path to the dlib model |

### Honk detection

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `AUDIO_SAMPLE_RATE` | `16000` | Match this to your microphone's actual sample rate |
| `AUDIO_CHUNK_SIZE` | `1024` | Increase to `2048` if audio is choppy or dropping frames |
| `HONK_ENERGY_THRESH` | `3000` | RMS energy threshold. Raise this if road noise causes false positives |
| `HONK_FREQ_LOW_HZ` | `300` | Lower bound of the horn frequency band |
| `HONK_FREQ_HIGH_HZ` | `3000` | Upper bound of the horn frequency band |
| `HONK_COOLDOWN_SEC` | `5` | Seconds before another honk alert can fire |

### Alert integration (optional)

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `ENABLE_ALERTS` | `False` | Set `True` to POST each violation to an authority REST endpoint |
| `ALERT_ENDPOINT_URL` | `""` | Your authority's API URL |
| `ALERT_API_KEY` | env var | Set the `TRAFFIC_API_KEY` environment variable — do not hardcode this in the file |

---

## Evidence format

Every detected violation is automatically saved in two ways.

**CSV log** at `logs/violations.csv`:

```
timestamp,violation_type,license_plate,speed_kmh,evidence_image,location
2024-06-15 14:32:07,SPEED,KA05MN1234,87.3,evidence/SPEED_KA05MN1234_20240615_143207_451200.jpg,N/A
2024-06-15 14:45:19,DROWSY_DRIVER,UNKNOWN,,evidence/DROWSY_DRIVER_UNKNOWN_20240615_144519_012800.jpg,N/A
2024-06-15 15:01:44,HONKING,AUDIO_ONLY,,,N/A
```

**JPEG snapshots** in `evidence/`, named with microsecond precision to prevent filename collisions:

```
{VIOLATION_TYPE}_{LICENSE_PLATE}_{YYYYMMDD}_{HHMMSS}_{microseconds}.jpg
```

---

## Bug fixes (this release)

The following issues were identified during internal testing and are resolved in this version. Each fix is applied in the codebase — this section documents what changed and why, so reviewers and contributors can understand the decisions.

---

### Bug 1 — Speed calculated as `inf` when vehicle crosses both lines in one frame

**Symptom:** `speed_kmh` column in the CSV showed `inf` or `nan` for fast-moving vehicles. Violation banners appeared for stationary objects.

**Root cause:** If a vehicle moved quickly enough to cross both `LINE_1_Y` and `LINE_2_Y` in a single frame, the time delta `dt` was `0` ms. Dividing the line distance by zero produced `inf`.

**Fix** (`detectors/speed_detector.py`):

```python
# Before — no guard against zero delta
speed_mps = self.config.LINE_DISTANCE_METERS / dt

# After — guard added; returns None if timing is unusable
if dt <= 0:
    return None
speed_mps = self.config.LINE_DISTANCE_METERS / dt
```

---

### Bug 2 — Same vehicle triggers multiple speed alerts

**Symptom:** A single vehicle passing the speed line produced 3–5 CSV entries for the same event, flooding the log and inflating violation counts.

**Root cause:** The vehicle centroid oscillated slightly around `LINE2_Y` (due to bounding box jitter from YOLOv8), causing the crossing condition to fire on several consecutive frames.

**Fix** (`detectors/speed_detector.py`): A per-vehicle `alerted` flag ensures only the first alert fires.

```python
if speed > self.config.SPEED_LIMIT_KMH and vid not in self._alerted:
    self._alerted.add(vid)
    self._handle_violation(...)   # only runs once per vehicle per pass
```

---

### Bug 3 — Honk detector crashes the process on systems without a microphone

**Symptom:** On machines with no audio input device, the system raised `OSError: [Errno -9996] Invalid input device` at startup and the entire process exited.

**Root cause:** `pyaudio.PyAudio().open()` throws `OSError` when no input device exists. This exception was unhandled.

**Fix** (`detectors/honk_detector.py`):

```python
try:
    stream = pa.open(
        format=pyaudio.paInt16, channels=1,
        rate=self.config.AUDIO_SAMPLE_RATE,
        input=True, frames_per_buffer=self.config.AUDIO_CHUNK_SIZE,
    )
except Exception as e:
    print(f"[WARNING] Audio stream error: {e}")
    return   # exits the audio thread cleanly; rest of system continues
```

---

### Bug 4 — dlib model path error on Windows at startup

**Symptom:** `RuntimeError: Unable to open file models/shape_predictor_68_face_landmarks.dat` on Windows, even when the file was present.

**Root cause:** The model path was hardcoded with a forward slash (`/`). dlib's C++ file loader does not normalise path separators on Windows, so it treated `models/shape_predictor_68_face_landmarks.dat` as a literal filename rather than a relative path.

**Fix** (`config/settings.py`): Path is now constructed with `pathlib.Path`, which resolves to the correct OS separator automatically.

```python
from pathlib import Path
DLIB_LANDMARK_MODEL = str(Path("models") / "shape_predictor_68_face_landmarks.dat")
```

---

### Bug 5 — Evidence images overwritten when two violations fire within the same second

**Symptom:** In busy traffic, multiple simultaneous violations produced JPEG files with identical names, causing later captures to overwrite earlier ones. Evidence was silently lost.

**Root cause:** The timestamp format `%Y%m%d_%H%M%S` has one-second resolution. Two events in the same second produced the same filename.

**Fix** (`utils/evidence_logger.py`): Microseconds are now appended using `%f`.

```python
# Before — second-resolution, causes collisions
ts_str = timestamp.strftime("%Y%m%d_%H%M%S")

# After — microsecond-resolution, unique per event
ts_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
```

---

### Bug 6 — Centroid tracker loses vehicle IDs when multiple vehicles enter frame at once

**Symptom:** When 3 or more vehicles entered the frame together, existing tracked vehicles were assigned new IDs, losing their speed measurement history and triggering false re-alerts.

**Root cause:** The original centroid matching used a naive `argmin` per row without properly marking used columns. When multiple new detections competed for the same existing centroid, the column could be assigned to more than one existing object.

**Fix** (`detectors/vehicle_tracker.py`): Replaced naive matching with a proper row-column sweep that marks both used rows and used columns before registering new objects.

```python
used_rows, used_cols = set(), set()
for (row, col) in zip(rows, cols):
    if row in used_rows or col in used_cols:
        continue   # skip if either side is already matched
    # ... assign match, mark both as used
    used_rows.add(row)
    used_cols.add(col)
```

---

### Bug 7 — `ImportError` on startup when PyAudio is not installed, even with honk detection disabled

**Symptom:** The process raised `ImportError: No module named 'pyaudio'` on startup even when the honk detection toggle was off, preventing the speed and drowsiness detectors from running.

**Root cause:** `import pyaudio` was at the top level of `honk_detector.py`. Python imports all module-level statements when the file is first loaded, regardless of runtime settings.

**Fix** (`detectors/honk_detector.py`): The import is deferred into the body of `start_listening()` so it only runs when audio monitoring is actually started.

```python
def start_listening(self):
    try:
        import pyaudio   # deferred — only executed if this method is called
    except ImportError:
        print("[WARNING] PyAudio not installed. Honk detection disabled.")
        return
    # ... rest of audio setup
```

---

### Bug 8 — OCR produces empty string and logs `UNKNOWN` for every plate

**Symptom:** The license plate column in `violations.csv` showed `UNKNOWN` for all speed violations, even when the plate was clearly readable in the evidence photo.

**Root cause:** The OCR region of interest (ROI) was cropping the top 35% of the bounding box, which corresponds to the windshield area. License plates are at the bottom of the vehicle.

**Fix** (`utils/license_plate_ocr.py`): ROI now targets the bottom 35% of the bounding box.

```python
# Before — cropped windshield region (wrong)
roi = frame[y1:y1 + int((y2 - y1) * 0.35), x1:x2]

# After — targets plate region at bottom of vehicle
plate_y1 = int(y1 + (y2 - y1) * 0.65)
roi = frame[max(0, plate_y1):y2, max(0, x1):x2]
```

---

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

Expected output:

```
tests/test_detectors.py::TestEAR::test_open_eye                              PASSED
tests/test_detectors.py::TestEAR::test_closed_eye                            PASSED
tests/test_detectors.py::TestCentroidTracker::test_register_objects          PASSED
tests/test_detectors.py::TestCentroidTracker::test_disappear_and_deregister  PASSED
tests/test_detectors.py::TestCentroidTracker::test_consistent_ids            PASSED

5 passed in 0.38s
```

If any test fails, check that you are running inside the `venv` environment and that `pip install -r requirements.txt` completed without errors.

---

## Hardware requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Camera | 1 × 1080p, 30 FPS | Multiple 1080p+ cameras for 3-D lane triangulation |
| Microphone | Any USB mic, 16 kHz | Directional or array mic for accurate vehicle source location |
| CPU | Intel i7 / AMD Ryzen 7 | Same or better |
| GPU | None (CPU-only, ~5 FPS) | NVIDIA RTX series — real-time 30+ FPS YOLOv8 inference |
| RAM | 8 GB | 16 GB+ |
| Storage | 20 GB free | 100 GB+ for long-term evidence archive |
| Internet | Not required | Required only for REST alert integration |

---

## Technology stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.9+ | Core runtime |
| Object detection | YOLOv8 (Ultralytics) | Vehicle detection and class identification |
| Tracking | Centroid tracker (custom) | Persistent per-vehicle IDs across frames |
| Face analysis | dlib 68-point predictor | Eye landmark extraction for EAR calculation |
| Computer vision | OpenCV 4.8+ | Frame capture, drawing, image processing |
| Audio | PyAudio + NumPy FFT | Real-time microphone analysis for horn detection |
| OCR | Tesseract + pytesseract | License plate text extraction |
| Data | Pandas + CSV | Violation logging and dashboard input |
| Visualisation | Matplotlib | Post-session violation dashboard |
| Alerting | Python `urllib` (REST) | Optional push to authority API |
| Simulation | HTML5 Canvas + JS | Browser-based visual demo (no Python required) |

---

## Benefits to traffic authorities

- Eliminates manual monitoring fatigue — runs 24/7 without operator intervention
- Catches multiple violation types simultaneously in a single camera feed
- Produces evidence-ready artefacts — photos, timestamps, and plate numbers suitable for fines or court use
- Scales to any deployment — city intersections, highway stretches, toll plazas, or school zones
- Deters violations through visible presence and immediate response

---

## Future enhancements

- [ ] Cloud-based live monitoring dashboard (Grafana / custom web UI)
- [ ] Automatic fine generation via government traffic authority APIs
- [ ] Wrong-way driving and red-light violation detection
- [ ] Multi-camera 3-D vehicle position reconstruction
- [ ] Behaviour prediction for proactive accident prevention
- [ ] IoT and smart-city sensor fusion (radar, LiDAR, traffic lights)
- [ ] Mobile alert app for on-the-ground traffic wardens

---

## License

MIT License — see `LICENSE` for full terms.

---

<p align="center"><i>Smarter Roads, Safer Lives — AI at the Service of Traffic Enforcement</i></p>
<p align="center"><b>Kranthi Kumar Yarlagadda</b></p>

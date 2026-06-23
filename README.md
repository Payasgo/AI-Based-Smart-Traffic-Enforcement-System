<h1 align="center">🚦 Smarter Roads, Safer Lives</h1>
<h3 align="center">AI-Powered Traffic Enforcement System</h3>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/YOLOv8-Ultralytics-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/OpenCV-4.8%2B-green?style=for-the-badge&logo=opencv" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
</p>

<p align="center">
  Real-time, multi-violation traffic monitoring using computer vision, audio AI, and deep learning — <br/>
  automatically detecting speeding, drunk/drowsy driving, and illegal honking, 24/7.
</p>

---

## 👤 Author

| | |
|---|---|
| **Name** | Kranthi Kumar Yarlagadda |
| **Field** | Artificial Intelligence & Computer Vision |
| **Email** | payasgo55@gmail.com · kranthikumar.yarli@gmail.com |

---

## 💡 Inspiration

This project was born from observing a very real, everyday danger on roads — rash driving, wrong-route usage, vehicles crossing lanes and driving head-on into oncoming traffic, and a general lack of lane discipline. Even more alarming: drivers stopping on roadsides to drink and then driving again, putting lives at risk with zero accountability.

These observations made one thing clear: **manual traffic enforcement is not enough**. The only scalable solution is an intelligent, automated system that watches the road 24/7, identifies offenders instantly, and provides irrefutable evidence to authorities.

> With wide-scale deployment, this technology has the potential to **reduce road accidents by at least 30%**, building a safer and more responsible driving culture.

---

## 🎯 What It Detects

| Violation | How |
|-----------|-----|
| 🚗 **Speeding** | Virtual detection lines + timestamp delta → speed in km/h |
| 😵 **Drunk / Drowsy Driver** | Eye Aspect Ratio (EAR) via 68-point facial landmarks + lane swerve analysis |
| 📢 **Illegal Honking** | Real-time FFT audio analysis to identify horn frequency bursts |
| 🎥 **All Violations** | JPEG evidence snapshot + CSV log entry + optional REST API alert |

Think of it as a **smart traffic cop** that:

1. Watches the road **24/7** through cameras
2. Listens for illegal horn use through microphones
3. Analyses driver behaviour using AI facial analysis
4. Automatically captures evidence for every infraction
5. Sends instant alerts to the traffic control team

---

## 🏗️ Architecture

```
traffic_enforcement/
│
├── main.py                          ← Orchestrator — start here
│
├── config/
│   └── settings.py                  ← All tunable parameters (speed limit, thresholds, etc.)
│
├── detectors/
│   ├── vehicle_tracker.py           ← YOLOv8 detection + centroid tracker (persistent IDs)
│   ├── speed_detector.py            ← Virtual-line speed estimation
│   ├── drunk_driver_detector.py     ← EAR drowsiness + lane-swerve detection
│   └── honk_detector.py             ← FFT-based audio horn detection (runs on audio thread)
│
├── utils/
│   ├── evidence_logger.py           ← JPEG snapshots + CSV violation log
│   ├── alert_system.py              ← Optional REST API push to authority endpoint
│   ├── license_plate_ocr.py         ← Tesseract OCR helper for plate reading
│   ├── calibration.py               ← Camera intrinsic calibration (chessboard)
│   └── visualizer.py                ← Matplotlib violation dashboard
│
├── models/
│   └── download_models.py           ← Auto-downloads dlib landmark model
│
├── tests/
│   └── test_detectors.py            ← Unit tests (pytest)
│
├── logs/                            ← violations.csv written here at runtime
└── evidence/                        ← Evidence JPEG images saved here at runtime
```

---

## ⚙️ How Each Module Works

### 🚗 Speed Detection
Two virtual horizontal lines are drawn across the video frame at configurable positions. When a tracked vehicle's centroid crosses Line 1, the timestamp is recorded. When it crosses Line 2, the elapsed time is used to calculate:

```
speed (km/h) = (real_distance_metres / elapsed_seconds) × 3.6
```

If speed exceeds `SPEED_LIMIT_KMH`, the system captures a photo, runs OCR on the license plate, logs the violation, and optionally sends an alert.

### 😵 Drunk / Drowsy Driver Detection
Uses **dlib's 68-point facial landmark predictor** to locate the driver's eyes within each vehicle's bounding box. The **Eye Aspect Ratio (EAR)** is computed each frame:

```
EAR = (|p2–p6| + |p3–p5|) / (2 × |p1–p4|)
```

If EAR stays below `EYE_AR_THRESHOLD` for `EYE_AR_CONSEC_FRAMES` consecutive frames → drowsiness confirmed. Separately, the vehicle's centroid x-position is tracked over time; excessive lateral oscillation (`SWERVE_PIXEL_THRESHOLD`) flags erratic/drunk driving.

### 📢 Honk Detection
Runs on a dedicated audio thread. Each audio chunk is analysed for:
1. **RMS energy** — must exceed `HONK_ENERGY_THRESH`
2. **Frequency band** — >40% of energy must fall in the 300–3000 Hz horn band (FFT)

When both conditions are met, a honk event is logged with a cooldown to prevent duplicate alerts.

### 🎥 Vehicle Tracking
YOLOv8n detects vehicles (cars, motorcycles, buses, trucks) every frame. A **centroid tracker** assigns persistent integer IDs to each vehicle across frames, enabling per-vehicle state (speed history, EAR counter, swerve history) to be maintained correctly even as vehicles move through the scene.

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | ≥ 3.9 |
| CUDA (optional) | ≥ 11.8 for GPU acceleration |
| Tesseract OCR | Latest |

**Install Tesseract** (external binary required for license plate OCR):

```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download installer: https://github.com/UB-Mannheim/tesseract/wiki
```

---

### Step 1 — Clone & install Python dependencies

```bash
git clone https://github.com/your-username/traffic-enforcement-ai.git
cd traffic-enforcement-ai
pip install -r requirements.txt
```

### Step 2 — Download AI models

```bash
python models/download_models.py
```

This downloads the **dlib 68-point facial landmark model** (~100 MB). YOLOv8n is fetched automatically by `ultralytics` on first run.

### Step 3 — Run the system

```bash
# Default webcam (index 0), 60 km/h limit, with live display
python main.py

# From a recorded video file, 80 km/h limit
python main.py --source road_footage.mp4 --speed-limit 80

# Headless / server mode (no GUI window)
python main.py --source 0 --no-display

# Custom output directories
python main.py --log-dir /data/logs --evidence-dir /data/evidence
```

### Step 4 — View the violation dashboard

```bash
python utils/visualizer.py --log logs/violations.csv
# Save to image instead of showing interactively
python utils/visualizer.py --log logs/violations.csv --output report.png
```

### Step 5 — Camera calibration *(optional but strongly recommended)*

Accurate speed measurement requires knowing how many pixels correspond to one real-world metre.

```bash
# Collect ~20 photos of a 9×6 chessboard at various angles, save to calib_images/
python utils/calibration.py --images calib_images/ --cols 9 --rows 6 --square 25
# Copy the printed CAMERA_MATRIX and DIST_COEFFS into config/settings.py
```

---

## 🔧 Configuration Reference

All parameters live in `config/settings.py`. The most important ones:

### Video & Display
| Parameter | Default | Description |
|-----------|---------|-------------|
| `VIDEO_SOURCE` | `0` | Camera index (int) or path to video file (str) |
| `SHOW_DISPLAY` | `True` | Show live video window; set `False` for headless deployments |

### Speed Detection
| Parameter | Default | Description |
|-----------|---------|-------------|
| `SPEED_LIMIT_KMH` | `60.0` | Vehicles above this speed are flagged |
| `PIXELS_PER_METER` | `8.0` | **Must be calibrated per camera** |
| `LINE_DISTANCE_METERS` | `10.0` | Real-world gap between the two virtual lines (metres) |
| `SPEED_LINE_1_Y` | `0.4` | Line 1 position as fraction of frame height |
| `SPEED_LINE_2_Y` | `0.6` | Line 2 position as fraction of frame height |

### Drowsiness Detection
| Parameter | Default | Description |
|-----------|---------|-------------|
| `EYE_AR_THRESHOLD` | `0.25` | EAR below this → eye considered closed |
| `EYE_AR_CONSEC_FRAMES` | `20` | Frames below threshold to confirm drowsiness |
| `SWERVE_PIXEL_THRESHOLD` | `80` | Max lateral centroid deviation before flagging swerve |
| `DLIB_LANDMARK_MODEL` | `models/shape_predictor_68_face_landmarks.dat` | Path to dlib model |

### Honk Detection
| Parameter | Default | Description |
|-----------|---------|-------------|
| `AUDIO_SAMPLE_RATE` | `16000` | Microphone sample rate (Hz) |
| `HONK_ENERGY_THRESH` | `3000` | RMS energy threshold for horn detection |
| `HONK_FREQ_LOW_HZ` | `300` | Lower bound of horn frequency band |
| `HONK_FREQ_HIGH_HZ` | `3000` | Upper bound of horn frequency band |
| `HONK_COOLDOWN_SEC` | `5` | Seconds before another honk alert can fire |

### Alerting
| Parameter | Default | Description |
|-----------|---------|-------------|
| `ENABLE_ALERTS` | `False` | Set `True` to push violations to an external REST API |
| `ALERT_ENDPOINT_URL` | _(empty)_ | Your authority API endpoint |
| `ALERT_API_KEY` | env var | Set `TRAFFIC_API_KEY` environment variable |

---

## 📂 Evidence Format

Every detected violation is automatically saved in two places:

**`logs/violations.csv`**
```
timestamp,violation_type,license_plate,speed_kmh,evidence_image,location
2024-06-15 14:32:07,SPEED,KA05MN1234,87.3,evidence/SPEED_KA05MN1234_20240615_143207.jpg,N/A
2024-06-15 14:45:19,DROWSY_DRIVER,UNKNOWN,,evidence/DROWSY_DRIVER_UNKNOWN_20240615_144519.jpg,N/A
2024-06-15 15:01:44,HONKING,AUDIO_ONLY,,,N/A
```

**`evidence/`** — timestamped JPEG snapshots of every violation, named:
```
{VIOLATION_TYPE}_{LICENSE_PLATE}_{YYYYMMDD_HHMMSS_ffffff}.jpg
```

All evidence can be directly linked to enforcement databases or uploaded to cloud storage.

---

## 🖥️ Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Camera** | 1080p, 1 unit | 1080p+, multiple units for 3-D triangulation |
| **Microphone** | Any, 16 kHz | Directional / array mic for accurate source localisation |
| **CPU** | Intel i7 / AMD Ryzen 7 | Same or better |
| **GPU** | None (CPU-only) | NVIDIA RTX series (real-time YOLOv8 at 30+ FPS) |
| **RAM** | 8 GB | 16 GB+ |
| **Storage** | 20 GB free | 100 GB+ for long-term evidence retention |
| **Internet** | Optional | Required only for authority alert integration |

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## 🔌 Technology Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.9+ |
| Object Detection | YOLOv8 (Ultralytics) |
| Face Landmarks | dlib — 68-point shape predictor |
| Computer Vision | OpenCV 4.8+ |
| Audio Analysis | PyAudio + NumPy FFT |
| License Plate OCR | Tesseract + pytesseract |
| Data & Logging | Pandas, CSV |
| Visualisation | Matplotlib |
| Alerting | REST API (urllib / configurable) |

---

## 🔭 Benefits to Traffic Authorities

- **Eliminates manual monitoring fatigue** — runs 24/7 without human intervention
- **Catches multiple violation types simultaneously** — speed, drowsiness, and honking in one system
- **Evidence-ready enforcement** — photos, timestamps, and plate numbers ready for fines or court use
- **Scalable deployment** — works on city roads, highways, toll plazas, or school zones
- **Deterrence effect** — visible camera presence reduces violations proactively

---

## 🚀 Future Enhancements

- [ ] Cloud-based live monitoring dashboard (Grafana / custom web UI)
- [ ] Automatic fine generation via government traffic authority APIs
- [ ] Wrong-way driving and lane-crossing detection
- [ ] Behaviour prediction models for accident prevention
- [ ] IoT sensor fusion (radar, LiDAR, smart traffic lights)
- [ ] Multi-camera 3-D vehicle position reconstruction
- [ ] Mobile alert app for traffic wardens

---

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.

---

<p align="center">
  <i>"Smarter Roads, Safer Lives — AI at the Service of Traffic Enforcement"</i><br/>
  <b>Kranthi Kumar Yarlagadda</b>
</p>

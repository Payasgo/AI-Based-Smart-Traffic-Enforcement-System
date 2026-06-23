"""
Configuration settings for the Traffic Enforcement System.
Adjust these values to match your deployment environment.
"""

import os


class Settings:
    # ── Video / Camera ──────────────────────────────────────────────
    VIDEO_SOURCE = 0                    # 0 = default webcam; or path to video file
    SHOW_DISPLAY = True                 # Set False for headless/server deployments
    FRAME_WIDTH  = 1280
    FRAME_HEIGHT = 720

    # ── Speed Detection ─────────────────────────────────────────────
    SPEED_LIMIT_KMH       = 60.0       # Vehicles above this are flagged
    # Pixels-per-meter calibration: measure a known real-world distance in pixels
    PIXELS_PER_METER      = 8.0        # Tune per camera setup
    SPEED_MEASUREMENT_FPS = 30         # FPS used for speed estimation

    # Detection line positions (fraction of frame height, 0.0–1.0)
    SPEED_LINE_1_Y = 0.4               # First virtual detection line
    SPEED_LINE_2_Y = 0.6               # Second virtual detection line
    # Real-world distance between the two lines in meters
    LINE_DISTANCE_METERS  = 10.0

    # ── Drunk / Drowsy Driver Detection ─────────────────────────────
    EYE_AR_THRESHOLD      = 0.25       # Eye Aspect Ratio below this = drowsy
    EYE_AR_CONSEC_FRAMES  = 20         # Consecutive frames to confirm drowsiness
    DLIB_LANDMARK_MODEL   = "models/shape_predictor_68_face_landmarks.dat"

    # Erratic-driving thresholds
    SWERVE_PIXEL_THRESHOLD = 80        # Lane-centre deviation in pixels
    SWERVE_CONSEC_FRAMES   = 15

    # ── Honk Detection ──────────────────────────────────────────────
    AUDIO_SAMPLE_RATE   = 16000        # Hz
    AUDIO_CHUNK_SIZE    = 1024
    HONK_ENERGY_THRESH  = 3000         # RMS energy threshold for horn detection
    HONK_FREQ_LOW_HZ    = 300          # Typical horn frequency band (Hz)
    HONK_FREQ_HIGH_HZ   = 3000
    HONK_COOLDOWN_SEC   = 5            # Seconds before re-triggering honk alert

    # ── YOLOv8 Vehicle Detection ─────────────────────────────────────
    YOLO_MODEL_PATH     = "yolov8n.pt" # Auto-downloaded by ultralytics if absent
    YOLO_CONF_THRESHOLD = 0.45
    YOLO_IOU_THRESHOLD  = 0.45
    # COCO class IDs considered "vehicles"
    VEHICLE_CLASS_IDS   = [2, 3, 5, 7]  # car, motorcycle, bus, truck

    # ── OCR / License Plate ──────────────────────────────────────────
    TESSERACT_CMD       = "tesseract"   # Path to tesseract binary if not on PATH
    PLATE_MIN_WIDTH     = 60
    PLATE_MIN_HEIGHT    = 20

    # ── Evidence & Logging ───────────────────────────────────────────
    LOG_DIR             = "logs"
    EVIDENCE_DIR        = "evidence"
    LOG_FILENAME        = "violations.csv"
    MAX_EVIDENCE_IMAGES = 10000         # Rotate after this many images

    # ── Alerting ─────────────────────────────────────────────────────
    ENABLE_ALERTS       = False         # Set True to push to REST endpoint
    ALERT_ENDPOINT_URL  = "https://your-authority-api.example.com/violations"
    ALERT_API_KEY       = os.getenv("TRAFFIC_API_KEY", "")

    # ── Camera Calibration (multi-camera 3-D) ────────────────────────
    # Supply intrinsic matrices and extrinsic params per camera here.
    # Left as placeholders – fill in after camera calibration.
    CAMERA_MATRIX       = None          # np.array([[fx,0,cx],[0,fy,cy],[0,0,1]])
    DIST_COEFFS         = None          # np.array([k1,k2,p1,p2,k3])

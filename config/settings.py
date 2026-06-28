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
    SPEED_LIMIT_KMH       = 60.0
    PIXELS_PER_METER      = 8.0
    SPEED_MEASUREMENT_FPS = 30
    SPEED_LINE_1_Y        = 0.4
    SPEED_LINE_2_Y        = 0.6
    LINE_DISTANCE_METERS  = 10.0

    # ── Drunk / Drowsy Driver Detection ─────────────────────────────
    EYE_AR_THRESHOLD      = 0.25
    EYE_AR_CONSEC_FRAMES  = 20
    DLIB_LANDMARK_MODEL   = "models/shape_predictor_68_face_landmarks.dat"
    SWERVE_PIXEL_THRESHOLD = 80
    SWERVE_CONSEC_FRAMES   = 15

    # ── Honk Detection ──────────────────────────────────────────────
    AUDIO_SAMPLE_RATE   = 16000
    AUDIO_CHUNK_SIZE    = 1024
    HONK_ENERGY_THRESH  = 3000
    HONK_FREQ_LOW_HZ    = 300
    HONK_FREQ_HIGH_HZ   = 3000
    HONK_COOLDOWN_SEC   = 5

    # ── YOLOv8 Vehicle Detection ─────────────────────────────────────
    YOLO_MODEL_PATH     = "yolov8n.pt"
    YOLO_CONF_THRESHOLD = 0.45
    YOLO_IOU_THRESHOLD  = 0.45
    VEHICLE_CLASS_IDS   = [2, 3, 5, 7]   # car, motorcycle, bus, truck

    # ── OCR / License Plate ──────────────────────────────────────────
    TESSERACT_CMD       = "tesseract"
    PLATE_MIN_WIDTH     = 60
    PLATE_MIN_HEIGHT    = 20

    # ── Evidence & Logging ───────────────────────────────────────────
    LOG_DIR             = "logs"
    EVIDENCE_DIR        = "evidence"
    LOG_FILENAME        = "violations.csv"
    MAX_EVIDENCE_IMAGES = 10000

    # ── Alerting ─────────────────────────────────────────────────────
    ENABLE_ALERTS       = False
    ALERT_ENDPOINT_URL  = "https://your-authority-api.example.com/violations"
    ALERT_API_KEY       = os.getenv("TRAFFIC_API_KEY", "")

    # ── Camera Calibration ───────────────────────────────────────────
    CAMERA_MATRIX       = None
    DIST_COEFFS         = None

    # ── NEW: Lane Detection & Departure Warning ──────────────────────
    LANE_DEPARTURE_PIXELS = 60          # Pixel deviation to trigger warning

    # ── NEW: Helmet Detection ────────────────────────────────────────
    HELMET_MODEL_PATH   = None          # Path to custom YOLOv8 helmet model (optional)

    # ── NEW: Seatbelt Detection ──────────────────────────────────────
    SEATBELT_MODEL_PATH    = None       # Path to custom YOLOv8 seatbelt model (optional)
    SEATBELT_CONSEC_FRAMES = 20         # Frames without seatbelt before alert

    # ── NEW: Phone Usage Detection ───────────────────────────────────
    PHONE_CONSEC_FRAMES = 15

    # ── NEW: Distraction Detection (head-pose) ───────────────────────
    DISTRACTION_YAW_DEG      = 25      # Max yaw before flagging distraction
    DISTRACTION_PITCH_DEG    = 20      # Max pitch before flagging distraction
    DISTRACTION_CONSEC_FRAMES = 20

    # ── NEW: Traffic Light Detection ─────────────────────────────────
    TRAFFIC_STOP_LINE_Y = 0.70         # Stop-line position (fraction of frame height)

    # ── NEW: Traffic Sign Recognition ────────────────────────────────
    SIGN_MODEL_PATH     = None         # Path to custom YOLOv8 sign model (optional)

    # ── NEW: Collision Warning ────────────────────────────────────────
    # TTC thresholds defined inside CollisionWarning class

    # ── NEW: Pedestrian Detection ─────────────────────────────────────
    PED_PROXIMITY_PIXELS = 80          # Alert if vehicle within this many pixels

    # ── NEW: Obstacle Detection ───────────────────────────────────────
    OBSTACLE_MIN_AREA    = 1500        # Minimum foreground blob area (px²)
    OBSTACLE_ALERT_DIST  = 120         # Alert if vehicle within this many pixels

    # ── NEW: Blind Spot Detection ─────────────────────────────────────
    BLIND_SPOT_ZONE_W   = 120          # Width of blind-spot zone in pixels

    # ── NEW: Parking Assistance ───────────────────────────────────────
    PARKING_MODE        = False        # Enable parking-assist overlay

    # ── NEW: Driver Skill Classification ─────────────────────────────
    # Deduction weights are defined inside DriverSkillClassifier.DEDUCTIONS

    # ── NEW: Driving Lesson Tracking ─────────────────────────────────
    LESSON_DIR          = "lessons"    # Directory for JSON lesson reports

    # ── NEW: Voice Coaching ───────────────────────────────────────────
    VOICE_COACH_ENABLED = True         # Set False to disable TTS

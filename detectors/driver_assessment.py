"""
Driver Assessment Modules
=========================
• DriverSkillClassifier  – scores driving quality in real-time
• DrivingLessonTracker   – records session events for lesson review
• VoiceCoach             – issues spoken coaching cues via TTS

All three classes share a common event bus via a lightweight callback
pattern so they can be wired together or used independently.
"""

import time
import threading
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
import json


# ──────────────────────────────────────────────────────────────────────────────
# 1. Driver Skill Classifier
# ──────────────────────────────────────────────────────────────────────────────

class DriverSkillClassifier:
    """
    Assigns a real-time driving-skill score (0–100) based on observable
    behaviours detected by the other modules.

    Scoring deductions (configurable):
        Speed violation      –15 pts
        Lane departure       –10 pts
        Hard braking         – 8 pts
        Phone usage          –20 pts
        Drowsiness           –12 pts
        Distraction          –10 pts
        Seatbelt missing     –15 pts
        Helmet missing       –20 pts
        Red-light violation  –25 pts
        Pedestrian proximity –10 pts
        Smooth driving bonus + 1 pt/10 s

    The score decays slowly toward 100 when no violations occur,
    encouraging safe driving.
    """

    # Event → deduction mapping
    DEDUCTIONS = {
        "SPEED":             15,
        "LANE_DEPARTURE":    10,
        "HARD_BRAKING":       8,
        "PHONE_USAGE":       20,
        "DROWSY_DRIVER":     12,
        "DISTRACTION":       10,
        "NO_SEATBELT":       15,
        "NO_HELMET":         20,
        "RED_LIGHT":         25,
        "PED_PROXIMITY":     10,
        "ERRATIC_DRIVING":   12,
        "COLLISION_WARNING":  8,
    }

    GRADE_BANDS = [
        (90, "A – Excellent"),
        (75, "B – Good"),
        (60, "C – Satisfactory"),
        (45, "D – Needs Improvement"),
        ( 0, "F – Dangerous"),
    ]

    def __init__(self, config, lesson_tracker=None, voice_coach=None):
        self.config         = config
        self.lesson_tracker = lesson_tracker
        self.voice_coach    = voice_coach
        self._score: float  = 100.0
        self._history: deque = deque(maxlen=600)   # last ~10 min @ 1 Hz
        self._last_bonus_ts: float = time.time()
        self._event_lock    = threading.Lock()

    # ------------------------------------------------------------------
    def record_event(self, event_type: str, metadata: dict = None):
        """Call this whenever any detector fires a violation/warning."""
        deduction = self.DEDUCTIONS.get(event_type.upper(), 5)
        with self._event_lock:
            self._score = max(0.0, self._score - deduction)
            self._history.append({
                "ts":        time.time(),
                "event":     event_type,
                "deduction": deduction,
                "score":     self._score,
                **(metadata or {}),
            })

        grade = self.current_grade
        print(f"[SKILL] Event: {event_type} | -{deduction} pts | "
              f"Score: {self._score:.0f} | Grade: {grade}")

        if self.lesson_tracker:
            self.lesson_tracker.record_event(event_type, self._score, metadata)
        if self.voice_coach:
            self.voice_coach.advise(event_type, self._score)

    # ------------------------------------------------------------------
    def tick(self):
        """Call once per second to apply slow score recovery."""
        now = time.time()
        if now - self._last_bonus_ts >= 10:
            with self._event_lock:
                self._score = min(100.0, self._score + 1.0)
            self._last_bonus_ts = now

    # ------------------------------------------------------------------
    def draw_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Render score HUD on frame (bottom-left corner)."""
        import cv2
        h, w = frame.shape[:2]
        score   = int(self._score)
        grade   = self.current_grade

        # Background pill
        cv2.rectangle(frame, (0, h - 75), (260, h), (20, 20, 20), -1)

        # Score bar
        bar_w = int(2.40 * score)   # max 240 px at score=100
        color = (0, 200, 0) if score >= 75 else \
                (0, 165, 255) if score >= 50 else (0, 0, 255)
        cv2.rectangle(frame, (10, h - 30), (10 + bar_w, h - 12), color, -1)
        cv2.rectangle(frame, (10, h - 30), (250, h - 12), (100, 100, 100), 1)

        cv2.putText(frame, f"DRIVER SCORE: {score}/100",
                    (10, h - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, grade,
                    (10, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        return frame

    # ------------------------------------------------------------------
    @property
    def score(self) -> float:
        return self._score

    @property
    def current_grade(self) -> str:
        for threshold, label in self.GRADE_BANDS:
            if self._score >= threshold:
                return label
        return "F – Dangerous"

    def summary(self) -> dict:
        events = list(self._history)
        counts = defaultdict(int)
        for e in events:
            counts[e["event"]] += 1
        return {
            "final_score": self._score,
            "grade":       self.current_grade,
            "event_counts": dict(counts),
            "total_events": len(events),
        }


# ──────────────────────────────────────────────────────────────────────────────
# 2. Driving Lesson Tracker
# ──────────────────────────────────────────────────────────────────────────────

class DrivingLessonTracker:
    """
    Records a complete driving session for post-lesson review.

    Stores:
        • Session start / end timestamps
        • All detected events with timestamp, score at that point, and metadata
        • A per-minute summary (score timeline)
        • Final JSON report written to lesson_dir

    Integration:
        Pass an instance to DriverSkillClassifier(lesson_tracker=...) so events
        are forwarded automatically, or call record_event() directly.
    """

    def __init__(self, config):
        self.config       = config
        self._lesson_dir  = Path(getattr(config, 'LESSON_DIR', 'lessons'))
        self._lesson_dir.mkdir(parents=True, exist_ok=True)

        self._session_start = datetime.now()
        self._events: list  = []
        self._score_timeline: list = []   # (minute, score)
        self._last_minute: int = 0
        self._active = True

        print(f"[LESSON] Session started at {self._session_start.isoformat()}")

    # ------------------------------------------------------------------
    def record_event(self, event_type: str, score: float, metadata: dict = None):
        """Record a driving event."""
        if not self._active:
            return
        entry = {
            "ts":       datetime.now().isoformat(),
            "event":    event_type,
            "score":    round(score, 1),
            **(metadata or {}),
        }
        self._events.append(entry)

        # Update per-minute timeline
        elapsed_min = int((datetime.now() - self._session_start).seconds / 60)
        if elapsed_min > self._last_minute:
            self._score_timeline.append((elapsed_min, round(score, 1)))
            self._last_minute = elapsed_min

    # ------------------------------------------------------------------
    def end_session(self, final_score: float, grade: str) -> Path:
        """Finalise and write JSON report.  Returns path to the report."""
        self._active = False
        session_end  = datetime.now()
        duration_s   = (session_end - self._session_start).seconds

        report = {
            "session_start":   self._session_start.isoformat(),
            "session_end":     session_end.isoformat(),
            "duration_seconds": duration_s,
            "final_score":     round(final_score, 1),
            "grade":           grade,
            "total_events":    len(self._events),
            "score_timeline":  self._score_timeline,
            "events":          self._events,
        }

        ts_str  = self._session_start.strftime("%Y%m%d_%H%M%S")
        outpath = self._lesson_dir / f"lesson_{ts_str}.json"
        with open(outpath, "w") as fh:
            json.dump(report, fh, indent=2)

        print(f"[LESSON] Session ended. Duration: {duration_s}s | "
              f"Score: {final_score:.0f} | Report: {outpath}")
        return outpath

    # ------------------------------------------------------------------
    def draw_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Show session elapsed time and event count on frame."""
        import cv2
        elapsed = (datetime.now() - self._session_start).seconds
        mins, secs = divmod(elapsed, 60)
        label = (f"LESSON  {mins:02d}:{secs:02d}  |  "
                 f"Events: {len(self._events)}")
        h, w = frame.shape[:2]
        cv2.putText(frame, label, (w - 380, 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 50), 1)
        return frame

    @property
    def events(self) -> list:
        return list(self._events)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Voice Coach
# ──────────────────────────────────────────────────────────────────────────────

class VoiceCoach:
    """
    Provides real-time spoken coaching cues using text-to-speech.

    TTS priority chain:
        1. pyttsx3  (cross-platform, offline)
        2. gTTS     (requires internet)
        3. espeak   (Linux CLI fallback)
        4. Print-only (silent fallback)

    Cues are rate-limited per event type to avoid spamming the driver.
    """

    # Event → coaching message
    MESSAGES = {
        "SPEED":              "Warning! You are exceeding the speed limit. Please slow down.",
        "LANE_DEPARTURE":     "Lane departure detected. Please stay within your lane.",
        "PHONE_USAGE":        "Hands-free required. Please put your phone down.",
        "DROWSY_DRIVER":      "Drowsiness detected. Please take a break and rest.",
        "DISTRACTION":        "Eyes on the road. Stay focused while driving.",
        "NO_SEATBELT":        "Please fasten your seatbelt immediately.",
        "NO_HELMET":          "Helmet not detected. Please wear your helmet.",
        "RED_LIGHT":          "You have crossed a red light. Obey traffic signals.",
        "PED_PROXIMITY":      "Pedestrian ahead. Please reduce speed.",
        "COLLISION_WARNING":  "Collision warning! Brake now!",
        "ERRATIC_DRIVING":    "Erratic driving detected. Please drive smoothly.",
        "OBSTACLE":           "Obstacle in your path. Please slow down.",
        "BLIND_SPOT_LEFT":    "Vehicle in your left blind spot.",
        "BLIND_SPOT_RIGHT":   "Vehicle in your right blind spot.",
        "HONKING":            "Unnecessary honking detected. Please avoid horn use.",
    }

    # Minimum seconds between repeating the same cue
    COOLDOWN: dict[str, float] = defaultdict(lambda: 10.0)

    def __init__(self, config):
        self.config     = config
        self._enabled   = getattr(config, 'VOICE_COACH_ENABLED', True)
        self._engine    = None
        self._queue: deque = deque(maxlen=5)
        self._last_spoken: dict[str, float] = {}
        self._thread    = None

        if self._enabled:
            self._init_tts()
            self._start_worker()

    # ------------------------------------------------------------------
    def _init_tts(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 165)
            engine.setProperty('volume', 0.9)
            self._engine = ('pyttsx3', engine)
            print("[VOICE] pyttsx3 TTS initialised.")
            return
        except Exception:
            pass
        try:
            import importlib
            importlib.import_module('gtts')
            self._engine = ('gtts', None)
            print("[VOICE] gTTS initialised (requires internet).")
            return
        except Exception:
            pass
        # Espeak test
        import subprocess
        try:
            subprocess.run(['espeak', '--version'],
                           capture_output=True, check=True)
            self._engine = ('espeak', None)
            print("[VOICE] espeak TTS initialised.")
        except Exception:
            self._engine = ('print', None)
            print("[VOICE] No TTS engine found – text-only coaching.")

    # ------------------------------------------------------------------
    def _start_worker(self):
        """Background thread drains the speech queue."""
        self._running = True
        self._thread  = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        while self._running:
            if self._queue:
                text = self._queue.popleft()
                self._speak_now(text)
            time.sleep(0.1)

    # ------------------------------------------------------------------
    def advise(self, event_type: str, score: float = None):
        """Enqueue a coaching cue for the given event."""
        if not self._enabled:
            return
        key = event_type.upper()
        now = time.time()
        cooldown = self.COOLDOWN[key]
        if now - self._last_spoken.get(key, 0) < cooldown:
            return

        message = self.MESSAGES.get(key)
        if message is None:
            return

        self._last_spoken[key] = now
        self._queue.append(message)
        print(f"[VOICE] Queued: {message}")

    # ------------------------------------------------------------------
    def _speak_now(self, text: str):
        if self._engine is None:
            return
        kind, engine = self._engine

        if kind == 'pyttsx3':
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"[VOICE] pyttsx3 error: {e}")

        elif kind == 'gtts':
            try:
                from gtts import gTTS
                import tempfile, os
                tts  = gTTS(text=text, lang='en', slow=False)
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    tts.save(tmp.name)
                    tmp_path = tmp.name
                # Play with available player
                for player in ('mpg123', 'ffplay', 'aplay'):
                    try:
                        import subprocess
                        subprocess.run([player, '-q', tmp_path],
                                       capture_output=True, timeout=10)
                        break
                    except Exception:
                        continue
                os.unlink(tmp_path)
            except Exception as e:
                print(f"[VOICE] gTTS error: {e}")

        elif kind == 'espeak':
            try:
                import subprocess
                subprocess.run(['espeak', '-s', '150', text],
                               capture_output=True, timeout=10)
            except Exception as e:
                print(f"[VOICE] espeak error: {e}")

        else:
            print(f"[VOICE COACH] {text}")

    # ------------------------------------------------------------------
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

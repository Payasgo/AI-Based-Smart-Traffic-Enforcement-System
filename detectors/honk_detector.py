"""
Honk / horn detection using real-time audio analysis.
Detects high-energy audio bursts in the horn frequency band.
"""

import time
import threading
import numpy as np
from datetime import datetime


class HonkDetector:
    """
    Listens to the microphone in a background thread and flags
    horn-like sounds based on energy and frequency band filtering.
    """

    def __init__(self, config, logger, alert_system):
        self.config       = config
        self.logger       = logger
        self.alert_system = alert_system
        self.running      = False
        self._last_alert  = 0
        self._lock        = threading.Lock()

    def start_listening(self):
        """Blocking loop — run in a daemon thread."""
        try:
            import pyaudio
        except ImportError:
            print("[WARNING] PyAudio not installed. Honk detection disabled.")
            return

        pa     = pyaudio.PyAudio()
        stream = None
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config.AUDIO_SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.config.AUDIO_CHUNK_SIZE,
            )
            print("[INFO] Honk detector listening...")
            self.running = True
            while self.running:
                data   = stream.read(self.config.AUDIO_CHUNK_SIZE, exception_on_overflow=False)
                frames = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                if self._is_honk(frames):
                    now = time.time()
                    with self._lock:
                        if now - self._last_alert > self.config.HONK_COOLDOWN_SEC:
                            self._last_alert = now
                            self._handle_honk(datetime.now())
        except Exception as e:
            print(f"[WARNING] Audio stream error: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()

    def stop(self):
        self.running = False

    def _is_honk(self, frames):
        """
        Two-stage check:
        1. RMS energy must exceed threshold.
        2. Dominant frequency must fall in the horn band.
        """
        rms = np.sqrt(np.mean(frames ** 2))
        if rms < self.config.HONK_ENERGY_THRESH:
            return False

        # FFT-based frequency check
        fft_mag  = np.abs(np.fft.rfft(frames))
        freqs    = np.fft.rfftfreq(len(frames), d=1.0 / self.config.AUDIO_SAMPLE_RATE)
        band_mask = (freqs >= self.config.HONK_FREQ_LOW_HZ) & (freqs <= self.config.HONK_FREQ_HIGH_HZ)
        band_energy = fft_mag[band_mask].sum()
        total_energy = fft_mag.sum()

        # Horn is present if >40% of energy is in the horn band
        return (total_energy > 0) and (band_energy / total_energy > 0.40)

    def _handle_honk(self, timestamp):
        print(f"[VIOLATION] HONKING detected at {timestamp}")
        self.logger.log_violation(
            violation_type="HONKING",
            license_plate="AUDIO_ONLY",
            speed_kmh=None,
            timestamp=timestamp,
            evidence_path=None
        )
        self.alert_system.send_alert("HONKING", "AUDIO_ONLY", None, timestamp)

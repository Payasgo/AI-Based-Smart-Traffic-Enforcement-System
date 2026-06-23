"""
License plate OCR using pytesseract.
"""

import cv2
import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not installed. License plate OCR disabled.")


def read_plate(frame: np.ndarray, bbox: tuple) -> str:
    """
    Crop the vehicle region, preprocess, and OCR the license plate.
    Returns the plate string or empty string.
    """
    if not TESSERACT_AVAILABLE:
        return ""

    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]

    # Focus on lower portion of vehicle (where plates typically appear)
    plate_y1 = y1 + int((y2 - y1) * 0.6)
    crop = frame[max(0, plate_y1):min(h, y2), max(0, x1):min(w, x2)]

    if crop.size == 0:
        return ""

    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Upscale for better OCR
        scaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        # Threshold
        _, thresh = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        config = "--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        text = pytesseract.image_to_string(thresh, config=config).strip()
        # Clean noise characters
        plate = "".join(c for c in text if c.isalnum()).upper()
        if len(plate) >= 4:
            return plate
    except Exception as e:
        logger.debug(f"OCR error: {e}")
    return ""

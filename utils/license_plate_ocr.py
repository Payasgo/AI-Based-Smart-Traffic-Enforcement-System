"""
License plate OCR utility using OpenCV pre-processing + Tesseract.
"""

import cv2
import numpy as np


def extract_license_plate(frame, bbox, tesseract_cmd=None):
    """
    Attempt to read a license plate from within the given bounding box.

    Parameters
    ----------
    frame        : BGR numpy array
    bbox         : (x1, y1, x2, y2) coordinates
    tesseract_cmd: optional path to tesseract binary

    Returns
    -------
    plate_text : str  ("UNKNOWN" on failure)
    plate_roi  : BGR numpy array of the plate region
    """
    try:
        import pytesseract
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    except ImportError:
        return "UNKNOWN", None

    x1, y1, x2, y2 = bbox
    # Focus on the lower portion of the bounding box (where plates usually are)
    plate_y1 = int(y1 + (y2 - y1) * 0.65)
    roi = frame[max(0, plate_y1):y2, max(0, x1):x2]

    if roi.size == 0:
        return "UNKNOWN", roi

    # Pre-processing pipeline
    gray     = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    resized  = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    blurred  = cv2.GaussianBlur(resized, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    config = "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    text = pytesseract.image_to_string(thresh, config=config).strip()
    text = "".join(c for c in text if c.isalnum())

    return text if len(text) >= 4 else "UNKNOWN", roi

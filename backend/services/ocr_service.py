import os
import re
from typing import Dict, List, Any, Optional
import numpy as np
from PIL import Image
from ..core.logging import logger

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

from pathlib import Path

COMMON_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    str(Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/bin/tesseract",
]

class OCRService:
    def __init__(self):
        self.tesseract_configured = False
        self.easyocr_reader = None
        self._check_tesseract()

    def _check_tesseract(self):
        if not PYTESSERACT_AVAILABLE:
            return
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd and os.path.exists(env_cmd):
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            self.tesseract_configured = True
            return

        for p in COMMON_TESSERACT_PATHS:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                self.tesseract_configured = True
                return

        try:
            pytesseract.get_tesseract_version()
            self.tesseract_configured = True
        except Exception:
            self.tesseract_configured = False

    @property
    def is_engine_available(self) -> bool:
        """Indicates if at least one OCR backend (Tesseract or EasyOCR) is configured or importable."""
        return self.tesseract_configured or EASYOCR_AVAILABLE or (self.easyocr_reader is not None)

    def _get_easyocr_reader(self):
        if self.easyocr_reader is None and EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
            except Exception as e:
                logger.warning(f"Could not initialize EasyOCR reader: {e}")
        return self.easyocr_reader

    def extract_text(self, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Extracts raw text, line tokens, and bounding boxes.
        Computes explicit OCR confidence from token confidence scores.
        Distinguishes between valid text extraction and unreadable negative results.
        """
        raw_text = ""
        words = []
        confidences = []

        # 1. Try Tesseract first
        if self.tesseract_configured and PYTESSERACT_AVAILABLE:
            try:
                data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
                tess_text = pytesseract.image_to_string(pil_image)
                n_boxes = len(data.get("text", []))
                for i in range(n_boxes):
                    txt = data["text"][i].strip()
                    conf = float(data["conf"][i])
                    if txt and conf > 0:
                        words.append({
                            "text": txt,
                            "confidence": conf,
                            "bbox": [data["left"][i], data["top"][i], data["width"][i], data["height"][i]]
                        })
                        confidences.append(conf)

                raw_text = tess_text.strip()
                mean_conf = round(float(np.mean(confidences)), 1) if confidences else 0.0

                if len(raw_text) > 10 and mean_conf > 30.0:
                    return {
                        "engine": "tesseract",
                        "raw_text": raw_text,
                        "words": words,
                        "ocr_confidence": mean_conf,
                        "success": True
                    }
                else:
                    logger.info("Tesseract yielded low character confidence. Cascading to EasyOCR.")
            except Exception as e:
                logger.warning(f"Tesseract execution error: {e}. Cascading to EasyOCR.")

        # 2. Try EasyOCR fallback if text is sparse or low-confidence
        reader = self._get_easyocr_reader()
        if reader is not None:
            try:
                img_np = np.array(pil_image.convert("RGB"))
                results = reader.readtext(img_np)
                words = []
                lines = []
                confidences = []
                for bbox, text, prob in results:
                    txt = text.strip()
                    if not txt:
                        continue
                    prob_pct = round(float(prob) * 100.0, 1)
                    confidences.append(prob_pct)
                    xs = [pt[0] for pt in bbox]
                    ys = [pt[1] for pt in bbox]
                    x_min = int(min(xs))
                    y_min = int(min(ys))
                    w = int(max(xs) - x_min)
                    h = int(max(ys) - y_min)
                    words.append({
                        "text": txt,
                        "confidence": prob_pct,
                        "bbox": [x_min, y_min, w, h]
                    })
                    lines.append(txt)

                easy_text = "\n".join(lines).strip()
                mean_conf = round(float(np.mean(confidences)), 1) if confidences else 0.0

                if easy_text:
                    return {
                        "engine": "easyocr_deeplearning",
                        "raw_text": easy_text,
                        "words": words,
                        "ocr_confidence": mean_conf,
                        "success": True
                    }
            except Exception as e:
                logger.warning(f"EasyOCR fallback failed: {e}")

        # If Tesseract returned some text earlier, use it even if short
        if raw_text:
            mean_conf = round(float(np.mean(confidences)), 1) if confidences else 0.0
            return {
                "engine": "tesseract",
                "raw_text": raw_text,
                "words": words,
                "ocr_confidence": mean_conf,
                "success": True
            }

        # 3. Explicit Unreadable / Negative State (Never fabricates)
        return {
            "engine": "none",
            "raw_text": "",
            "words": [],
            "ocr_confidence": 0.0,
            "success": False,
            "note": "Document image contains no legible or recognizable text."
        }

ocr_service = OCRService()

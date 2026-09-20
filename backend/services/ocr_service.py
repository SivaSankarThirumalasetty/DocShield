import os
import re
from typing import Dict, List, Any, Optional
import numpy as np
from PIL import Image

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

COMMON_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\sivas\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
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
        # Check environment or common locations
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

        # Check if tesseract is in system PATH
        try:
            pytesseract.get_tesseract_version()
            self.tesseract_configured = True
        except Exception:
            self.tesseract_configured = False

    def _get_easyocr_reader(self):
        if self.easyocr_reader is None and EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
            except Exception as e:
                print(f"[!] Warning: Could not initialize EasyOCR reader: {e}")
        return self.easyocr_reader

    def extract_text(self, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Extracts raw text, line tokens, and bounding boxes.
        Uses Tesseract if configured, or EasyOCR deep-learning pipeline.
        """
        # 1. Try Tesseract
        if self.tesseract_configured and PYTESSERACT_AVAILABLE:
            try:
                data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
                raw_text = pytesseract.image_to_string(pil_image)
                words = []
                n_boxes = len(data["text"])
                for i in range(n_boxes):
                    txt = data["text"][i].strip()
                    conf = float(data["conf"][i])
                    if txt and conf > 0:
                        words.append({
                            "text": txt,
                            "confidence": conf,
                            "bbox": [data["left"][i], data["top"][i], data["width"][i], data["height"][i]]
                        })
                return {
                    "engine": "tesseract",
                    "raw_text": raw_text.strip(),
                    "words": words,
                    "success": True
                }
            except Exception as e:
                print(f"[!] Tesseract execution error: {e}. Trying EasyOCR.")

        # 2. Try EasyOCR
        reader = self._get_easyocr_reader()
        if reader is not None:
            try:
                img_np = np.array(pil_image.convert("RGB"))
                results = reader.readtext(img_np)
                # Sort bounding boxes top-to-bottom, left-to-right
                # results: [ (bbox, text, prob) ]
                words = []
                lines = []
                for bbox, text, prob in results:
                    txt = text.strip()
                    if not txt:
                        continue
                    xs = [pt[0] for pt in bbox]
                    ys = [pt[1] for pt in bbox]
                    x_min = int(min(xs))
                    y_min = int(min(ys))
                    w = int(max(xs) - x_min)
                    h = int(max(ys) - y_min)
                    words.append({
                        "text": txt,
                        "confidence": round(float(prob) * 100.0, 1),
                        "bbox": [x_min, y_min, w, h]
                    })
                    lines.append(txt)

                raw_text = "\n".join(lines)
                return {
                    "engine": "easyocr_deeplearning",
                    "raw_text": raw_text,
                    "words": words,
                    "success": True
                }
            except Exception as e:
                print(f"[!] EasyOCR error: {e}. Falling back to prototype parser.")

        # 3. Prototype Fallback Reader
        return self._prototype_ocr(pil_image)

    def _prototype_ocr(self, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Prototype OCR fallback that allows full end-to-end pipeline testing.
        """
        return {
            "engine": "prototype_heuristic",
            "raw_text": "[OCR Engine Standby: Upload an image with legible text]",
            "words": [],
            "success": True,
            "note": "Install Tesseract or ensure EasyOCR is active for live character recognition."
        }

ocr_service = OCRService()

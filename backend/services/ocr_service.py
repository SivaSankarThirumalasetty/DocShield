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

# Same Tesseract engine via its C library (wheel bundles libtesseract). Used where no
# `tesseract` executable can be installed, e.g. serverless Python runtimes.
try:
    import tesserocr
    TESSEROCR_AVAILABLE = True
except ImportError:
    TESSEROCR_AVAILABLE = False

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

OCR_UPSCALE = 2
OCR_UPSCALE_BELOW_PX = 1700  # documents are resized to <= 1600 px before OCR


def resolve_tessdata_dir() -> Optional[str]:
    for candidate in [
        os.environ.get("TESSDATA_PREFIX"),
        str(Path(__file__).resolve().parent.parent / "tessdata"),
    ]:
        if candidate and (Path(candidate) / "eng.traineddata").exists():
            return candidate
    return None


class OCRService:
    def __init__(self):
        self.tesseract_configured = False
        # "cli" (pytesseract + tesseract binary) or "library" (tesserocr + libtesseract)
        self.tesseract_mode: Optional[str] = None
        self.tessdata_dir: Optional[str] = None
        self.easyocr_reader = None
        self.easyocr_error: Optional[str] = None
        self._check_tesseract()

    def _check_tesseract(self):
        self._check_tesseract_cli()
        if self.tesseract_configured:
            self.tesseract_mode = "cli"
            return
        if TESSEROCR_AVAILABLE:
            self.tessdata_dir = resolve_tessdata_dir()
            if self.tessdata_dir:
                try:
                    with tesserocr.PyTessBaseAPI(path=self.tessdata_dir, lang="eng"):
                        pass
                    self.tesseract_configured = True
                    self.tesseract_mode = "library"
                except Exception as e:
                    logger.warning(f"tesserocr could not initialise: {type(e).__name__}")

    def _check_tesseract_cli(self):
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
        """True only when an OCR engine is actually usable (binary found or model loaded)."""
        return self.tesseract_configured or (self.easyocr_reader is not None)

    def warm_up(self) -> None:
        """Loads the EasyOCR model eagerly so readiness reflects real usability."""
        self._get_easyocr_reader()

    def status(self) -> Dict[str, Any]:
        return {
            "tesseract": self.tesseract_configured,
            "tesseract_mode": self.tesseract_mode,
            "easyocr_installed": EASYOCR_AVAILABLE,
            "easyocr_loaded": self.easyocr_reader is not None,
        }

    def _get_easyocr_reader(self):
        if self.easyocr_reader is None and EASYOCR_AVAILABLE:
            try:
                model_dir = None
                for candidate in [
                    Path(__file__).resolve().parent.parent / "models_weights" / "easyocr",
                    Path.cwd() / "backend" / "models_weights" / "easyocr",
                    Path.cwd() / "models_weights" / "easyocr",
                    Path("/app/backend/models_weights/easyocr"),
                    Path("/app/models_weights/easyocr"),
                ]:
                    if (candidate / "craft_mlt_25k.pth").exists() and (candidate / "english_g2.pth").exists():
                        model_dir = str(candidate)
                        break
                # Production images bake the weights in; never download at request time.
                download_enabled = os.environ.get("EASYOCR_DOWNLOAD_ENABLED", "true").lower() in ("true", "1", "yes")
                self.easyocr_reader = easyocr.Reader(
                    ['en'],
                    gpu=False,
                    model_storage_directory=model_dir,
                    download_enabled=download_enabled,
                    verbose=False,
                )
                self.easyocr_error = None
            except Exception as e:
                self.easyocr_error = type(e).__name__
                logger.warning(f"Could not initialize EasyOCR reader: {e}")
        return self.easyocr_reader

    def _tesseract_words(self, pil_image: Image.Image):
        """Runs Tesseract (CLI or library) and returns (text, words, confidences)."""
        # Tesseract is unreliable when glyphs are only ~10-15 px tall, which is typical of
        # small scans and phone screenshots. Upscale small images for OCR only (other
        # stages keep the original pixels) and map word boxes back to original coordinates.
        scale = OCR_UPSCALE if max(pil_image.size) < OCR_UPSCALE_BELOW_PX else 1
        if scale != 1:
            pil_image = pil_image.resize(
                (pil_image.width * scale, pil_image.height * scale), Image.Resampling.BICUBIC
            )
        text, words, confidences = self._tesseract_words_raw(pil_image)
        if scale != 1:
            for w in words:
                w["bbox"] = [int(v / scale) for v in w["bbox"]]
        return text, words, confidences

    def _tesseract_words_raw(self, pil_image: Image.Image):
        words: List[Dict[str, Any]] = []
        confidences: List[float] = []
        if self.tesseract_mode == "library":
            with tesserocr.PyTessBaseAPI(path=self.tessdata_dir, lang="eng") as api:
                api.SetImage(pil_image.convert("RGB"))
                text = api.GetUTF8Text()
                it = api.GetIterator()
                level = tesserocr.RIL.WORD
                if it is not None:
                    while True:
                        txt = (it.GetUTF8Text(level) or "").strip()
                        conf = float(it.Confidence(level))
                        box = it.BoundingBox(level)
                        if txt and conf > 0 and box:
                            x1, y1, x2, y2 = box
                            words.append({"text": txt, "confidence": conf, "bbox": [x1, y1, x2 - x1, y2 - y1]})
                            confidences.append(conf)
                        if not it.Next(level):
                            break
            return text, words, confidences

        data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(pil_image)
        for i in range(len(data.get("text", []))):
            txt = data["text"][i].strip()
            conf = float(data["conf"][i])
            if txt and conf > 0:
                words.append({
                    "text": txt,
                    "confidence": conf,
                    "bbox": [data["left"][i], data["top"][i], data["width"][i], data["height"][i]]
                })
                confidences.append(conf)
        return text, words, confidences

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
        if self.tesseract_configured:
            try:
                tess_text, words, confidences = self._tesseract_words(pil_image)
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

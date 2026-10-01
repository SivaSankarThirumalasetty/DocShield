import io
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
from typing import Tuple, List, Optional
from ..models.schemas import TamperAnalysisResult
from ..utils.image_utils import pil_to_base64
from ..core.logging import logger

FORENSIC_LIMITATIONS = [
    "Error Level Analysis (ELA) evaluates JPEG compression quantization discrepancies only.",
    "Cannot detect physical forgery, holographic alterations, substrate tampering, or optical variable ink.",
    "Multiple social media re-compression cycles (e.g. WhatsApp/Telegram) may elevate background noise or produce false anomalies.",
    "Must be evaluated by a trained document forensics examiner alongside physical security checks."
]

class TamperingService:
    def __init__(self, ela_quality: int = 90):
        self.ela_quality = ela_quality

    def compute_ela(self, pil_image: Image.Image) -> Tuple[Image.Image, float, List[List[int]], float]:
        """
        Error Level Analysis (ELA) as an advisory forensic signal.
        Returns: (enhanced_diff_img, anomaly_score, bounding_boxes, confidence)
        """
        rgb_img = pil_image.convert("RGB")
        w, h = rgb_img.size
        
        # 1. Compute resolution-based confidence
        # Images below 400x300 have insufficient DCT block resolution for ELA
        resolution_pixels = w * h
        if resolution_pixels < 120_000:
            analysis_confidence = 35.0
        elif resolution_pixels < 500_000:
            analysis_confidence = 65.0
        else:
            analysis_confidence = 85.0

        # 2. Resave in memory at fixed JPEG quality
        buffer = io.BytesIO()
        rgb_img.save(buffer, "JPEG", quality=self.ela_quality)
        buffer.seek(0)
        resaved_img = Image.open(buffer)

        # 3. Compute absolute difference
        ela_diff = ImageChops.difference(rgb_img, resaved_img)
        extrema = ela_diff.getextrema()
        max_diff = max([ex[1] for ex in extrema]) if extrema else 1
        if max_diff == 0:
            max_diff = 1

        scale = 255.0 / max_diff
        enhanced_ela = ImageEnhance.Brightness(ela_diff).enhance(scale)

        diff_arr = np.array(ela_diff)
        gray_diff = cv2.cvtColor(diff_arr, cv2.COLOR_RGB2GRAY)
        
        mean_val = float(np.mean(gray_diff))
        std_val = float(np.std(gray_diff))
        
        # Anomaly threshold: 3 standard deviations above mean, minimum 20
        anomaly_threshold = mean_val + 3.0 * std_val
        _, thresh = cv2.threshold(gray_diff, max(20, int(anomaly_threshold)), 255, cv2.THRESH_BINARY)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bounding_boxes = []
        min_box_area = resolution_pixels * 0.005  # At least 0.5% of total document area
        for c in contours:
            area = cv2.contourArea(c)
            if area > min_box_area:
                x, y, wb, hb = cv2.boundingRect(c)
                bounding_boxes.append([int(x), int(y), int(wb), int(hb)])

        raw_score = (mean_val * 2.5) + (std_val * 2.0) + (len(bounding_boxes) * 8.0)
        ela_score = float(min(100.0, max(0.0, raw_score)))

        return enhanced_ela, ela_score, bounding_boxes, analysis_confidence

    def analyze(self, pil_image: Image.Image) -> TamperAnalysisResult:
        try:
            enhanced_ela, ela_score, boxes, conf = self.compute_ela(pil_image)
            ela_base64 = pil_to_base64(enhanced_ela, format="JPEG", quality=85)
            
            notes = []
            has_anomalies = len(boxes) > 0 or ela_score > 55.0
            
            if ela_score > 65.0:
                notes.append("Significant compression discrepancy detected across multiple document patches; secondary manual forensic verification recommended.")
                evidence_state = "FAIL"
            elif ela_score > 40.0:
                notes.append("Moderate localized error-level variance observed. Further manual forensic review advised.")
                evidence_state = "INDETERMINATE"
            else:
                notes.append("Uniform compression profile consistent with authentic unaltered digital capture.")
                evidence_state = "PASS"

            if boxes:
                notes.append(f"{len(boxes)} patch region(s) identified with localized compression discontinuities.")

            return TamperAnalysisResult(
                ela_score=round(ela_score, 1),
                has_anomalies=has_anomalies,
                anomaly_regions=len(boxes),
                bounding_boxes=boxes,
                ela_image_base64=ela_base64,
                analysis_confidence=conf,
                forensic_notes=notes,
                forensic_limitations=FORENSIC_LIMITATIONS,
                evidence_state=evidence_state
            )
        except Exception as e:
            logger.error(f"Forensic ELA analysis error: {e}")
            return TamperAnalysisResult(
                ela_score=0.0,
                has_anomalies=False,
                anomaly_regions=0,
                bounding_boxes=[],
                ela_image_base64=None,
                analysis_confidence=0.0,
                forensic_notes=[f"Forensic analysis notice: Analysis unavailable ({str(e)})"],
                forensic_limitations=FORENSIC_LIMITATIONS,
                evidence_state="UNAVAILABLE"
            )

tampering_service = TamperingService()

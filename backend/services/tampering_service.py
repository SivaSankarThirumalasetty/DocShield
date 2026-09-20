import io
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
from typing import Tuple, List, Optional
from ..models.schemas import TamperAnalysisResult
from ..utils.image_utils import pil_to_base64

class TamperingService:
    def __init__(self, ela_quality: int = 90, scale_factor: float = 15.0):
        self.ela_quality = ela_quality
        self.scale_factor = scale_factor

    def compute_ela(self, pil_image: Image.Image) -> Tuple[Image.Image, float, List[List[int]]]:
        """
        In-memory Error Level Analysis (adapted from 02_tampering notebooks).
        Performs JPEG recompression in RAM and computes pixel error discrepancy.
        """
        rgb_img = pil_image.convert("RGB")
        
        # In-memory resave with fixed JPEG compression
        buffer = io.BytesIO()
        rgb_img.save(buffer, "JPEG", quality=self.ela_quality)
        buffer.seek(0)
        resaved_img = Image.open(buffer)

        # Difference between original and recompressed
        ela_diff = ImageChops.difference(rgb_img, resaved_img)

        # Calculate difference extrema
        extrema = ela_diff.getextrema()
        max_diff = max([ex[1] for ex in extrema]) if extrema else 1
        if max_diff == 0:
            max_diff = 1

        scale = 255.0 / max_diff
        enhanced_ela = ImageEnhance.Brightness(ela_diff).enhance(scale)

        # Convert difference to numpy array to find anomaly bounding boxes
        diff_arr = np.array(ela_diff)
        gray_diff = cv2.cvtColor(diff_arr, cv2.COLOR_RGB2GRAY)
        
        # Calculate mean error score (0 to 100 normalized)
        mean_val = float(np.mean(gray_diff))
        std_val = float(np.std(gray_diff))
        
        # Anomalies show up as high local deviations in error level
        anomaly_threshold = mean_val + 2.5 * std_val
        _, thresh = cv2.threshold(gray_diff, max(12, int(anomaly_threshold)), 255, cv2.THRESH_BINARY)
        
        # Morphological filter to merge small speckles into distinct suspicious zones
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bounding_boxes = []
        min_box_area = (rgb_img.width * rgb_img.height) * 0.002  # at least 0.2% of doc area
        for c in contours:
            area = cv2.contourArea(c)
            if area > min_box_area:
                x, y, w, h = cv2.boundingRect(c)
                bounding_boxes.append([int(x), int(y), int(w), int(h)])

        # Calculate normalized tampering risk score (0 - 100)
        # Low variance and low mean = uniform original image
        # High spikes in difference = spliced or digitally altered regions
        raw_score = (mean_val * 4.0) + (std_val * 3.5) + (len(bounding_boxes) * 6.0)
        ela_score = float(min(100.0, max(0.0, raw_score)))

        return enhanced_ela, ela_score, bounding_boxes

    def analyze(self, pil_image: Image.Image) -> TamperAnalysisResult:
        try:
            enhanced_ela, ela_score, boxes = self.compute_ela(pil_image)
            ela_base64 = pil_to_base64(enhanced_ela, format="JPEG", quality=85)
            
            notes = []
            has_anomalies = len(boxes) > 0 or ela_score > 40.0
            
            if ela_score > 60.0:
                notes.append("High compression discrepancy detected across multiple document regions.")
            elif ela_score > 35.0:
                notes.append("Moderate localized error-level variance observed. Secondary forensic verification advised.")
            else:
                notes.append("Uniform compression profile consistent with authentic unaltered digital capture.")

            if boxes:
                notes.append(f"{len(boxes)} suspicious region(s) identified with localized compression discontinuities.")

            return TamperAnalysisResult(
                ela_score=round(ela_score, 1),
                has_anomalies=has_anomalies,
                anomaly_regions=len(boxes),
                bounding_boxes=boxes,
                ela_image_base64=ela_base64,
                forensic_notes=notes
            )
        except Exception as e:
            return TamperAnalysisResult(
                ela_score=0.0,
                has_anomalies=False,
                anomaly_regions=0,
                bounding_boxes=[],
                ela_image_base64=None,
                forensic_notes=[f"Tamper analysis error: {str(e)}"]
            )

tampering_service = TamperingService()

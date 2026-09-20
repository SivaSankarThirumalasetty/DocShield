import os
import math
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional
from ..models.schemas import FaceVerificationResult
from ..utils.image_utils import cv2_to_base64, safe_crop

def resolve_weights_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "models_weights",
        Path(__file__).resolve().parent.parent / "backend" / "models_weights",
        Path(__file__).resolve().parent / "models_weights",
        Path.cwd() / "backend" / "models_weights",
        Path.cwd() / "models_weights",
        Path("/app/backend/models_weights"),
        Path("/app/models_weights"),
    ]
    for c in candidates:
        if (c / "deploy.prototxt").exists() and (c / "res10_300x300_ssd_iter_140000_fp16.caffemodel").exists():
            return c
    return candidates[0]

WEIGHTS_DIR = resolve_weights_dir()
PROTO_PATH = WEIGHTS_DIR / "deploy.prototxt"
MODEL_PATH = WEIGHTS_DIR / "res10_300x300_ssd_iter_140000_fp16.caffemodel"

# Try importing face_recognition
try:
    import face_recognition
    FACE_REC_AVAILABLE = True
except ImportError:
    FACE_REC_AVAILABLE = False

def face_distance_to_conf(face_distance: float, threshold: float = 0.6) -> float:
    """Adapted from 03_face_verification/face_compare.py"""
    if face_distance > 1.0:
        return 0.0
    if face_distance > threshold:
        r = 1.0 - threshold
        val = (1.0 - face_distance) / (r * 2.0)
        return max(0.0, min(1.0, val)) * 100.0
    else:
        r = threshold
        val = 1.0 - (face_distance / (r * 2.0))
        curved = val + ((1.0 - val) * math.pow(max(0.0, (val - 0.5) * 2), 0.2))
        return max(0.0, min(1.0, curved)) * 100.0

class FaceService:
    def __init__(self):
        self.net = None
        self.weights_dir = WEIGHTS_DIR
        self.load_error = None
        self._load_detector()

    def _load_detector(self):
        weights_dir = resolve_weights_dir()
        self.weights_dir = weights_dir
        proto_path = weights_dir / "deploy.prototxt"
        model_path = weights_dir / "res10_300x300_ssd_iter_140000_fp16.caffemodel"
        if proto_path.exists() and model_path.exists():
            try:
                # cv2.dnn.readNet(model, config) is the universal OpenCV DNN loader
                self.net = cv2.dnn.readNet(str(model_path), str(proto_path))
                print(f"[*] Caffe face detector successfully loaded with cv2.dnn.readNet from {weights_dir}")
            except Exception as e1:
                try:
                    if hasattr(cv2.dnn, 'readNetFromCaffe'):
                        self.net = cv2.dnn.readNetFromCaffe(str(proto_path), str(model_path))
                        print(f"[*] Caffe face detector loaded with readNetFromCaffe from {weights_dir}")
                    else:
                        raise e1
                except Exception as e2:
                    self.load_error = f"Error reading Caffe model: {str(e2)}"
                    print(f"[!] Warning: Could not load Caffe face detector: {e2}")
        else:
            self.load_error = f"Weights missing at {weights_dir} (proto={proto_path.exists()}, model={model_path.exists()})"
            print(f"[!] Warning: Face detection model weights missing at {weights_dir}")

    def detect_faces(self, cv_image: np.ndarray, conf_threshold: float = 0.5) -> List[Tuple[int, int, int, int]]:
        if self.net is None:
            # Fallback to Haar Cascade
            return self._haar_detect(cv_image)

        try:
            h, w = cv_image.shape[:2]
            blob = cv2.dnn.blobFromImage(cv_image, 1.0, (300, 300), [104, 117, 123], False, False)
            self.net.setInput(blob)
            detections = self.net.forward()
            
            boxes = []
            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])
                if confidence > conf_threshold:
                    x1 = int(detections[0, 0, i, 3] * w)
                    y1 = int(detections[0, 0, i, 4] * h)
                    x2 = int(detections[0, 0, i, 5] * w)
                    y2 = int(detections[0, 0, i, 6] * h)
                    # clamp
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    bw = max(1, min(x2 - x1, w - x1))
                    bh = max(1, min(y2 - y1, h - y1))
                    boxes.append((x1, y1, bw, bh))
            return boxes
        except Exception as e:
            print(f"[!] Caffe forward pass error: {e}")
            return self._haar_detect(cv_image)

    def _haar_detect(self, cv_image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        try:
            cascade_file = getattr(cv2.data, 'haarcascades', '') + 'haarcascade_frontalface_default.xml'
            if not os.path.isfile(cascade_file):
                return []
            face_cascade = cv2.CascadeClassifier(cascade_file)
            if face_cascade.empty():
                return []
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
        except Exception as e:
            print(f"[!] Haar detection warning: {e}")
            return []

    def crop_primary_face(self, cv_image: np.ndarray, is_document: bool = False) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
        boxes = self.detect_faces(cv_image)
        h, w = cv_image.shape[:2]
        
        # If not detected at full scale (common on small ID card portraits), inspect left and right portrait quadrants
        if not boxes and w > 250 and h > 150:
            left_w = int(w * 0.45)
            left_sub = cv_image[:, :left_w]
            left_boxes = self.detect_faces(left_sub, conf_threshold=0.35)
            if left_boxes:
                boxes = left_boxes
            else:
                right_start = int(w * 0.55)
                right_sub = cv_image[:, right_start:]
                right_boxes = self.detect_faces(right_sub, conf_threshold=0.35)
                if right_boxes:
                    boxes = [(bx + right_start, by, bw, bh) for (bx, by, bw, bh) in right_boxes]

        if not boxes:
            # Heuristic candidate crop fallback for ID documents or traveller portraits
            if is_document and w > 200 and h > 150:
                # Standard ID portrait is in the left 40%
                cand_w = int(w * 0.38)
                cand_h = int(h * 0.55)
                box = (int(w * 0.04), int(h * 0.15), cand_w, cand_h)
                return safe_crop(cv_image, box), box
            elif not is_document and w > 100 and h > 100:
                # Live person selfie is center 70%
                cand_w = int(w * 0.70)
                cand_h = int(h * 0.75)
                box = (int(w * 0.15), int(h * 0.10), cand_w, cand_h)
                return safe_crop(cv_image, box), box
            return None, None
            
        # Select largest bounding box by area
        best_box = max(boxes, key=lambda b: b[2] * b[3])
        # Add slight margin
        x, y, w_box, h_box = best_box
        margin_x = int(w_box * 0.15)
        margin_y = int(h_box * 0.20)
        box_with_margin = (max(0, x - margin_x), max(0, y - margin_y), w_box + 2 * margin_x, h_box + 2 * margin_y)
        crop = safe_crop(cv_image, box_with_margin)
        return crop, best_box

    def verify_faces(self, doc_cv: np.ndarray, person_cv: Optional[np.ndarray]) -> FaceVerificationResult:
        doc_crop, doc_box = self.crop_primary_face(doc_cv, is_document=True)
        doc_detected = doc_crop is not None
        doc_crop_b64 = cv2_to_base64(doc_crop) if doc_detected else None

        if person_cv is None:
            return FaceVerificationResult(
                document_face_detected=doc_detected,
                person_face_detected=False,
                similarity_score=0.0,
                match_verdict="NOT_APPLICABLE",
                document_face_crop_base64=doc_crop_b64,
                notes="No live person/selfie image provided for biometric verification."
            )

        person_crop, person_box = self.crop_primary_face(person_cv, is_document=False)
        person_detected = person_crop is not None
        person_crop_b64 = cv2_to_base64(person_crop) if person_detected else None

        if not doc_detected or not person_detected:
            reasons = []
            if not doc_detected: reasons.append("Document portrait not detected")
            if not person_detected: reasons.append("Live person face not detected")
            return FaceVerificationResult(
                document_face_detected=doc_detected,
                person_face_detected=person_detected,
                similarity_score=0.0,
                match_verdict="INDETERMINATE",
                document_face_crop_base64=doc_crop_b64,
                person_face_crop_base64=person_crop_b64,
                notes="; ".join(reasons)
            )

        # Facial embedding comparison
        if FACE_REC_AVAILABLE:
            try:
                rgb_doc = cv2.cvtColor(doc_crop, cv2.COLOR_BGR2RGB)
                rgb_person = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
                enc_doc = face_recognition.face_encodings(rgb_doc)
                enc_person = face_recognition.face_encodings(rgb_person)

                if enc_doc and enc_person:
                    dist = float(face_recognition.face_distance([enc_doc[0]], enc_person[0])[0])
                    sim = face_distance_to_conf(dist, threshold=0.6)
                    verdict = "MATCH" if dist <= 0.6 else "MISMATCH"
                    return FaceVerificationResult(
                        document_face_detected=True,
                        person_face_detected=True,
                        similarity_score=round(sim, 1),
                        match_verdict=verdict,
                        face_distance=round(dist, 4),
                        document_face_crop_base64=doc_crop_b64,
                        person_face_crop_base64=person_crop_b64,
                        notes=f"Deep 128-d face embedding verification (Euclidean distance: {round(dist, 3)})"
                    )
            except Exception as e:
                print(f"[!] Warning: face_recognition calculation failed: {e}")

        # Prototype fallback feature correlation
        gray_doc = cv2.resize(cv2.cvtColor(doc_crop, cv2.COLOR_BGR2GRAY), (100, 100))
        gray_pers = cv2.resize(cv2.cvtColor(person_crop, cv2.COLOR_BGR2GRAY), (100, 100))
        corr = cv2.matchTemplate(gray_doc, gray_pers, cv2.TM_CCOEFF_NORMED)[0][0]
        sim = float(max(0.0, min(100.0, (corr + 1.0) / 2.0 * 100.0)))
        verdict = "MATCH" if sim >= 65.0 else "MISMATCH"
        return FaceVerificationResult(
            document_face_detected=True,
            person_face_detected=True,
            similarity_score=round(sim, 1),
            match_verdict=verdict,
            face_distance=round(1.0 - (sim / 100.0), 3),
            document_face_crop_base64=doc_crop_b64,
            person_face_crop_base64=person_crop_b64,
            notes="Fallback template correlation matcher (Prototype mode)"
        )

face_service = FaceService()

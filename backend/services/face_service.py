import os
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional
from ..models.schemas import FaceVerificationResult
from ..utils.image_utils import cv2_to_base64, safe_crop
from ..core.logging import logger

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

try:
    import face_recognition
    FACE_REC_AVAILABLE = True
except ImportError:
    FACE_REC_AVAILABLE = False
    logger.warning("Biometric face_recognition package is not installed.")

MIN_FACE_DIMENSION = 45  # Pixels: faces below 45x45 are too small for reliable biometric embedding

def face_distance_to_conf(face_distance: float, threshold: float = 0.6) -> float:
    """Calculates linear biometric match confidence without arbitrary curve inflation."""
    if face_distance > 1.0:
        return 0.0
    conf = max(0.0, min(100.0, (1.0 - (face_distance / (threshold * 1.5))) * 100.0))
    return round(conf, 1)

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
                self.net = cv2.dnn.readNet(str(model_path), str(proto_path))
                logger.info(f"Caffe face detector loaded from {weights_dir}")
            except Exception as e1:
                try:
                    if hasattr(cv2.dnn, 'readNetFromCaffe'):
                        self.net = cv2.dnn.readNetFromCaffe(str(proto_path), str(model_path))
                        logger.info(f"Caffe face detector loaded via readNetFromCaffe from {weights_dir}")
                    else:
                        raise e1
                except Exception as e2:
                    self.load_error = f"Error reading Caffe model: {str(e2)}"
                    logger.warning(f"Could not load Caffe face detector: {e2}")
        else:
            self.load_error = f"Weights missing at {weights_dir}"
            logger.warning(f"Face detection model weights missing at {weights_dir}")

    def detect_all_faces(self, cv_image: np.ndarray, conf_threshold: float = 0.45) -> List[Tuple[int, int, int, int]]:
        """Detects all faces in an image and returns their bounding boxes."""
        if self.net is None:
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
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    bw = max(1, min(x2 - x1, w - x1))
                    bh = max(1, min(y2 - y1, h - y1))
                    boxes.append((x1, y1, bw, bh))
            return boxes
        except Exception as e:
            logger.warning(f"Caffe face detection error: {e}. Falling back to Haar.")
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
            logger.warning(f"Haar face detection error: {e}")
            return []

    def _locate_and_crop(self, cv_image: np.ndarray, is_document: bool = False) -> Tuple[Optional[np.ndarray], int, List[str], Optional[Tuple[int, int, int, int]]]:
        boxes = self.detect_all_faces(cv_image)
        h, w = cv_image.shape[:2]
        quality_flags = []

        # Quadrant search fallback for small ID portraits
        if not boxes and is_document and w > 250 and h > 150:
            left_w = int(w * 0.45)
            left_boxes = self.detect_all_faces(cv_image[:, :left_w], conf_threshold=0.35)
            if left_boxes:
                boxes = left_boxes

        face_count = len(boxes)

        if face_count == 0:
            quality_flags.append("NO_FACE_DETECTED")
            return None, 0, quality_flags, None

        if face_count > 1:
            quality_flags.append("MULTIPLE_FACES_DETECTED")

        # Pick primary face by area
        best_box = max(boxes, key=lambda b: b[2] * b[3])
        x, y, w_box, h_box = best_box

        # Quality check: Resolution
        if w_box < MIN_FACE_DIMENSION or h_box < MIN_FACE_DIMENSION:
            quality_flags.append("FACE_TOO_SMALL")
            return None, face_count, quality_flags, best_box

        # Add margin and crop
        margin_x = int(w_box * 0.15)
        margin_y = int(h_box * 0.20)
        box_with_margin = (max(0, x - margin_x), max(0, y - margin_y), w_box + 2 * margin_x, h_box + 2 * margin_y)
        crop = safe_crop(cv_image, box_with_margin)

        return crop, face_count, quality_flags, best_box

    def crop_face_with_quality(self, cv_image: np.ndarray, is_document: bool = False) -> Tuple[Optional[np.ndarray], int, List[str]]:
        """
        Detects faces and evaluates quality.
        Returns: (crop, face_count, quality_flags)
        """
        crop, face_count, quality_flags, _ = self._locate_and_crop(cv_image, is_document=is_document)
        return crop, face_count, quality_flags

    @staticmethod
    def _extract_embedding(full_cv: np.ndarray, crop_cv: np.ndarray, box: Optional[Tuple[int, int, int, int]]):
        rgb_crop = cv2.cvtColor(crop_cv, cv2.COLOR_BGR2RGB)
        encs = face_recognition.face_encodings(rgb_crop)
        if encs:
            return encs
        if box is not None:
            x, y, w_box, h_box = box
            rgb_full = cv2.cvtColor(full_cv, cv2.COLOR_BGR2RGB)
            encs = face_recognition.face_encodings(
                rgb_full,
                known_face_locations=[(y, x + w_box, y + h_box, x)]
            )
            if encs:
                return encs
        return []

    def verify_faces(self, doc_cv: np.ndarray, person_cv: Optional[np.ndarray]) -> FaceVerificationResult:
        doc_crop, doc_count, doc_flags, doc_box = self._locate_and_crop(doc_cv, is_document=True)
        doc_detected = doc_crop is not None
        doc_crop_b64 = cv2_to_base64(doc_crop) if doc_detected else None

        # Scenario: Document-only verification (no live selfie provided)
        if person_cv is None:
            return FaceVerificationResult(
                document_face_detected=doc_detected,
                person_face_detected=False,
                similarity_score=0.0,
                match_verdict="NOT_APPLICABLE",
                face_count_doc=doc_count,
                face_count_person=0,
                quality_flags=doc_flags,
                document_face_crop_base64=doc_crop_b64,
                notes="Live traveller photograph omitted (Document screening only).",
                evidence_state="NOT_APPLICABLE"
            )

        person_crop, person_count, person_flags, person_box = self._locate_and_crop(person_cv, is_document=False)
        person_detected = person_crop is not None
        person_crop_b64 = cv2_to_base64(person_crop) if person_detected else None

        combined_quality = list(set(doc_flags + person_flags))

        # Check for multiple faces
        if "MULTIPLE_FACES_DETECTED" in combined_quality:
            return FaceVerificationResult(
                document_face_detected=doc_detected,
                person_face_detected=person_detected,
                similarity_score=0.0,
                match_verdict="INDETERMINATE",
                face_count_doc=doc_count,
                face_count_person=person_count,
                quality_flags=combined_quality,
                document_face_crop_base64=doc_crop_b64,
                person_face_crop_base64=person_crop_b64,
                notes="Multiple faces detected in input image. Biometric screening requires a single person portrait.",
                evidence_state="INDETERMINATE"
            )

        # Check for tiny faces
        if "FACE_TOO_SMALL" in combined_quality:
            return FaceVerificationResult(
                document_face_detected=doc_detected,
                person_face_detected=person_detected,
                similarity_score=0.0,
                match_verdict="INDETERMINATE",
                face_count_doc=doc_count,
                face_count_person=person_count,
                quality_flags=combined_quality,
                document_face_crop_base64=doc_crop_b64,
                person_face_crop_base64=person_crop_b64,
                notes=f"Detected face crop is below minimum biometric resolution ({MIN_FACE_DIMENSION}px). Image quality insufficient.",
                evidence_state="INDETERMINATE"
            )

        # Check for absent faces
        if not doc_detected or not person_detected:
            reasons = []
            if not doc_detected: reasons.append("Document portrait not detected")
            if not person_detected: reasons.append("Live person face not detected")
            return FaceVerificationResult(
                document_face_detected=doc_detected,
                person_face_detected=person_detected,
                similarity_score=0.0,
                match_verdict="INDETERMINATE",
                face_count_doc=doc_count,
                face_count_person=person_count,
                quality_flags=combined_quality,
                document_face_crop_base64=doc_crop_b64,
                person_face_crop_base64=person_crop_b64,
                notes="; ".join(reasons) + ". Cannot complete biometric comparison.",
                evidence_state="INDETERMINATE"
            )

        # Check model availability
        if not FACE_REC_AVAILABLE:
            return FaceVerificationResult(
                document_face_detected=True,
                person_face_detected=True,
                similarity_score=0.0,
                match_verdict="NOT_AVAILABLE",
                face_count_doc=doc_count,
                face_count_person=person_count,
                quality_flags=combined_quality,
                document_face_crop_base64=doc_crop_b64,
                person_face_crop_base64=person_crop_b64,
                notes="Biometric face embedding engine (dlib ResNet) is offline. Manual comparison required.",
                evidence_state="UNAVAILABLE"
            )

        try:
            enc_doc = self._extract_embedding(doc_cv, doc_crop, doc_box)
            enc_person = self._extract_embedding(person_cv, person_crop, person_box)

            if enc_doc and enc_person:
                dist = float(face_recognition.face_distance([enc_doc[0]], enc_person[0])[0])
                sim = face_distance_to_conf(dist, threshold=0.6)
                verdict = "MATCH" if dist <= 0.6 else "MISMATCH"
                evidence_state = "PASS" if dist <= 0.6 else "FAIL"

                return FaceVerificationResult(
                    document_face_detected=True,
                    person_face_detected=True,
                    similarity_score=sim,
                    match_verdict=verdict,
                    face_distance=round(dist, 4),
                    face_count_doc=doc_count,
                    face_count_person=person_count,
                    quality_flags=combined_quality,
                    document_face_crop_base64=doc_crop_b64,
                    person_face_crop_base64=person_crop_b64,
                    notes=f"Deep 128-d Euclidean embedding comparison (Distance: {round(dist, 3)}, Threshold: 0.60)",
                    evidence_state=evidence_state
                )
            else:
                return FaceVerificationResult(
                    document_face_detected=True,
                    person_face_detected=True,
                    similarity_score=0.0,
                    match_verdict="INDETERMINATE",
                    face_count_doc=doc_count,
                    face_count_person=person_count,
                    quality_flags=combined_quality + ["LANDMARK_ALIGNMENT_FAILED"],
                    document_face_crop_base64=doc_crop_b64,
                    person_face_crop_base64=person_crop_b64,
                    notes="Facial landmarks could not be aligned or encoded. Image lighting/angle too severe.",
                    evidence_state="INDETERMINATE"
                )
        except Exception as e:
            logger.error(f"Biometric calculation error: {e}")
            return FaceVerificationResult(
                document_face_detected=True,
                person_face_detected=True,
                similarity_score=0.0,
                match_verdict="INDETERMINATE",
                face_count_doc=doc_count,
                face_count_person=person_count,
                quality_flags=combined_quality,
                document_face_crop_base64=doc_crop_b64,
                person_face_crop_base64=person_crop_b64,
                notes=f"Biometric embedding calculation failed: {str(e)}",
                evidence_state="INDETERMINATE"
            )

face_service = FaceService()

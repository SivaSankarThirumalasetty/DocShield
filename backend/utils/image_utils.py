import cv2
import numpy as np
import base64
import io
from PIL import Image
from typing import Tuple, Optional

def bytes_to_cv2(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes.")
    return img

def cv2_to_pil(cv_img: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)

def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    rgb = np.array(pil_img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

def cv2_to_base64(cv_img: np.ndarray, format: str = "JPEG", quality: int = 85) -> str:
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    buffer = io.BytesIO()
    pil_img.save(buffer, format=format, quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime = "image/jpeg" if format.upper() == "JPEG" else "image/png"
    return f"data:{mime};base64,{encoded}"

def pil_to_base64(pil_img: Image.Image, format: str = "JPEG", quality: int = 85) -> str:
    buffer = io.BytesIO()
    if format.upper() == "JPEG" and pil_img.mode in ("RGBA", "LA", "P"):
        pil_img = pil_img.convert("RGB")
    pil_img.save(buffer, format=format, quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime = "image/jpeg" if format.upper() == "JPEG" else "image/png"
    return f"data:{mime};base64,{encoded}"

def get_skew_angle(cv_image: np.ndarray) -> float:
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (9, 9), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilate = cv2.dilate(thresh, kernel, iterations=2)
    contours, _ = cv2.findContours(dilate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    if len(contours) == 0:
        return 0.0
    largest_contour = contours[0]
    min_area_rect = cv2.minAreaRect(largest_contour)
    angle = min_area_rect[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        if angle < -45:
            angle = (90 + angle)
    return float(angle)

def rotate_image(cv_image: np.ndarray, angle: float) -> np.ndarray:
    (h, w) = cv_image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(cv_image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def deskew(cv_image: np.ndarray, angle_threshold: float = 1.0) -> Tuple[np.ndarray, float]:
    try:
        angle = get_skew_angle(cv_image)
        if abs(angle) > angle_threshold and abs(angle) < 45.0:
            return rotate_image(cv_image, -angle), angle
        return cv_image, 0.0
    except Exception:
        return cv_image, 0.0

def safe_crop(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    x, y, w, h = bbox
    ih, iw = image.shape[:2]
    x1 = max(0, min(x, iw - 1))
    y1 = max(0, min(y, ih - 1))
    x2 = max(x1 + 1, min(x + w, iw))
    y2 = max(y1 + 1, min(y + h, ih))
    cropped = image[y1:y2, x1:x2]
    if cropped.size == 0:
        return None
    return cropped

def resize_if_larger(image: np.ndarray, max_dim: int = 1600) -> np.ndarray:
    h, w = image.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return image

import io
import pytest
from fastapi import HTTPException
from PIL import Image
from backend.core.security import validate_image_upload, detect_mime_from_bytes, mask_aadhaar_number

def test_detect_mime_jpeg():
    # Standard JPEG header
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00" + b"\x00" * 50
    assert detect_mime_from_bytes(jpeg_bytes) == "image/jpeg"

def test_detect_mime_png():
    # Standard PNG header
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
    assert detect_mime_from_bytes(png_bytes) == "image/png"

def test_reject_fake_extension():
    # A text file disguised as a JPEG
    fake_bytes = b"Hello, this is not an image file at all!"
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload(fake_bytes, field_name="test_doc")
    assert exc_info.value.status_code == 400
    assert "Invalid file format" in exc_info.value.detail

def test_reject_empty_upload():
    with pytest.raises(HTTPException) as exc_info:
        validate_image_upload(b"", field_name="test_doc")
    assert exc_info.value.status_code == 400
    assert "is empty" in exc_info.value.detail

def test_accept_valid_image():
    # Create valid in-memory PNG
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(buf, format="PNG")
    valid_bytes = buf.getvalue()

    validated = validate_image_upload(valid_bytes, field_name="test_doc")
    assert validated.size == (100, 100)

def test_aadhaar_masking():
    raw_aadhaar = "Aadhaar number is 5489 1234 9876 in the document"
    masked = mask_aadhaar_number(raw_aadhaar)
    assert "XXXX-XXXX-9876" in masked
    assert "5489 1234" not in masked

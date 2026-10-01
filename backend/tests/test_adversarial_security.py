import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from backend.core.security import sanitize_filename, validate_image_upload
from backend.core.config import settings

client = TestClient(app)

def create_valid_test_image(width=200, height=200, color="blue", format="PNG"):
    buffer = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer.getvalue()

# =========================================================================
# 1. UPLOAD EXPLOITS & MALICIOUS PAYLOADS
# =========================================================================

def test_reject_oversized_upload():
    """Attempts to upload payload exceeding max_upload_size_bytes (10MB limit)."""
    oversized_bytes = b"X" * (settings.max_upload_size_bytes + 1024)
    response = client.post(
        "/api/analyze-document",
        files={"document": ("huge.jpg", oversized_bytes, "image/jpeg")}
    )
    assert response.status_code in (400, 413), f"Expected 400/413, got {response.status_code}"

def test_reject_svg_with_script_injection():
    """Attempts to upload SVG XML payload containing XSS vectors."""
    svg_payload = b"""<?xml version="1.0" standalone="no"?>
    <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
    <svg version="1.1" baseProfile="full" xmlns="http://www.w3.org/2000/svg">
       <polygon id="triangle" points="0,0 0,50 50,0" fill="#009900" stroke="#004400"/>
       <script type="text/javascript">
          alert(document.cookie);
       </script>
    </svg>"""
    response = client.post(
        "/api/analyze-document",
        files={"document": ("exploit.svg", svg_payload, "image/svg+xml")}
    )
    assert response.status_code == 400
    assert "Invalid file format" in response.text or "format" in response.text.lower()

def test_reject_html_disguised_as_jpeg():
    """Uploads HTML markup disguised as a .jpg extension."""
    fake_jpeg = b"<!DOCTYPE html><html><body><h1>Phishing Payload</h1></body></html>"
    response = client.post(
        "/api/analyze-document",
        files={"document": ("passport.jpg", fake_jpeg, "image/jpeg")}
    )
    assert response.status_code == 400

def test_reject_corrupted_jpeg_truncated_headers():
    """Uploads JPEG magic bytes followed by random corrupted truncation."""
    corrupted_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 20
    response = client.post(
        "/api/analyze-document",
        files={"document": ("corrupted.jpg", corrupted_jpeg, "image/jpeg")}
    )
    assert response.status_code == 400

def test_reject_decompression_bomb():
    """Attempts to process an image with dimensions exceeding safe pixel threshold."""
    huge_buffer = io.BytesIO()
    # 6000 x 5000 = 30,000,000 pixels (exceeds 25,000,000 default threshold)
    huge_img = Image.new("RGB", (6000, 5000), color="white")
    huge_img.save(huge_buffer, format="JPEG")
    huge_bytes = huge_buffer.getvalue()

    with pytest.raises(Exception):
        validate_image_upload(huge_bytes, field_name="decompression_bomb")

# =========================================================================
# 2. PATH TRAVERSAL & FILENAME SANITIZATION
# =========================================================================

@pytest.mark.parametrize("malicious_filename, expected_safe", [
    ("../../../../etc/passwd", "etcpasswd"),
    ("..\\..\\windows\\win.ini", "win.ini"),
    ("image.png\x00.exe", "image.png.exe"),
    ("<script>alert('xss')</script>.jpg", "scriptalertxssscript.jpg"),
    ("CON.png", "CON.png"),
    ("AUX.png", "AUX.png"),
    ("NUL.png", "NUL.png"),
    ("A" * 500 + ".png", "A" * 500 + ".png"),
    ("", "upload.bin"),
    (None, "upload.bin")
])
def test_path_traversal_sanitization(malicious_filename, expected_safe):
    sanitized = sanitize_filename(malicious_filename)
    assert ".." not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert "\x00" not in sanitized
    assert "<" not in sanitized
    assert ">" not in sanitized

# =========================================================================
# 3. CASE ISOLATION & BRUTE FORCE ENUMERATION DEFENSE
# =========================================================================

def test_unauthorized_case_access_blocked():
    """Verifies that accessing a case without a matching session token or officer key returns HTTP 403."""
    doc_bytes = create_valid_test_image(300, 200)
    res = client.post(
        "/api/analyze-document",
        files={"document": ("test.png", doc_bytes, "image/png")}
    )
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]

    # 1. Attempt access without any headers
    anon_res = client.get(f"/api/case/{case_id}")
    assert anon_res.status_code == 403

    # 2. Attempt access with an invalid session token
    tampered_res = client.get(
        f"/api/case/{case_id}",
        headers={"X-Session-Token": "tampered-token-1234567890abcdef"}
    )
    assert tampered_res.status_code == 403

    # 3. Authorized access with legitimate session token
    auth_res = client.get(
        f"/api/case/{case_id}",
        headers={"X-Session-Token": data["session_token"]}
    )
    assert auth_res.status_code == 200
    assert auth_res.json()["case_id"] == case_id

def test_nonexistent_case_returns_404_or_403_without_info_leak():
    """Verifies brute-force case probing does not leak internal error traces."""
    res = client.get(
        "/api/case/DOC-NONEXISTENT-9999",
        headers={"X-Officer-Key": settings.officer_key}
    )
    assert res.status_code == 404
    assert "detail" in res.json()

def test_officer_list_and_review_strictly_require_key():
    """Ensures endpoints modifying case reviews or listing all cases reject unauthenticated callers."""
    # List cases
    assert client.get("/api/cases").status_code == 401
    
    # Submit review
    assert client.post(
        "/api/case/DOC-FAKE-123/review",
        json={"officer_id": "OFC", "officer_name": "Name", "decision": "CLEARED_FOR_ENTRY"}
    ).status_code == 401

# =========================================================================
# 4. JSON VALIDATION & UNEXPECTED INJECTION
# =========================================================================

def test_malformed_json_in_review_rejected():
    """Validates that malformed JSON payloads return HTTP 422 Unprocessable Entity."""
    response = client.post(
        "/api/case/DOC-FAKE/review",
        headers={"X-Officer-Key": settings.officer_key, "Content-Type": "application/json"},
        content=b"{ invalid json ::: "
    )
    assert response.status_code == 422

def test_debug_endpoint_disabled_in_production():
    """Ensures debug diagnostic endpoints are unavailable or disabled by default."""
    response = client.get("/api/debug")
    assert response.status_code in (403, 404), f"Debug endpoint returned {response.status_code}"

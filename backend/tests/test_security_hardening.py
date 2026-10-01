import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.main import app
from backend.core.config import settings
from backend.core.security import sanitize_filename

client = TestClient(app)

def create_valid_test_image():
    img = Image.new("RGB", (200, 150), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf

def test_security_headers_present():
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    
    # Anti-Caching Directives
    assert "no-store" in headers.get("cache-control", "")
    assert "no-cache" in headers.get("cache-control", "")
    assert headers.get("pragma") == "no-cache"
    
    # Defensive Security Headers
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert "frame-ancestors 'none'" in headers.get("content-security-policy", "")

def test_path_traversal_sanitization():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("safe_image_123.jpg") == "safe_image_123.jpg"
    assert sanitize_filename("bad;file$name!.png") == "badfilename.png"

def test_case_authorization_workflow():
    # 1. Analyze a document to create a case
    buf = create_valid_test_image()
    res = client.post(
        "/api/analyze-document",
        files={"document": ("passport.jpg", buf, "image/jpeg")}
    )
    assert res.status_code == 200
    data = res.json()
    case_id = data["case_id"]
    session_token = data.get("session_token")
    assert session_token is not None

    # 2. Access without session token or officer key -> must be FORBIDDEN (403)
    unauthorized_res = client.get(f"/api/case/{case_id}")
    assert unauthorized_res.status_code == 403
    assert "Access denied" in unauthorized_res.json()["detail"]

    # 3. Access with invalid session token -> must be FORBIDDEN (403)
    bad_token_res = client.get(
        f"/api/case/{case_id}",
        headers={"X-Session-Token": "invalid_fake_token_12345"}
    )
    assert bad_token_res.status_code == 403

    # 4. Access with valid session token -> must SUCCEED (200)
    authorized_res = client.get(
        f"/api/case/{case_id}",
        headers={"X-Session-Token": session_token}
    )
    assert authorized_res.status_code == 200
    assert authorized_res.json()["case_id"] == case_id

    # 5. Access with Officer Key -> must SUCCEED (200)
    officer_res = client.get(
        f"/api/case/{case_id}",
        headers={"X-Officer-Key": settings.officer_key}
    )
    assert officer_res.status_code == 200
    assert officer_res.json()["case_id"] == case_id

def test_list_cases_officer_authorization():
    # Attempting to list all cases without officer key must be rejected (401)
    unauthorized = client.get("/api/cases")
    assert unauthorized.status_code == 401
    assert "Officer authorization token missing" in unauthorized.json()["detail"]

    # Listing cases with valid officer key must succeed (200)
    authorized = client.get(
        "/api/cases",
        headers={"X-Officer-Key": settings.officer_key}
    )
    assert authorized.status_code == 200
    assert isinstance(authorized.json(), list)

def test_officer_review_authorization():
    # Create case
    buf = create_valid_test_image()
    res = client.post(
        "/api/analyze-document",
        files={"document": ("doc.jpg", buf, "image/jpeg")}
    )
    case_id = res.json()["case_id"]

    review_payload = {
        "officer_id": "TEST-OFC-1",
        "officer_name": "Test Officer",
        "decision": "CLEARED_FOR_ENTRY",
        "notes": "Verified"
    }

    # Attempt review without officer key -> 401
    unauthorized_review = client.post(
        f"/api/case/{case_id}/review",
        json=review_payload
    )
    assert unauthorized_review.status_code == 401

    # Attempt review with valid officer key -> 200
    authorized_review = client.post(
        f"/api/case/{case_id}/review",
        headers={"X-Officer-Key": settings.officer_key},
        json=review_payload
    )
    assert authorized_review.status_code == 200
    assert authorized_review.json()["officer_review"]["decision"] == "CLEARED_FOR_ENTRY"

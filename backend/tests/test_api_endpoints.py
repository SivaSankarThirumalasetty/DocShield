import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.main import app

client = TestClient(app)

def test_liveness_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"

def test_readiness_endpoint():
    res = client.get("/ready")
    assert res.status_code in [200, 503]
    data = res.json()
    assert "status" in data
    assert "checks" in data
    assert "database" in data["checks"]

def test_api_health_backward_compatibility():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "modules" in data

def test_debug_endpoint_disabled_by_default():
    res = client.get("/api/debug")
    # Debug endpoint must return 404 when disabled
    assert res.status_code == 404

def test_analyze_document_validation_failure():
    # Attempting to upload fake non-image file
    fake_file = io.BytesIO(b"Not a real image file content")
    response = client.post(
        "/api/analyze-document",
        files={"document": ("fake.jpg", fake_file, "image/jpeg")}
    )
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]

def test_analyze_document_success():
    # Create valid synthetic document image
    img = Image.new("RGB", (300, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/api/analyze-document",
        files={"document": ("test_passport.jpg", buf, "image/jpeg")},
        data={"doc_type_hint": "PASSPORT"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "case_id" in data
    assert "risk_assessment" in data
    assert "document_info" in data

    # Verify the created case can be fetched with session token
    case_id = data["case_id"]
    session_token = data.get("session_token")
    assert session_token is not None
    get_res = client.get(f"/api/case/{case_id}", headers={"X-Session-Token": session_token})
    assert get_res.status_code == 200
    assert get_res.json()["case_id"] == case_id

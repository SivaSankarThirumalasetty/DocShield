"""Behaviour of the stateless container mode used in the Cloudflare deployment,
plus data-minimisation and readiness guarantees."""
import json
import os
import subprocess
import sys
from pathlib import Path

from backend.core.redaction import mask_document_number, redact_result_for_storage

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_in_fresh_process(code: str, **env) -> dict:
    """Settings are read at import time, so mode changes need a fresh interpreter."""
    full_env = {**os.environ, **env}
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=full_env,
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


STATELESS_PROBE = r"""
import io, json
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app
c = TestClient(app)
buf = io.BytesIO(); Image.new("RGB", (400, 300), "white").save(buf, "PNG")
r = c.post("/api/analyze-document", files={"document": ("d.png", buf.getvalue(), "image/png")})
body = r.json()
print(json.dumps({
    "status": r.status_code,
    "token": body.get("session_token"),
    "persistence": body.get("persistence"),
    "pipeline": [s["stage"] for s in body.get("pipeline", [])],
    "case_get": c.get("/api/case/" + body["case_id"]).status_code,
    "cases": c.get("/api/cases", headers={"X-Officer-Key": "x"}).status_code,
    "ready_has_db": "database" in c.get("/ready").json()["checks"],
}))
"""


def test_stateless_mode_never_issues_tokens_or_stores_cases():
    res = _run_in_fresh_process(STATELESS_PROBE, PERSISTENCE_MODE="none", DOCSHIELD_OFFICER_KEY="")
    assert res["status"] == 200
    assert res["token"] is None
    assert res["persistence"] == {"status": "NOT_STORED", "backend": "none"}
    assert res["case_get"] == 404
    assert res["cases"] == 401
    assert res["ready_has_db"] is False
    for stage in ("image_decoding", "ocr", "format_and_checksum_validation",
                  "simulated_registry_check", "image_forensics_ela", "face_comparison", "risk_scoring"):
        assert stage in res["pipeline"]


NO_KEY_PROBE = r"""
import json
from fastapi.testclient import TestClient
from backend.main import app
c = TestClient(app)
print(json.dumps({
    "empty": c.get("/api/cases", headers={"X-Officer-Key": ""}).status_code,
    "guess": c.get("/api/cases", headers={"X-Officer-Key": "docshield-officer-secret-key-change-in-production"}).status_code,
}))
"""


def test_officer_endpoints_closed_when_no_key_configured(tmp_path):
    res = _run_in_fresh_process(
        NO_KEY_PROBE, DOCSHIELD_OFFICER_KEY="", DATABASE_URL=f"sqlite:///{tmp_path / 'k.db'}"
    )
    assert res == {"empty": 401, "guess": 401}


READY_PROBE = r"""
import json
from fastapi.testclient import TestClient
from backend.main import app
r = TestClient(app).get("/ready")
print(json.dumps({"status": r.status_code, "body": r.json()}))
"""


def test_readiness_fails_when_full_pipeline_required_but_models_absent(tmp_path):
    # This development venv has no EasyOCR model loaded, so readiness must be 503.
    res = _run_in_fresh_process(
        READY_PROBE, REQUIRE_FULL_PIPELINE="true", DATABASE_URL=f"sqlite:///{tmp_path / 'r.db'}"
    )
    body = res["body"]
    if all(body["checks"][k] for k in body["required"]):
        return  # Running inside the full production image: everything genuinely loaded.
    assert res["status"] == 503
    assert body["status"] == "not_ready"
    assert "ocr_easyocr" in body["required"]


def test_mask_document_number():
    assert mask_document_number("367598346125", "AADHAAR") == "XXXX-XXXX-6125"
    assert mask_document_number("3675 9834 6125") == "XXXX-XXXX-6125"
    assert mask_document_number("Z2098451", "PASSPORT") == "****8451"
    assert mask_document_number("ABCDE1234F", "PAN") == "******234F"
    assert mask_document_number(None) is None


def test_redaction_removes_images_text_and_identity_fields():
    full = {
        "case_id": "DS-1",
        "document_preview_base64": "data:image/jpeg;base64,AAAA",
        "person_preview_base64": "data:image/jpeg;base64,BBBB",
        "session_token": "secret",
        "document_info": {
            "document_type": "AADHAAR", "document_number": "367598346125", "name": "Aarav Sharma",
            "dob": "1994-08-14", "address": "Civil Lines", "father_or_spouse_name": "X",
            "mrz_lines": ["P<IND"], "mrz_data": {"a": 1}, "raw_text_preview": "3675 9834 6125 Aarav",
        },
        "tampering": {"ela_image_base64": "data:..."},
        "face_verification": {"document_face_crop_base64": "a", "person_face_crop_base64": "b"},
        "watchlist": {"matched_name": "Someone"},
        "risk_assessment": {"reasons": ["number 3675 9834 6125 seen"]},
    }
    red = redact_result_for_storage(full)
    blob = json.dumps(red)
    for secret in ("AAAA", "BBBB", "secret", "Aarav", "Civil Lines", "1994-08-14", "Someone", "367598346125", "3675 9834"):
        assert secret not in blob
    assert red["document_info"]["document_number"] == "XXXX-XXXX-6125"
    assert red["redacted"] is True
    # The original is not mutated.
    assert full["document_info"]["name"] == "Aarav Sharma"


EDGE_PROBE = r"""
import io, json, base64
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app
c = TestClient(app)
buf = io.BytesIO(); Image.new("RGB", (400, 300), "white").save(buf, "PNG")
ok = c.post("/api/analyze-document", headers={"X-DocShield-Edge-Auth": "edge-s3cret"},
            files={"document": ("d.png", buf.getvalue(), "image/png")})
rec = json.loads(base64.urlsafe_b64decode(ok.headers["X-DocShield-Case-Record"]))
print(json.dumps({
    "no_secret": c.get("/api/ready").status_code,
    "wrong_secret": c.get("/api/ready", headers={"X-DocShield-Edge-Auth": "nope"}).status_code,
    "health_open": c.get("/health").status_code,
    "ok": ok.status_code,
    "record_case": rec["case_id"] == ok.json()["case_id"],
    "record_redacted": rec.get("redacted") is True and rec["document_preview_base64"] is None,
    "body_has_preview": ok.json()["document_preview_base64"] is not None,
}))
"""


def test_edge_secret_and_redacted_record_header():
    res = _run_in_fresh_process(EDGE_PROBE, PERSISTENCE_MODE="none", EDGE_SHARED_SECRET="edge-s3cret")
    assert res == {
        "no_secret": 401, "wrong_secret": 401, "health_open": 200, "ok": 200,
        "record_case": True, "record_redacted": True, "body_has_preview": True,
    }


def test_ready_requires_override():
    res = _run_in_fresh_process(READY_PROBE, PERSISTENCE_MODE="none", READY_REQUIRES="demo_registry,face_detector")
    assert res["body"]["required"] == ["demo_registry", "face_detector"]
    assert res["status"] == 200

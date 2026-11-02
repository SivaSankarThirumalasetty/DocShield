"""
Data minimisation applied to a screening result before it is persisted.

The submitter receives the full computed result once, in the HTTP response.
Persisted case records keep only what a reviewer needs to understand the
automated assessment: no images, no OCR text, no names, dates of birth,
addresses or MRZ lines, and only a masked document number.

The Cloudflare Worker applies the same rules (worker/src/redact.js); keep the
two implementations in sync.
"""
import re
from typing import Any, Dict, Optional

AADHAAR_PATTERN = re.compile(r"\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b")


def mask_document_number(number: Optional[str], document_type: Optional[str] = None) -> Optional[str]:
    if not number:
        return number
    if number.startswith("XXXX-XXXX-"):
        return number
    compact = re.sub(r"[\s-]", "", number)
    if (document_type or "").upper() == "AADHAAR" or (len(compact) == 12 and compact.isdigit()):
        return f"XXXX-XXXX-{compact[-4:]}" if len(compact) >= 4 else "XXXX"
    if len(compact) <= 4:
        return "*" * len(compact)
    return "*" * (len(compact) - 4) + compact[-4:]


def redact_result_for_storage(result: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a minimised copy of a ScreeningResult dict suitable for persistence."""
    data = dict(result)
    data["document_preview_base64"] = None
    data["person_preview_base64"] = None
    data["session_token"] = None

    info = dict(data.get("document_info") or {})
    info["document_number"] = mask_document_number(info.get("document_number"), info.get("document_type"))
    for field in ("name", "dob", "address", "father_or_spouse_name", "mrz_data"):
        info[field] = None
    info["mrz_lines"] = []
    info["raw_text_preview"] = ""
    data["document_info"] = info

    tampering = dict(data.get("tampering") or {})
    tampering["ela_image_base64"] = None
    data["tampering"] = tampering

    face = dict(data.get("face_verification") or {})
    face["document_face_crop_base64"] = None
    face["person_face_crop_base64"] = None
    data["face_verification"] = face

    watchlist = dict(data.get("watchlist") or {})
    watchlist["matched_name"] = None
    data["watchlist"] = watchlist

    risk = dict(data.get("risk_assessment") or {})
    risk["reasons"] = [AADHAAR_PATTERN.sub(r"XXXX-XXXX-\3", r) for r in risk.get("reasons", [])]
    data["risk_assessment"] = risk
    data["redacted"] = True
    return data

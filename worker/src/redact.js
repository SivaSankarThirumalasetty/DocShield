// Data minimisation applied before a screening result is written to D1.
// Mirrors backend/core/redaction.py; keep both implementations in sync.

const AADHAAR_PATTERN = /\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b/g;

export function maskDocumentNumber(number, documentType) {
  if (!number) return number ?? null;
  if (number.startsWith("XXXX-XXXX-")) return number;
  const compact = number.replace(/[\s-]/g, "");
  if ((documentType || "").toUpperCase() === "AADHAAR" || /^\d{12}$/.test(compact)) {
    return compact.length >= 4 ? `XXXX-XXXX-${compact.slice(-4)}` : "XXXX";
  }
  if (compact.length <= 4) return "*".repeat(compact.length);
  return "*".repeat(compact.length - 4) + compact.slice(-4);
}

export function redactResultForStorage(result) {
  const data = { ...result };
  data.document_preview_base64 = null;
  data.person_preview_base64 = null;
  data.session_token = null;

  const info = { ...(data.document_info || {}) };
  info.document_number = maskDocumentNumber(info.document_number, info.document_type);
  for (const field of ["name", "dob", "address", "father_or_spouse_name", "mrz_data"]) info[field] = null;
  info.mrz_lines = [];
  info.raw_text_preview = "";
  data.document_info = info;

  data.tampering = { ...(data.tampering || {}), ela_image_base64: null };
  data.face_verification = {
    ...(data.face_verification || {}),
    document_face_crop_base64: null,
    person_face_crop_base64: null,
  };
  data.watchlist = { ...(data.watchlist || {}), matched_name: null };

  const risk = { ...(data.risk_assessment || {}) };
  risk.reasons = (risk.reasons || []).map((r) => String(r).replace(AADHAAR_PATTERN, "XXXX-XXXX-$3"));
  data.risk_assessment = risk;
  data.redacted = true;
  return data;
}

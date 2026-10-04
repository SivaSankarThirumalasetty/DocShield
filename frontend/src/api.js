// Configurable API base URL for Cloudflare Worker/Container -> Python FastAPI backend communication.
// Development: defaults to "" (routed via Vite dev proxy to http://127.0.0.1:8000) or explicit VITE_API_BASE_URL.
// Production (Cloudflare): defaults to https://docshield.sivasankar-t1606.workers.dev (configurable via VITE_API_BASE_URL).
const DEFAULT_CLOUDFLARE_API_BASE = "https://docshield.sivasankar-t1606.workers.dev";
const rawApiBase = (
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : import.meta.env.PROD
    ? DEFAULT_CLOUDFLARE_API_BASE
    : ""
).trim();
export const API_BASE = rawApiBase.replace(/\/+$/, "");

const DEFAULT_TIMEOUT_MS = 45000;
const HEALTH_TIMEOUT_MS = 8000;

// Ephemeral in-memory session token store for active analysis
let currentSessionToken = null;
let currentOfficerKey = "";
try {
  currentOfficerKey =
    typeof window !== "undefined" && window.localStorage
      ? localStorage.getItem("docshield_officer_key") || ""
      : "";
} catch (_) {
  currentOfficerKey = "";
}

export function setOfficerKey(key) {
  currentOfficerKey = (key || "").trim();
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      if (currentOfficerKey) {
        localStorage.setItem("docshield_officer_key", currentOfficerKey);
      } else {
        localStorage.removeItem("docshield_officer_key");
      }
    }
  } catch (_) {}
}

export function getOfficerKey() {
  return currentOfficerKey;
}

export function getSessionToken() {
  return currentSessionToken;
}

function sanitizeErrorMessage(status, rawDetail) {
  if (status === 413) {
    return "File size exceeds the 10MB security limit. Please upload a smaller document scan.";
  }
  if (status === 415) {
    return "Unsupported file format. Only authentic JPEG, PNG, and WebP images are permitted.";
  }
  if (status === 429) {
    return "Rate limit reached for document screening. Please wait a moment and try again.";
  }
  if (status === 502 || status === 503 || status === 504) {
    return "Screening backend is currently warming up or temporarily unavailable. Please retry in a few seconds.";
  }

  if (typeof rawDetail === "string" && rawDetail.trim()) {
    const trimmed = rawDetail.trim();
    // Never expose raw HTML error pages or Python tracebacks to the user
    if (
      trimmed.startsWith("<!DOCTYPE") ||
      trimmed.startsWith("<html") ||
      trimmed.includes("Traceback (most recent call last)")
    ) {
      return "Verification processing error on the server. Please verify your document image and try again.";
    }
    return trimmed;
  }

  if (status === 400 || status === 422) {
    return "Invalid document upload or request format. Please upload a clear JPEG, PNG, or WebP image.";
  }
  if (status === 401 || status === 403) {
    return "Authorization required. Please provide a valid Officer Key or active session token.";
  }
  if (status === 404) {
    return "Requested screening record or endpoint was not found.";
  }
  return "Verification service error. Please ensure the backend is online and try again.";
}

async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new Error(
        "Document analysis timed out while waiting for OCR/biometric processing. The backend may be waking up from a cold start—please retry."
      );
    }
    throw new Error(
      "Screening backend is currently unreachable. Please check your connection or verify that the API server is online."
    );
  } finally {
    clearTimeout(timer);
  }
}

async function extractErrorFromResponse(res) {
  let detail = null;
  try {
    const errData = await res.json();
    if (errData && errData.detail) {
      detail =
        typeof errData.detail === "string"
          ? errData.detail
          : Array.isArray(errData.detail)
          ? errData.detail.map((e) => e.msg || JSON.stringify(e)).join("; ")
          : JSON.stringify(errData.detail);
    } else if (errData && errData.error) {
      detail = typeof errData.error === "string" ? errData.error : JSON.stringify(errData.error);
    }
  } catch (_) {
    try {
      const text = await res.text();
      if (text) detail = text;
    } catch (__) {}
  }
  return sanitizeErrorMessage(res.status, detail);
}

export async function checkHealth() {
  const res = await fetchWithTimeout(
    `${API_BASE}/api/health`,
    { headers: { "Cache-Control": "no-cache" } },
    HEALTH_TIMEOUT_MS
  );
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function analyzeDocument(docFile, personFile = null, docTypeHint = "auto") {
  if (!docFile) {
    throw new Error("Please select an identity document image to screen.");
  }
  if (docFile.size === 0) {
    throw new Error("Uploaded document file is empty (0 bytes).");
  }
  if (docFile.size > 10 * 1024 * 1024) {
    throw new Error("Uploaded document exceeds maximum allowed size of 10MB.");
  }
  if (personFile && personFile.size > 10 * 1024 * 1024) {
    throw new Error("Uploaded traveller photo exceeds maximum allowed size of 10MB.");
  }

  const formData = new FormData();
  formData.append("document", docFile);
  if (personFile) {
    formData.append("person_image", personFile);
  }
  if (docTypeHint && docTypeHint !== "auto") {
    formData.append("doc_type_hint", docTypeHint);
  }

  const res = await fetchWithTimeout(
    `${API_BASE}/api/analyze-document`,
    {
      method: "POST",
      body: formData,
    },
    DEFAULT_TIMEOUT_MS
  );

  if (!res.ok) {
    const msg = await extractErrorFromResponse(res);
    throw new Error(msg);
  }

  const data = await res.json();
  if (data && data.session_token) {
    currentSessionToken = data.session_token;
  }
  return data;
}

export async function verifyFace(image1File, image2File) {
  if (!image1File || !image2File) {
    throw new Error("Both portrait images are required for 1:1 biometric face verification.");
  }
  const formData = new FormData();
  formData.append("image1", image1File);
  formData.append("image2", image2File);

  const res = await fetchWithTimeout(
    `${API_BASE}/api/verify-face`,
    {
      method: "POST",
      body: formData,
    },
    DEFAULT_TIMEOUT_MS
  );

  if (!res.ok) {
    const msg = await extractErrorFromResponse(res);
    throw new Error(msg);
  }
  return res.json();
}

export async function getCase(caseId, sessionToken = null) {
  const token = sessionToken || currentSessionToken;
  const headers = { "Cache-Control": "no-cache" };
  if (token) headers["X-Session-Token"] = token;
  if (currentOfficerKey) headers["X-Officer-Key"] = currentOfficerKey;

  const res = await fetchWithTimeout(`${API_BASE}/api/case/${encodeURIComponent(caseId)}`, {
    headers,
  });
  if (!res.ok) {
    if (res.status === 403) throw new Error("Access denied: Authorization required to view case.");
    if (res.status === 404) throw new Error("Case not found.");
    const msg = await extractErrorFromResponse(res);
    throw new Error(msg);
  }
  return res.json();
}

export async function listCases() {
  const headers = { "Cache-Control": "no-cache" };
  if (currentOfficerKey) headers["X-Officer-Key"] = currentOfficerKey;

  const res = await fetchWithTimeout(`${API_BASE}/api/cases`, { headers });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Officer authorization required to view case history.");
    const msg = await extractErrorFromResponse(res);
    throw new Error(msg);
  }
  return res.json();
}

export async function submitOfficerReview(caseId, reviewData) {
  const headers = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
  };
  if (currentOfficerKey) headers["X-Officer-Key"] = currentOfficerKey;

  const res = await fetchWithTimeout(
    `${API_BASE}/api/case/${encodeURIComponent(caseId)}/review`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(reviewData),
    }
  );
  if (!res.ok) {
    const msg = await extractErrorFromResponse(res);
    throw new Error(msg);
  }
  return res.json();
}

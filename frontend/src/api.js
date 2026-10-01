const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

// Ephemeral in-memory session token store for active analysis
let currentSessionToken = null;
let currentOfficerKey = "";
try {
  currentOfficerKey = typeof window !== "undefined" && window.localStorage ? localStorage.getItem("docshield_officer_key") || "" : "";
} catch (_) {
  currentOfficerKey = "";
}

export function setOfficerKey(key) {
  currentOfficerKey = key || "";
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      if (key) {
        localStorage.setItem("docshield_officer_key", key);
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

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/api/health`, {
    headers: { "Cache-Control": "no-cache" }
  });
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function analyzeDocument(docFile, personFile = null, docTypeHint = "auto") {
  const formData = new FormData();
  formData.append("document", docFile);
  if (personFile) {
    formData.append("person_image", personFile);
  }
  if (docTypeHint && docTypeHint !== "auto") {
    formData.append("doc_type_hint", docTypeHint);
  }

  const res = await fetch(`${API_BASE}/api/analyze-document`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    let msg = "Verification service error. Please try again.";
    try {
      const errData = await res.json();
      if (errData && errData.detail) {
        msg = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch (_) {
      try {
        const text = await res.text();
        if (text) msg = `Verification service error: ${text}`;
      } catch (__) {}
    }
    throw new Error(msg);
  }

  const data = await res.json();
  if (data && data.session_token) {
    currentSessionToken = data.session_token;
  }
  return data;
}

export async function getCase(caseId, sessionToken = null) {
  const token = sessionToken || currentSessionToken;
  const headers = { "Cache-Control": "no-cache" };
  if (token) headers["X-Session-Token"] = token;
  if (currentOfficerKey) headers["X-Officer-Key"] = currentOfficerKey;

  const res = await fetch(`${API_BASE}/api/case/${caseId}`, { headers });
  if (!res.ok) {
    if (res.status === 403) throw new Error("Access denied: Authorization required to view case.");
    if (res.status === 404) throw new Error("Case not found.");
    throw new Error("Failed to fetch case details.");
  }
  return res.json();
}

export async function listCases() {
  const headers = { "Cache-Control": "no-cache" };
  if (currentOfficerKey) headers["X-Officer-Key"] = currentOfficerKey;

  const res = await fetch(`${API_BASE}/api/cases`, { headers });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Officer authorization required to view case history.");
    throw new Error("Failed to fetch cases");
  }
  return res.json();
}

export async function submitOfficerReview(caseId, reviewData) {
  const headers = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache"
  };
  if (currentOfficerKey) headers["X-Officer-Key"] = currentOfficerKey;

  const res = await fetch(`${API_BASE}/api/case/${caseId}/review`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(reviewData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to submit review: ${res.statusText}`);
  }
  return res.json();
}

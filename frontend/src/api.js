// API client. Production and local development are both same-origin:
// production goes through the Cloudflare Worker, local dev through the Vite proxy.
export const API_BASE = "";

const ANALYZE_TIMEOUT_MS = 150000; // includes a possible container cold start
const DEFAULT_TIMEOUT_MS = 30000;
const READY_TIMEOUT_MS = 95000;
const REVIEWER_TOKEN_KEY = "docshield_reviewer_token";

// Reviewer bearer token: kept for this browser tab only (sessionStorage), never localStorage.
let reviewerToken = "";
try {
  reviewerToken = window.sessionStorage.getItem(REVIEWER_TOKEN_KEY) || "";
} catch (_) {
  reviewerToken = "";
}

export function setReviewerToken(token) {
  reviewerToken = (token || "").trim();
  try {
    if (reviewerToken) window.sessionStorage.setItem(REVIEWER_TOKEN_KEY, reviewerToken);
    else window.sessionStorage.removeItem(REVIEWER_TOKEN_KEY);
  } catch (_) {
    // Storage unavailable (private mode / blocked): token stays in memory only.
  }
}

export function getReviewerToken() {
  return reviewerToken;
}

// The submitter's case token lives only in memory for the current page session.
let currentSessionToken = null;
export function getSessionToken() {
  return currentSessionToken;
}

function authHeaders() {
  return reviewerToken ? { Authorization: `Bearer ${reviewerToken}` } : {};
}

function sanitizeErrorMessage(status, rawDetail) {
  if (status === 413) return "File too large. Each image must be 10 MB or smaller.";
  if (status === 415) return "Unsupported upload. Only JPEG, PNG and WebP images are accepted.";
  if (status === 429) return "Too many requests. Please wait a minute and try again.";
  if (status === 503 || status === 504) {
    return "The screening engine is starting or busy. Please retry in a few seconds.";
  }
  if (status === 502) return "The screening engine returned an error. Please try again.";
  if (typeof rawDetail === "string" && rawDetail.trim() && rawDetail.length < 300 && !rawDetail.trim().startsWith("<")) {
    return rawDetail.trim();
  }
  if (status === 400 || status === 422) return "Invalid upload or request. Please use a clear JPEG, PNG or WebP image.";
  if (status === 401) return "Reviewer authentication required.";
  if (status === 404) return "Not found, or you are not authorised to view it.";
  return "Unexpected service error. Please try again.";
}

async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
  const external = options.signal;
  const onAbort = () => controller.abort("cancelled");
  if (external) external.addEventListener("abort", onAbort);
  try {
    return await fetch(url, { ...options, signal: controller.signal, cache: "no-store" });
  } catch (err) {
    if (controller.signal.aborted) {
      throw new Error(
        controller.signal.reason === "cancelled"
          ? "Request cancelled."
          : "The request timed out. The screening engine may be starting; please retry.",
        { cause: err }
      );
    }
    throw new Error("Could not reach the DocShield service. Check your connection and retry.", { cause: err });
  } finally {
    clearTimeout(timer);
    if (external) external.removeEventListener("abort", onAbort);
  }
}

async function errorFrom(res) {
  let detail = null;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch (_) {
    // Non-JSON error body: fall back to a status-based message.
  }
  return new Error(sanitizeErrorMessage(res.status, detail));
}

/**
 * Real readiness of the whole stack (Worker + D1 + container models).
 * Resolves to { state: "ready" | "starting" | "unavailable", body }.
 */
export async function checkReadiness(signal) {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/api/ready`, { signal }, READY_TIMEOUT_MS);
    const body = await res.json().catch(() => null);
    if (res.ok && body?.status === "ready") return { state: "ready", body };
    if (res.status === 503 && body) return { state: "starting", body };
    return { state: "unavailable", body };
  } catch (err) {
    if (err.message === "Request cancelled.") throw err;
    return { state: "unavailable", body: null };
  }
}

export async function analyzeDocument(docFile, personFile = null, docTypeHint = "auto", signal) {
  if (!docFile) throw new Error("Please select an identity document image to screen.");
  if (docFile.size === 0) throw new Error("The selected document file is empty.");
  if (docFile.size > 10 * 1024 * 1024) throw new Error("The document image exceeds 10 MB.");
  if (personFile && personFile.size > 10 * 1024 * 1024) throw new Error("The person photo exceeds 10 MB.");

  const formData = new FormData();
  formData.append("document", docFile);
  if (personFile) formData.append("person_image", personFile);
  if (docTypeHint && docTypeHint !== "auto") formData.append("doc_type_hint", docTypeHint);

  const res = await fetchWithTimeout(`${API_BASE}/api/analyze-document`, { method: "POST", body: formData, signal }, ANALYZE_TIMEOUT_MS);
  if (!res.ok) throw await errorFrom(res);
  const data = await res.json();
  currentSessionToken = data?.session_token || null;
  return data;
}

export async function getCase(caseId, sessionToken = null) {
  const token = sessionToken || currentSessionToken;
  const headers = { ...authHeaders() };
  if (token) headers["X-Session-Token"] = token;
  const res = await fetchWithTimeout(`${API_BASE}/api/case/${encodeURIComponent(caseId)}`, { headers });
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

export async function getReviewerProfile() {
  const res = await fetchWithTimeout(`${API_BASE}/api/officer/me`, { headers: authHeaders() });
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

export async function listCases() {
  const res = await fetchWithTimeout(`${API_BASE}/api/cases`, { headers: authHeaders() });
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

export async function submitOfficerReview(caseId, reviewData) {
  const res = await fetchWithTimeout(`${API_BASE}/api/case/${encodeURIComponent(caseId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(reviewData),
  });
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

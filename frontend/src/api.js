const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
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
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Server error: ${res.statusText}`);
  }

  return res.json();
}

export async function getCase(caseId) {
  const res = await fetch(`${API_BASE}/api/case/${caseId}`);
  if (!res.ok) throw new Error("Case not found");
  return res.json();
}

export async function listCases() {
  const res = await fetch(`${API_BASE}/api/cases`);
  if (!res.ok) throw new Error("Failed to fetch cases");
  return res.json();
}

export async function submitOfficerReview(caseId, reviewData) {
  const res = await fetch(`${API_BASE}/api/case/${caseId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(reviewData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to submit review: ${res.statusText}`);
  }
  return res.json();
}

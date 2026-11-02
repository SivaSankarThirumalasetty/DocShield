// Token handling. Raw tokens are never stored; D1 holds SHA-256 hashes only.

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function randomToken(bytes = 32) {
  const buf = new Uint8Array(bytes);
  crypto.getRandomValues(buf);
  return btoa(String.fromCharCode(...buf)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// Constant-time comparison of two equal-length hex digests.
export function timingSafeEqualHex(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function bearerToken(request) {
  const header = request.headers.get("Authorization") || "";
  const match = /^Bearer\s+([A-Za-z0-9_\-]{20,200})$/.exec(header.trim());
  return match ? match[1] : null;
}

/**
 * Resolves the officer behind a bearer token, or null. Checks expiry and
 * revocation on every call; nothing about the officer is trusted from the client.
 */
export async function authenticateOfficer(request, db, now = new Date()) {
  const token = bearerToken(request);
  if (!token) return null;
  const hash = await sha256Hex(token);
  const row = await db
    .prepare(
      `SELECT officer_id, tenant_id, display_name, role
         FROM officers
        WHERE token_hash = ?1 AND revoked_at IS NULL AND expires_at > ?2`
    )
    .bind(hash, now.toISOString())
    .first();
  return row || null;
}

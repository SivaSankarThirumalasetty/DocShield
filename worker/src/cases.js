// D1-backed case store. Every read is scoped by tenant and checked against
// either the submitter's session token hash or an authenticated officer.

import { redactResultForStorage } from "./redact.js";
import { sha256Hex, timingSafeEqualHex } from "./auth.js";

export const PUBLIC_TENANT = "public-demo";

export const REVIEW_DECISIONS = new Set([
  "CONCUR_NO_FURTHER_ACTION",
  "REFER_FOR_PHYSICAL_INSPECTION",
  "DOCUMENT_UNVERIFIABLE",
  "ESCALATE_TO_SUPERVISOR",
]);

const CASE_ID_PATTERN = /^DS-\d{8}-[0-9A-F]{8,16}$/;

export function isValidCaseId(caseId) {
  return typeof caseId === "string" && CASE_ID_PATTERN.test(caseId);
}

export async function audit(db, { tenantId, caseId = null, actor, action, detail = null }) {
  await db
    .prepare("INSERT INTO audit_log (ts, tenant_id, case_id, actor, action, detail) VALUES (?1, ?2, ?3, ?4, ?5, ?6)")
    .bind(new Date().toISOString(), tenantId, caseId, actor, action, detail)
    .run();
}

/** Stores a redacted record; returns the raw session token (shown to the submitter once). */
export async function storeCase(db, result, { sessionToken, retentionHours, tenantId = PUBLIC_TENANT, now = new Date() }) {
  if (!isValidCaseId(result.case_id)) throw new Error("invalid case id from backend");
  const redacted = redactResultForStorage(result);
  const expires = new Date(now.getTime() + retentionHours * 3600 * 1000);
  const risk = result.risk_assessment || {};
  const tokenHash = await sha256Hex(sessionToken);
  await db.batch([
    db
      .prepare(
        `INSERT INTO cases (case_id, tenant_id, created_at, expires_at, session_token_hash, document_type,
                            document_number_masked, risk_score, risk_level, verdict, review_json, result_json)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, NULL, ?11)`
      )
      .bind(
        result.case_id,
        tenantId,
        now.toISOString(),
        expires.toISOString(),
        tokenHash,
        redacted.document_info?.document_type || "UNKNOWN",
        redacted.document_info?.document_number ?? null,
        Math.max(0, Math.min(100, Number(risk.score) || 0)),
        String(risk.level || "MEDIUM"),
        String(risk.verdict || "INCOMPLETE_SCREENING"),
        JSON.stringify(redacted)
      ),
    db
      .prepare("INSERT INTO audit_log (ts, tenant_id, case_id, actor, action, detail) VALUES (?1, ?2, ?3, ?4, ?5, ?6)")
      .bind(now.toISOString(), tenantId, result.case_id, "SYSTEM", "CASE_CREATED", `risk=${risk.score} verdict=${risk.verdict}`),
  ]);
  return { expiresAt: expires.toISOString() };
}

function rowToCase(row) {
  const data = JSON.parse(row.result_json);
  data.officer_review = row.review_json ? JSON.parse(row.review_json) : null;
  data.persistence = { status: "STORED", backend: "cloudflare-d1", redacted: true, expires_at: row.expires_at };
  return data;
}

/**
 * Returns the case if the caller is the submitter (matching session token) or an
 * officer of the same tenant. Returns null otherwise, so callers can respond 404
 * without revealing whether the case exists.
 */
export async function getAuthorizedCase(db, caseId, { sessionToken = null, officer = null, now = new Date() }) {
  if (!isValidCaseId(caseId)) return null;
  const row = await db
    .prepare("SELECT * FROM cases WHERE case_id = ?1 AND expires_at > ?2")
    .bind(caseId, now.toISOString())
    .first();
  if (!row) return null;
  if (officer && officer.tenant_id === row.tenant_id) return rowToCase(row);
  if (sessionToken && typeof sessionToken === "string" && sessionToken.length <= 200) {
    const hash = await sha256Hex(sessionToken);
    if (timingSafeEqualHex(hash, row.session_token_hash)) return rowToCase(row);
  }
  return null;
}

export async function listCases(db, officer, { limit = 20, offset = 0, now = new Date() } = {}) {
  const { results } = await db
    .prepare(
      `SELECT case_id, created_at, document_type, document_number_masked, risk_score, risk_level, verdict, review_json
         FROM cases WHERE tenant_id = ?1 AND expires_at > ?2
        ORDER BY created_at DESC LIMIT ?3 OFFSET ?4`
    )
    .bind(officer.tenant_id, now.toISOString(), limit, offset)
    .all();
  return results.map((r) => ({
    case_id: r.case_id,
    timestamp: r.created_at,
    document_type: r.document_type,
    document_number: r.document_number_masked,
    risk_score: r.risk_score,
    risk_level: r.risk_level,
    verdict: r.verdict,
    officer_decision: r.review_json ? JSON.parse(r.review_json).decision : null,
  }));
}

export function validateReview(body) {
  if (!body || typeof body !== "object") return "Request body must be a JSON object.";
  if (!REVIEW_DECISIONS.has(body.decision)) return "decision must be one of: " + [...REVIEW_DECISIONS].join(", ");
  if (body.notes != null && (typeof body.notes !== "string" || body.notes.length > 2000)) return "notes must be a string of at most 2000 characters.";
  if (body.override_ai_verdict != null && typeof body.override_ai_verdict !== "boolean") return "override_ai_verdict must be a boolean.";
  return null;
}

export async function recordReview(db, caseId, officer, body, now = new Date()) {
  // Identity comes from the authenticated officer record, never from the request body.
  const review = {
    reviewed: true,
    officer_id: officer.officer_id,
    officer_name: officer.display_name,
    decision: body.decision,
    override_ai_verdict: Boolean(body.override_ai_verdict),
    notes: body.notes || null,
    timestamp: now.toISOString(),
  };
  const res = await db
    .prepare("UPDATE cases SET review_json = ?1 WHERE case_id = ?2 AND tenant_id = ?3 AND expires_at > ?4")
    .bind(JSON.stringify(review), caseId, officer.tenant_id, now.toISOString())
    .run();
  if (!res.meta || res.meta.changes !== 1) return null;
  await audit(db, {
    tenantId: officer.tenant_id,
    caseId,
    actor: officer.officer_id,
    action: "REVIEW_RECORDED",
    detail: `decision=${body.decision} override=${review.override_ai_verdict}`,
  });
  return getAuthorizedCase(db, caseId, { officer, now });
}

export async function purgeExpired(db, now = new Date()) {
  const iso = now.toISOString();
  const cases = await db.prepare("DELETE FROM cases WHERE expires_at <= ?1").bind(iso).run();
  // Audit entries are kept for 90 days.
  const auditCutoff = new Date(now.getTime() - 90 * 24 * 3600 * 1000).toISOString();
  await db.prepare("DELETE FROM audit_log WHERE ts < ?1").bind(auditCutoff).run();
  return cases.meta?.changes ?? 0;
}

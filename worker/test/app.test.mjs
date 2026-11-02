import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { handleRequest } from "../src/app.js";
import { sha256Hex } from "../src/auth.js";
import { maskDocumentNumber, redactResultForStorage } from "../src/redact.js";
import { purgeExpired } from "../src/cases.js";
import { createD1 } from "./d1-shim.mjs";
import { originBackendFetch } from "../src/index.js";

const b64url = (obj) => Buffer.from(JSON.stringify(obj)).toString("base64url");
// The backend sends the full result as the body and a redacted record in a header.
// Tests send an UNREDACTED record to prove the Worker re-redacts defensively.
const analyzeResponse = (result = backendResult()) =>
  Response.json(result, { headers: { "X-DocShield-Case-Record": b64url(result) } });

const MIGRATIONS = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "migrations");
const ORIGIN = "https://docshield.example.workers.dev";

function backendResult(overrides = {}) {
  return {
    case_id: "DS-20261102-ABCDEF123456",
    timestamp: "2026-11-02T00:00:00Z",
    processing_time_ms: 10,
    document_info: {
      document_type: "AADHAAR",
      document_number: "XXXX-XXXX-6125",
      name: "Aarav Sharma",
      dob: "14/08/1994",
      raw_text_preview: "GOVERNMENT OF INDIA Aarav",
      mrz_lines: [],
    },
    validation: { overall_valid: true, checks: [] },
    watchlist: { status: "CLEARED", matched_name: "x" },
    tampering: { ela_score: 10, ela_image_base64: "data:image/jpeg;base64,ELA" },
    face_verification: { match_verdict: "NOT_APPLICABLE", document_face_crop_base64: "data:FACE" },
    risk_assessment: { score: 20, level: "MEDIUM", verdict: "INCOMPLETE_SCREENING", reasons: ["r"] },
    pipeline: [{ stage: "ocr", status: "COMPLETED" }],
    document_preview_base64: "data:image/jpeg;base64,DOC",
    person_preview_base64: null,
    session_token: null,
    persistence: { status: "NOT_STORED", backend: "none" },
    ...overrides,
  };
}

let env, calls, logs, backendImpl;

function makeAssets() {
  const files = {
    "/index.html": ["<!doctype html><div id=root></div>", "text/html; charset=utf-8"],
    "/assets/app-123.js": ["console.log(1)", "application/javascript"],
  };
  return {
    async fetch(req) {
      const path = new URL(req.url).pathname;
      const key = path === "/" ? "/index.html" : path;
      const f = files[key];
      return f ? new Response(f[0], { status: 200, headers: { "Content-Type": f[1] } }) : new Response("nf", { status: 404 });
    },
  };
}

const deps = {
  backendFetch: async (req) => {
    calls.push(req);
    return backendImpl(req);
  },
  log: (event, fields) => logs.push({ event, ...fields }),
};

beforeEach(() => {
  calls = [];
  logs = [];
  backendImpl = async (req) => {
    const path = new URL(req.url).pathname;
    if (path === "/ready") return Response.json({ status: "ready", checks: { ocr_tesseract: true }, required: ["ocr_tesseract"] });
    if (path === "/api/health") return Response.json({ status: "healthy", modules: {} });
    if (path === "/api/analyze-document") return analyzeResponse();
    return Response.json({ detail: "nope" }, { status: 404 });
  };
  env = { DB: createD1(MIGRATIONS), ASSETS: makeAssets(), CASE_RETENTION_HOURS: "24", APP_VERSION: "test", GIT_COMMIT: "abc" };
});

function multipart(bytes = 1000, extraHeaders = {}) {
  const body = new Uint8Array(bytes);
  return new Request(`${ORIGIN}/api/analyze-document`, {
    method: "POST",
    headers: { "Content-Type": "multipart/form-data; boundary=x", "Content-Length": String(bytes), "CF-Connecting-IP": "203.0.113.9", ...extraHeaders },
    body,
  });
}

async function addOfficer(tenant = "public-demo", { expires = "2999-01-01T00:00:00Z", revoked = null, id = "OFF-1" } = {}) {
  const token = `tok_${id}_` + "a".repeat(40);
  await env.DB.prepare(
    "INSERT INTO officers (officer_id, tenant_id, display_name, role, token_hash, created_at, expires_at, revoked_at) VALUES (?1, ?2, ?3, 'reviewer', ?4, ?5, ?6, ?7)"
  )
    .bind(id, tenant, `Reviewer ${id}`, await sha256Hex(token), new Date().toISOString(), expires, revoked)
    .run();
  return token;
}

const get = (path, headers = {}) => handleRequest(new Request(`${ORIGIN}${path}`, { headers }), env, deps);

// ---------------------------------------------------------------- routing

test("API paths never fall through to the SPA shell", async () => {
  for (const path of ["/api/does-not-exist", "/api", "/api/debug"]) {
    const res = await get(path);
    assert.equal(res.status, 404);
    assert.match(res.headers.get("Content-Type"), /application\/json/);
  }
});

test("missing static asset is a real 404, navigation falls back to index.html", async () => {
  const missing = await get("/assets/missing.js");
  assert.equal(missing.status, 404);
  assert.match(missing.headers.get("Content-Type"), /text\/plain/);

  const nav = await get("/screening");
  assert.equal(nav.status, 200);
  assert.match(nav.headers.get("Content-Type"), /text\/html/);
  assert.match(nav.headers.get("Content-Security-Policy"), /default-src 'self'/);

  const js = await get("/assets/app-123.js");
  assert.equal(js.status, 200);
  assert.match(js.headers.get("Cache-Control"), /immutable/);
});

test("ready combines container readiness and D1; 503 when backend not ready", async () => {
  let res = await get("/api/ready");
  assert.equal(res.status, 200);
  let body = await res.json();
  assert.equal(body.status, "ready");
  assert.equal(body.edge.d1, true);

  backendImpl = async () => Response.json({ status: "not_ready", checks: { ocr_easyocr: false } }, { status: 503 });
  res = await get("/ready");
  assert.equal(res.status, 503);
  body = await res.json();
  assert.equal(body.status, "not_ready");
  assert.equal(body.backend.checks.ocr_easyocr, false);
});

test("health returns 503 JSON when the container is unreachable", async () => {
  backendImpl = async () => {
    throw new Error("container not running");
  };
  const res = await get("/api/health");
  assert.equal(res.status, 503);
  assert.equal((await res.json()).status, "unreachable");
});

// ---------------------------------------------------------------- analyze + persistence

test("analyze stores a redacted record in D1 and returns a session token", async () => {
  const res = await handleRequest(multipart(), env, deps);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Cache-Control"), "no-store");
  const body = await res.json();
  const token = res.headers.get("X-DocShield-Session-Token");
  assert.ok(token && token.length >= 40);
  assert.equal(JSON.parse(res.headers.get("X-DocShield-Persistence")).status, "STORED");
  assert.equal(res.headers.get("X-DocShield-Case-Record"), null, "internal header must not reach the browser");
  // The submitter still receives the full computed result once, unmodified.
  assert.equal(body.document_info.name, "Aarav Sharma");

  const row = await env.DB.prepare("SELECT * FROM cases WHERE case_id = ?1").bind(body.case_id).first();
  assert.ok(row);
  assert.notEqual(row.session_token_hash, token);
  for (const secret of ["Aarav", "14/08/1994", "data:image", "data:FACE", "GOVERNMENT OF INDIA"]) {
    assert.ok(!row.result_json.includes(secret), `stored record leaked ${secret}`);
  }
  assert.equal(calls[0].headers.get("CF-Connecting-IP"), "203.0.113.9");
});

test("D1 failure is reported honestly, without a session token", async () => {
  env.DB.batch = async () => {
    throw new Error("D1 down");
  };
  const res = await handleRequest(multipart(), env, deps);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("X-DocShield-Session-Token"), null);
  assert.equal(JSON.parse(res.headers.get("X-DocShield-Persistence")).status, "FAILED");
  assert.equal((await res.json()).case_id, "DS-20261102-ABCDEF123456");
});

test("missing case-record header means not stored, never a fake token", async () => {
  backendImpl = async () => Response.json(backendResult());
  const res = await handleRequest(multipart(), env, deps);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("X-DocShield-Session-Token"), null);
  assert.equal(JSON.parse(res.headers.get("X-DocShield-Persistence")).status, "FAILED");
});

test("origin mode: refuses without config, sends the edge secret", async () => {
  await assert.rejects(originBackendFetch(new Request("https://x/api/ready"), {}), /not configured/);
  await assert.rejects(originBackendFetch(new Request("https://x/api/ready"), { BACKEND_URL: "http://plain.example", EDGE_SHARED_SECRET: "s" }), /not configured/);
  const realFetch = globalThis.fetch;
  let seen;
  globalThis.fetch = async (url, init) => {
    seen = { url, auth: init.headers.get("X-DocShield-Edge-Auth") };
    return new Response("{}");
  };
  try {
    await originBackendFetch(new Request("https://edge/api/ready?x=1"), { BACKEND_URL: "https://api.example.com/", EDGE_SHARED_SECRET: "edge-secret" });
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.deepEqual(seen, { url: "https://api.example.com/api/ready?x=1", auth: "edge-secret" });
});

test("upload limits enforced at the edge before reaching the container", async () => {
  let res = await handleRequest(multipart(21 * 1024 * 1024), env, deps);
  assert.equal(res.status, 413);
  res = await handleRequest(
    new Request(`${ORIGIN}/api/analyze-document`, { method: "POST", headers: { "Content-Type": "application/json", "Content-Length": "2" }, body: "{}" }),
    env,
    deps
  );
  assert.equal(res.status, 415);
  res = await handleRequest(new Request(`${ORIGIN}/api/analyze-document`), env, deps);
  assert.equal(res.status, 405);
  assert.equal(calls.length, 0);
});

test("rate limiter blocks before the container is called", async () => {
  env.ANALYZE_LIMITER = { limit: async () => ({ success: false }) };
  const res = await handleRequest(multipart(), env, deps);
  assert.equal(res.status, 429);
  assert.equal(calls.length, 0);
});

test("backend errors are relayed as sanitised JSON only", async () => {
  backendImpl = async () =>
    new Response(JSON.stringify({ detail: "Invalid file format for d.png.", trace: "Traceback /app/backend" }), {
      status: 400,
      headers: { "Content-Type": "application/json", Server: "uvicorn" },
    });
  let res = await handleRequest(multipart(), env, deps);
  assert.equal(res.status, 400);
  assert.deepEqual(await res.json(), { detail: "Invalid file format for d.png." });

  backendImpl = async () => new Response("<html>Traceback (most recent call last)</html>", { status: 500 });
  res = await handleRequest(multipart(), env, deps);
  assert.equal(res.status, 502);
  assert.ok(!(await res.text()).includes("Traceback"));
});

// ---------------------------------------------------------------- authorization

async function createCase() {
  const res = await handleRequest(multipart(), env, deps);
  const body = await res.json();
  return { case_id: body.case_id, session_token: res.headers.get("X-DocShield-Session-Token") };
}

test("case retrieval: submitter token works, wrong/absent token is 404", async () => {
  const c = await createCase();
  let res = await get(`/api/case/${c.case_id}`, { "X-Session-Token": c.session_token });
  assert.equal(res.status, 200);
  const stored = await res.json();
  assert.equal(stored.document_info.name, null);
  assert.equal(stored.document_preview_base64, null);
  assert.equal(stored.persistence.backend, "cloudflare-d1");

  assert.equal((await get(`/api/case/${c.case_id}`)).status, 404);
  assert.equal((await get(`/api/case/${c.case_id}`, { "X-Session-Token": "x".repeat(43) })).status, 404);
  assert.equal((await get(`/api/case/DS-20261102-000000000000`, { "X-Session-Token": c.session_token })).status, 404);
  assert.equal((await get(`/api/case/..%2F..%2Fetc`)).status, 404);
});

test("officer endpoints require a valid, unexpired, unrevoked token", async () => {
  assert.equal((await get("/api/cases")).status, 401);
  assert.equal((await get("/api/cases", { Authorization: "Bearer " + "z".repeat(43) })).status, 401);

  const expired = await addOfficer("public-demo", { expires: "2000-01-01T00:00:00Z", id: "OLD" });
  assert.equal((await get("/api/cases", { Authorization: `Bearer ${expired}` })).status, 401);
  const revoked = await addOfficer("public-demo", { revoked: "2026-01-01T00:00:00Z", id: "REV" });
  assert.equal((await get("/api/cases", { Authorization: `Bearer ${revoked}` })).status, 401);

  const token = await addOfficer();
  const res = await get("/api/cases", { Authorization: `Bearer ${token}` });
  assert.equal(res.status, 200);
  assert.ok(Array.isArray(await res.json()));
  const me = await (await get("/api/officer/me", { Authorization: `Bearer ${token}` })).json();
  assert.equal(me.officer_id, "OFF-1");
});

test("failed officer auth is rate limited", async () => {
  env.AUTH_LIMITER = { limit: async () => ({ success: false }) };
  const res = await get("/api/cases", { Authorization: "Bearer " + "z".repeat(43) });
  assert.equal(res.status, 429);
});

test("tenant isolation: officers cannot read or review another tenant's cases", async () => {
  const c = await createCase(); // stored under public-demo
  const other = await addOfficer("tenant-b", { id: "B-1" });
  assert.equal((await get(`/api/case/${c.case_id}`, { Authorization: `Bearer ${other}` })).status, 404);
  const listed = await (await get("/api/cases", { Authorization: `Bearer ${other}` })).json();
  assert.equal(listed.length, 0);
  const review = await handleRequest(
    new Request(`${ORIGIN}/api/case/${c.case_id}/review`, {
      method: "POST",
      headers: { Authorization: `Bearer ${other}`, "Content-Type": "application/json" },
      body: JSON.stringify({ decision: "CONCUR_NO_FURTHER_ACTION" }),
    }),
    env,
    deps
  );
  assert.equal(review.status, 404);
});

test("review records identity from the token, validates decisions, and audits", async () => {
  const c = await createCase();
  const token = await addOfficer();
  const post = (body) =>
    handleRequest(
      new Request(`${ORIGIN}/api/case/${c.case_id}/review`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: typeof body === "string" ? body : JSON.stringify(body),
      }),
      env,
      deps
    );
  assert.equal((await post({ decision: "DETAINED" })).status, 422);
  assert.equal((await post("{bad json")).status, 422);

  const ok = await post({ decision: "REFER_FOR_PHYSICAL_INSPECTION", officer_id: "SPOOFED", officer_name: "Spoof", notes: "n" });
  assert.equal(ok.status, 200);
  const body = await ok.json();
  assert.equal(body.officer_review.officer_id, "OFF-1");
  assert.equal(body.officer_review.officer_name, "Reviewer OFF-1");
  const auditRow = await env.DB.prepare("SELECT * FROM audit_log WHERE action = 'REVIEW_RECORDED'").first();
  assert.equal(auditRow.actor, "OFF-1");
});

// ---------------------------------------------------------------- retention + redaction

test("expired cases are invisible and purged", async () => {
  const c = await createCase();
  await env.DB.prepare("UPDATE cases SET expires_at = '2000-01-01T00:00:00Z'").run();
  assert.equal((await get(`/api/case/${c.case_id}`, { "X-Session-Token": c.session_token })).status, 404);
  assert.equal(await purgeExpired(env.DB), 1);
});

test("redaction mirrors the Python implementation", () => {
  assert.equal(maskDocumentNumber("367598346125", "AADHAAR"), "XXXX-XXXX-6125");
  assert.equal(maskDocumentNumber("Z2098451", "PASSPORT"), "****8451");
  assert.equal(maskDocumentNumber("ABCDE1234F", "PAN"), "******234F");
  const red = redactResultForStorage(backendResult({ risk_assessment: { reasons: ["n 3675 9834 6125"] } }));
  assert.equal(red.risk_assessment.reasons[0], "n XXXX-XXXX-6125");
  assert.equal(red.redacted, true);
});

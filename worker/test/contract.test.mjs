// Contract test: the real Worker router talking to a real FastAPI backend.
// Runs only when BACKEND_URL is set (CI starts uvicorn with PERSISTENCE_MODE=none):
//   BACKEND_URL=http://127.0.0.1:8000 node --test worker/test/contract.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { handleRequest } from "../src/app.js";
import { createD1 } from "./d1-shim.mjs";

const BACKEND_URL = process.env.BACKEND_URL;
const EDGE_SECRET = process.env.EDGE_SHARED_SECRET || "";
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const ORIGIN = "https://docshield.test";

const env = {
  DB: createD1(join(ROOT, "migrations")),
  ASSETS: { fetch: async () => new Response("nf", { status: 404 }) },
  CASE_RETENTION_HOURS: "24",
};
const deps = {
  backendFetch: (req) => {
    const u = new URL(req.url);
    const headers = new Headers(req.headers);
    if (EDGE_SECRET) headers.set("X-DocShield-Edge-Auth", EDGE_SECRET);
    return fetch(BACKEND_URL + u.pathname + u.search, { method: req.method, headers, body: req.body, duplex: "half" });
  },
  log: () => {},
};

async function upload(file, hint) {
  const form = new FormData();
  form.append("document", new Blob([readFileSync(join(ROOT, "sample_data", file))], { type: "image/png" }), file);
  if (hint) form.append("doc_type_hint", hint);
  const encoded = new Request(ORIGIN, { method: "POST", body: form });
  const body = await encoded.arrayBuffer();
  return handleRequest(
    new Request(`${ORIGIN}/api/analyze-document`, {
      method: "POST",
      headers: { "Content-Type": encoded.headers.get("Content-Type"), "Content-Length": String(body.byteLength), "CF-Connecting-IP": "198.51.100.7" },
      body,
    }),
    env,
    deps
  );
}

test("worker <-> backend contract", { skip: !BACKEND_URL && "BACKEND_URL not set" }, async (t) => {
  await t.test("health and readiness are real JSON from the backend", async () => {
    const health = await handleRequest(new Request(`${ORIGIN}/api/health`), env, deps);
    assert.equal(health.status, 200);
    const h = await health.json();
    assert.ok("demo_registry" in h.modules);

    const ready = await handleRequest(new Request(`${ORIGIN}/api/ready`), env, deps);
    const r = await ready.json();
    assert.ok([200, 503].includes(ready.status));
    assert.equal(r.edge.d1, true);
    assert.ok(r.backend.checks && "ocr_tesseract" in r.backend.checks);
  });

  await t.test("real screening flows through, is persisted redacted, and is retrievable", async () => {
    const res = await upload("aadhaar_invalid_checksum.png", "AADHAAR");
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.match(body.case_id, /^DS-\d{8}-[0-9A-F]{12}$/);
    assert.ok(Array.isArray(body.pipeline) && body.pipeline.some((s) => s.stage === "ocr"));
    assert.ok(["NO_ADVERSE_INDICATORS", "INCOMPLETE_SCREENING", "MANUAL_REVIEW_RECOMMENDED", "ESCALATE_FOR_EXPERT_REVIEW"].includes(body.risk_assessment.verdict));
    assert.equal(JSON.parse(res.headers.get("X-DocShield-Persistence")).status, "STORED");
    const token = res.headers.get("X-DocShield-Session-Token");

    const got = await handleRequest(
      new Request(`${ORIGIN}/api/case/${body.case_id}`, { headers: { "X-Session-Token": token } }),
      env,
      deps
    );
    assert.equal(got.status, 200);
    const stored = await got.json();
    assert.equal(stored.document_preview_base64, null);
    assert.equal(stored.document_info.raw_text_preview, "");
  });

  await t.test("backend rejects direct calls without the edge secret", { skip: !EDGE_SECRET && "EDGE_SHARED_SECRET not set" }, async () => {
    const direct = await fetch(BACKEND_URL + "/api/ready");
    assert.equal(direct.status, 401);
    const live = await fetch(BACKEND_URL + "/health");
    assert.equal(live.status, 200);
  });

  await t.test("malformed upload is rejected by the backend with a safe 400", async () => {
    const fake = new TextEncoder().encode("--b\r\nContent-Disposition: form-data; name=\"document\"; filename=\"x.png\"\r\nContent-Type: image/png\r\n\r\nnot an image\r\n--b--\r\n");
    const res = await handleRequest(
      new Request(`${ORIGIN}/api/analyze-document`, {
        method: "POST",
        headers: { "Content-Type": "multipart/form-data; boundary=b", "Content-Length": String(fake.byteLength) },
        body: fake,
      }),
      env,
      deps
    );
    assert.equal(res.status, 400);
    const j = await res.json();
    assert.deepEqual(Object.keys(j), ["detail"]);
  });
});

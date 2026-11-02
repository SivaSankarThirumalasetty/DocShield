// DocShield edge request handling: API routing, auth, rate limiting, D1 case
// persistence, and static asset serving. The Python container is reached only
// through `deps.backendFetch`, so this module runs under plain Node in tests.

import { json, errorJson, withApiHeaders, clientIp, requestIdFor, HTML_CSP } from "./http.js";
import { authenticateOfficer, randomToken } from "./auth.js";
import {
  storeCase,
  getAuthorizedCase,
  listCases,
  validateReview,
  recordReview,
  isValidCaseId,
} from "./cases.js";

const MB = 1024 * 1024;
// Two images of up to 10 MB each plus multipart framing.
const MAX_ANALYZE_BODY = 20 * MB + 64 * 1024;
const BACKEND_TIMEOUT_MS = 120_000;
const HEALTH_TIMEOUT_MS = 90_000;

const STATIC_EXTENSION = /\.(js|mjs|cjs|css|map|png|jpe?g|gif|webp|svg|ico|json|txt|xml|woff2?|ttf|eot|wasm)$/i;

async function withTimeout(promise, ms) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("timeout")), ms);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

async function rateLimited(limiter, key) {
  if (!limiter) return false; // Binding absent only in local tests; production config always defines it.
  const { success } = await limiter.limit({ key });
  return !success;
}

/** Only `detail` is ever relayed from a backend error, and only if it is a short string. */
async function relayBackendError(res, requestId) {
  let detail = "Screening request failed.";
  try {
    const body = await res.json();
    if (typeof body?.detail === "string" && body.detail.length < 300) detail = body.detail;
  } catch (_) {}
  if (res.status === 503) return errorJson(503, detail, { "X-Request-ID": requestId, "Retry-After": "15" });
  return errorJson(res.status >= 500 ? 502 : res.status, detail, { "X-Request-ID": requestId });
}

async function readBoundedBody(request, maxBytes) {
  const declared = request.headers.get("Content-Length");
  if (declared === null) return { error: errorJson(411, "Content-Length required.") };
  if (!/^\d+$/.test(declared)) return { error: errorJson(400, "Invalid Content-Length.") };
  if (Number(declared) > maxBytes) {
    return { error: errorJson(413, "Upload exceeds the 10 MB per-image limit.") };
  }
  const body = await request.arrayBuffer();
  if (body.byteLength > maxBytes) return { error: errorJson(413, "Upload exceeds the 10 MB per-image limit.") };
  return { body };
}

async function proxyMultipart(request, env, deps, path, requestId) {
  const ip = clientIp(request);
  if (await rateLimited(env.ANALYZE_LIMITER, ip)) {
    return { response: errorJson(429, "Too many screening requests. Please wait a minute and retry.", { "Retry-After": "60" }) };
  }
  const contentType = request.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().startsWith("multipart/form-data")) {
    return { response: errorJson(415, "Expected multipart/form-data.") };
  }
  const { body, error } = await readBoundedBody(request, MAX_ANALYZE_BODY);
  if (error) return { response: error };

  const upstream = new Request(`http://backend${path}`, {
    method: "POST",
    headers: {
      "Content-Type": contentType,
      "Content-Length": String(body.byteLength),
      "CF-Connecting-IP": ip,
      "X-Request-ID": requestId,
    },
    body,
  });
  try {
    return { upstream: await withTimeout(deps.backendFetch(upstream, env), BACKEND_TIMEOUT_MS) };
  } catch (err) {
    deps.log("backend_error", { requestId, path, error: String(err && err.message) });
    const status = err?.message === "timeout" ? 504 : 503;
    return { response: errorJson(status, "The screening engine is unavailable or starting. Please retry shortly.", { "Retry-After": "20" }) };
  }
}

async function handleAnalyze(request, env, deps, requestId) {
  const { response, upstream } = await proxyMultipart(request, env, deps, "/api/analyze-document", requestId);
  if (response) return response;
  if (upstream.status !== 200) return relayBackendError(upstream, requestId);

  const result = await upstream.json();
  const retentionHours = Math.max(1, Math.min(720, Number(env.CASE_RETENTION_HOURS) || 24));
  const sessionToken = randomToken();
  try {
    const { expiresAt } = await storeCase(env.DB, result, { sessionToken, retentionHours });
    result.session_token = sessionToken;
    result.persistence = { status: "STORED", backend: "cloudflare-d1", redacted: true, expires_at: expiresAt };
  } catch (err) {
    // The screening result is still returned, but no retrievable case exists.
    deps.log("persist_error", { requestId, error: String(err && err.message) });
    result.session_token = null;
    result.persistence = { status: "FAILED", backend: "cloudflare-d1" };
  }
  return json(result, 200, { "X-Request-ID": requestId });
}

async function d1Ok(env) {
  try {
    await env.DB.prepare("SELECT 1 AS ok").first();
    return true;
  } catch (_) {
    return false;
  }
}

async function handleReady(env, deps, requestId) {
  const [d1, backend] = await Promise.all([
    d1Ok(env),
    withTimeout(deps.backendFetch(new Request("http://backend/ready"), env), HEALTH_TIMEOUT_MS)
      .then(async (r) => ({ status: r.status, body: await r.json().catch(() => null) }))
      .catch((err) => ({ status: 0, error: err?.message === "timeout" ? "timeout" : "unreachable" })),
  ]);
  const backendReady = backend.status === 200 && backend.body?.status === "ready";
  const ready = d1 && backendReady;
  return json(
    {
      status: ready ? "ready" : "not_ready",
      edge: { worker: "ok", d1, version: env.APP_VERSION || "dev", commit: env.GIT_COMMIT || "unknown" },
      backend: backend.body
        ? { status: backend.body.status, checks: backend.body.checks, required: backend.body.required }
        : { status: backend.error || "unreachable" },
      timestamp: new Date().toISOString(),
    },
    ready ? 200 : 503,
    { "X-Request-ID": requestId }
  );
}

async function handleHealth(env, deps, requestId) {
  try {
    const res = await withTimeout(deps.backendFetch(new Request("http://backend/api/health"), env), HEALTH_TIMEOUT_MS);
    return withApiHeaders(res, requestId);
  } catch (err) {
    return json(
      { status: "unreachable", detail: "The screening engine did not respond.", timestamp: new Date().toISOString() },
      503,
      { "X-Request-ID": requestId }
    );
  }
}

async function requireOfficer(request, env) {
  const officer = await authenticateOfficer(request, env.DB);
  if (officer) return { officer };
  if (request.headers.has("Authorization") && (await rateLimited(env.AUTH_LIMITER, clientIp(request)))) {
    return { error: errorJson(429, "Too many failed authentication attempts.", { "Retry-After": "60" }) };
  }
  return { error: errorJson(401, "Reviewer authentication required.", { "WWW-Authenticate": "Bearer" }) };
}

async function handleApi(request, env, deps, url, requestId) {
  const { pathname } = url;
  const method = request.method;

  if (pathname === "/api/health" || pathname === "/health") {
    return method === "GET" ? handleHealth(env, deps, requestId) : errorJson(405, "Method not allowed.");
  }
  if (pathname === "/api/ready" || pathname === "/ready") {
    return method === "GET" ? handleReady(env, deps, requestId) : errorJson(405, "Method not allowed.");
  }
  if (pathname === "/api/analyze-document") {
    return method === "POST" ? handleAnalyze(request, env, deps, requestId) : errorJson(405, "Method not allowed.");
  }
  if (pathname === "/api/verify-face") {
    if (method !== "POST") return errorJson(405, "Method not allowed.");
    const { response, upstream } = await proxyMultipart(request, env, deps, "/api/verify-face", requestId);
    if (response) return response;
    return upstream.status === 200 ? withApiHeaders(upstream, requestId) : relayBackendError(upstream, requestId);
  }
  if (pathname === "/api/officer/me") {
    if (method !== "GET") return errorJson(405, "Method not allowed.");
    const { officer, error } = await requireOfficer(request, env);
    if (error) return error;
    return json({ officer_id: officer.officer_id, display_name: officer.display_name, tenant_id: officer.tenant_id, role: officer.role });
  }
  if (pathname === "/api/cases") {
    if (method !== "GET") return errorJson(405, "Method not allowed.");
    const { officer, error } = await requireOfficer(request, env);
    if (error) return error;
    const limit = Number(url.searchParams.get("limit") ?? 20);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100 || !Number.isInteger(offset) || offset < 0) {
      return errorJson(422, "limit must be 1-100 and offset >= 0.");
    }
    return json(await listCases(env.DB, officer, { limit, offset }));
  }

  const caseMatch = /^\/api\/case\/([^/]+)(\/review)?$/.exec(pathname);
  if (caseMatch) {
    const caseId = decodeURIComponent(caseMatch[1]);
    if (caseMatch[2]) {
      if (method !== "POST") return errorJson(405, "Method not allowed.");
      const { officer, error } = await requireOfficer(request, env);
      if (error) return error;
      let body;
      try {
        body = await request.json();
      } catch (_) {
        return errorJson(422, "Request body must be valid JSON.");
      }
      const problem = validateReview(body);
      if (problem) return errorJson(422, problem);
      const updated = isValidCaseId(caseId) ? await recordReview(env.DB, caseId, officer, body) : null;
      return updated ? json(updated) : errorJson(404, "Case not found or access denied.");
    }
    if (method !== "GET") return errorJson(405, "Method not allowed.");
    const officer = request.headers.has("Authorization") ? await authenticateOfficer(request, env.DB) : null;
    const found = await getAuthorizedCase(env.DB, caseId, {
      sessionToken: request.headers.get("X-Session-Token"),
      officer,
    });
    return found ? json(found) : errorJson(404, "Case not found or access denied.");
  }

  return errorJson(404, "Unknown API endpoint.");
}

function withHtmlHeaders(response, pathname) {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  headers.set("Permissions-Policy", "camera=(self), microphone=(), geolocation=()");
  const contentType = headers.get("Content-Type") || "";
  if (contentType.startsWith("text/html")) {
    headers.set("Content-Security-Policy", HTML_CSP);
    headers.set("Cache-Control", "no-cache");
  } else if (pathname.startsWith("/assets/")) {
    headers.set("Cache-Control", "public, max-age=31536000, immutable");
  }
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

async function handleStatic(request, env, url) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method Not Allowed", { status: 405, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
  const asset = await env.ASSETS.fetch(request);
  if (asset.status !== 404) return withHtmlHeaders(asset, url.pathname);

  // Missing files keep a real 404; only extensionless navigations fall back to the SPA shell.
  if (STATIC_EXTENSION.test(url.pathname) || url.pathname.startsWith("/assets/") || url.pathname.startsWith("/samples/")) {
    return new Response("Not Found", {
      status: 404,
      headers: { "Content-Type": "text/plain; charset=utf-8", "X-Content-Type-Options": "nosniff" },
    });
  }
  const index = await env.ASSETS.fetch(new Request(new URL("/", url), { method: "GET" }));
  return withHtmlHeaders(index, "/index.html");
}

export async function handleRequest(request, env, deps) {
  const url = new URL(request.url);
  const requestId = requestIdFor(request);
  const isApi = url.pathname === "/api" || url.pathname.startsWith("/api/") || url.pathname === "/health" || url.pathname === "/ready";
  if (!isApi) return handleStatic(request, env, url);

  const started = Date.now();
  let response;
  try {
    response = await handleApi(request, env, deps, url, requestId);
  } catch (err) {
    deps.log("unhandled_error", { requestId, path: url.pathname, error: String(err && err.message) });
    response = errorJson(500, "Internal error.");
  }
  deps.log("request", { requestId, method: request.method, path: url.pathname, status: response.status, ms: Date.now() - started });
  return response;
}

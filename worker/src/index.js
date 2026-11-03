// Cloudflare Worker entry point for DocShield — FREE mode (default).
//
//   Browser -> this Worker (static assets + /api/*) -> D1 (redacted cases, reviewer tokens, audit)
//                                                   -> BACKEND_URL (FastAPI on a free remote host)
//
// The backend is on the public internet, so every call carries EDGE_SHARED_SECRET
// (a Worker secret) and the backend rejects requests without it.

import { handleRequest } from "./app.js";
import { purgeExpired } from "./cases.js";

function log(event, fields) {
  console.log(JSON.stringify({ event, ...fields }));
}

export function originBackendFetch(request, env) {
  const base = (env.BACKEND_URL || "").replace(/\/+$/, "");
  if (!base.startsWith("https://") || !env.EDGE_SHARED_SECRET) {
    return Promise.reject(new Error("backend not configured"));
  }
  const url = new URL(request.url);
  const headers = new Headers(request.headers);
  headers.set("X-DocShield-Edge-Auth", env.EDGE_SHARED_SECRET);
  return fetch(base + url.pathname + url.search, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    redirect: "manual",
  });
}

const deps = { backendFetch: originBackendFetch, log };

export default {
  fetch(request, env) {
    return handleRequest(request, env, deps);
  },

  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(purgeExpired(env.DB).then((deleted) => log("retention_purge", { deleted })));
  },
};

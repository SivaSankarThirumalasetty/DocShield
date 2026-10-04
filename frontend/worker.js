/**
 * Cloudflare Worker & Container entrypoint for DocShield Production Frontend & API Gateway.
 * Mirrors repository root worker.js for deployments executed from frontend/.
 */

import { Container, getContainer } from "@cloudflare/containers";

const CONTAINER_SINGLETON_NAME = "docshield-api-singleton";

export class DocShieldBackendContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "15m";
  pingEndpoint = "localhost/health";
  enableInternet = true;

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      PORT: "8000",
      HOST: "0.0.0.0",
      DOCSHIELD_ENV: env?.DOCSHIELD_ENV || "production",
      DOCSHIELD_MODE: env?.DOCSHIELD_MODE || "PROTOTYPE",
      FRONTEND_ORIGIN:
        env?.FRONTEND_ORIGIN ||
        "https://docshield.sivasankar-t1606.workers.dev",
      ...(env?.DOCSHIELD_OFFICER_KEY
        ? { DOCSHIELD_OFFICER_KEY: env.DOCSHIELD_OFFICER_KEY }
        : {}),
    };
  }
}

const MIME_BY_EXTENSION = {
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".txt": "text/plain; charset=utf-8",
  ".wasm": "application/wasm",
};

const STATIC_ASSET_EXT_REGEX =
  /\.(js|mjs|cjs|jsx|ts|tsx|css|png|jpg|jpeg|gif|webp|svg|ico|json|wasm|map|woff|woff2|ttf|eot|txt|xml)$/i;

function getExplicitMimeType(pathname) {
  const lower = pathname.toLowerCase();
  const dotIdx = lower.lastIndexOf(".");
  if (dotIdx === -1) return null;
  const ext = lower.slice(dotIdx);
  return MIME_BY_EXTENSION[ext] || null;
}

function applyResponseHeaders(response, pathname) {
  const headers = new Headers(response.headers);

  const explicitMime = getExplicitMimeType(pathname);
  if (explicitMime) {
    headers.set("Content-Type", explicitMime);
  }

  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set(
    "Permissions-Policy",
    "camera=(self), microphone=(), geolocation=()"
  );

  if (pathname.startsWith("/assets/")) {
    headers.set("Cache-Control", "public, max-age=31536000, immutable");
  } else if (pathname === "/" || pathname.endsWith(".html")) {
    headers.set("Cache-Control", "public, max-age=0, must-revalidate");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function fetchAssetWithDistFallback(env, request, url, targetPath) {
  const primaryUrl = new URL(targetPath, url.origin);
  const primaryRes = await env.ASSETS.fetch(new Request(primaryUrl, request));
  if (primaryRes.status !== 404) {
    return primaryRes;
  }

  const normalized = targetPath === "/" ? "" : targetPath;
  for (const prefix of ["/dist", "/frontend/dist"]) {
    const fallbackUrl = new URL(`${prefix}${normalized || "/"}`, url.origin);
    const fallbackRes = await env.ASSETS.fetch(
      new Request(fallbackUrl, request)
    );
    if (fallbackRes.status !== 404) {
      return fallbackRes;
    }
  }

  return primaryRes;
}

function buildForwardedHeaders(request, env) {
  const proxyHeaders = new Headers(request.headers);
  proxyHeaders.delete("host");

  const clientIp =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For")?.split(",")[0]?.trim();
  if (clientIp) {
    proxyHeaders.set("CF-Connecting-IP", clientIp);
    proxyHeaders.set("X-Forwarded-For", clientIp);
  }
  proxyHeaders.set("X-Forwarded-Proto", "https");
  if (
    (env?.DOCSHIELD_MODE || "PROTOTYPE") === "PROTOTYPE" &&
    !proxyHeaders.has("X-Officer-Key")
  ) {
    proxyHeaders.set(
      "X-Officer-Key",
      env?.DOCSHIELD_OFFICER_KEY ||
        "docshield-officer-secret-key-change-in-production"
    );
  }
  return proxyHeaders;
}

function getAllowedOrigin(request, env) {
  const origin = request.headers.get("Origin");
  if (!origin) return null;
  const configuredOrigin = (
    env?.FRONTEND_ORIGIN || "https://docshield.sivasankar-t1606.workers.dev"
  )
    .trim()
    .replace(/\/+$/, "");
  const allowed = new Set([
    configuredOrigin,
    "https://docshield.sivasankar-t1606.workers.dev",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
  ]);
  return allowed.has(origin) ? origin : null;
}

function attachCorsHeaders(headers, allowedOrigin) {
  if (allowedOrigin) {
    headers.set("Access-Control-Allow-Origin", allowedOrigin);
    headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    headers.set(
      "Access-Control-Allow-Headers",
      "Content-Type, Accept, X-Officer-Key, X-Session-Token, Cache-Control"
    );
    headers.set("Access-Control-Max-Age", "600");
    headers.set("Vary", "Origin");
  }
}

async function routeToBackend(request, env, url) {
  const allowedOrigin = getAllowedOrigin(request, env);

  if (request.method === "OPTIONS") {
    const optHeaders = new Headers({
      "X-Content-Type-Options": "nosniff",
      "X-DocShield-Backend": "cloudflare-worker",
    });
    attachCorsHeaders(optHeaders, allowedOrigin);
    return new Response(null, { status: 200, headers: optHeaders });
  }

  const contentLength = Number(request.headers.get("Content-Length") || "0");
  if (contentLength > 10 * 1024 * 1024) {
    const errHeaders = new Headers({
      "Content-Type": "application/json; charset=utf-8",
      "X-Content-Type-Options": "nosniff",
      "X-DocShield-Backend": "cloudflare-worker",
    });
    attachCorsHeaders(errHeaders, allowedOrigin);
    return new Response(
      JSON.stringify({
        detail: "File size exceeds maximum allowed limit of 10MB.",
      }),
      { status: 413, headers: errHeaders }
    );
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const bodyBuffer = hasBody ? await request.arrayBuffer() : undefined;
  if (bodyBuffer && bodyBuffer.byteLength > 10 * 1024 * 1024) {
    const errHeaders = new Headers({
      "Content-Type": "application/json; charset=utf-8",
      "X-Content-Type-Options": "nosniff",
      "X-DocShield-Backend": "cloudflare-worker",
    });
    attachCorsHeaders(errHeaders, allowedOrigin);
    return new Response(
      JSON.stringify({
        detail: "File size exceeds maximum allowed limit of 10MB.",
      }),
      { status: 413, headers: errHeaders }
    );
  }

  const proxyHeaders = buildForwardedHeaders(request, env);
  if (bodyBuffer) {
    proxyHeaders.set("Content-Length", String(bodyBuffer.byteLength));
  }

  const backendOrigin = (env.BACKEND_ORIGIN || "").trim().replace(/\/+$/, "");

  if (env.DOCSHIELD_BACKEND && !backendOrigin) {
    try {
      const containerStub = getContainer(
        env.DOCSHIELD_BACKEND,
        CONTAINER_SINGLETON_NAME
      );
      const containerUrl = `http://localhost:8000${url.pathname}${url.search}`;
      const containerReq = new Request(containerUrl, {
        method: request.method,
        headers: proxyHeaders,
        body: bodyBuffer,
        redirect: "manual",
      });
      const containerRes = await containerStub.fetch(containerReq);
      if (containerRes.status < 502) {
        const responseHeaders = new Headers(containerRes.headers);
        responseHeaders.set("X-Content-Type-Options", "nosniff");
        responseHeaders.set("X-DocShield-Backend", "cloudflare-container");
        attachCorsHeaders(responseHeaders, allowedOrigin);
        return new Response(containerRes.body, {
          status: containerRes.status,
          statusText: containerRes.statusText,
          headers: responseHeaders,
        });
      }
    } catch (_) {}
  }

  if (backendOrigin) {
    const targetUrl = `${backendOrigin}${url.pathname}${url.search}`;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const upstream = await fetch(targetUrl, {
          method: request.method,
          headers: proxyHeaders,
          body: bodyBuffer,
          redirect: "manual",
        });

        if (
          (upstream.status === 502 ||
            upstream.status === 503 ||
            upstream.status === 504 ||
            upstream.status === 522 ||
            upstream.status === 530) &&
          attempt < 2
        ) {
          await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
          continue;
        }

        if (
          url.pathname === "/ready" &&
          (upstream.headers.get("content-type") || "").includes("text/html")
        ) {
          const healthRes = await fetch(`${backendOrigin}/api/health`, {
            method: "GET",
            headers: proxyHeaders,
          });
          const healthJson = await healthRes.json();
          const readyHeaders = new Headers({
            "Content-Type": "application/json; charset=utf-8",
            "X-Content-Type-Options": "nosniff",
            "X-DocShield-Backend": "cloudflare-worker",
          });
          attachCorsHeaders(readyHeaders, allowedOrigin);
          return new Response(
            JSON.stringify({
              status: healthJson.status === "healthy" ? "ready" : "degraded",
              mode: env.DOCSHIELD_MODE || "PROTOTYPE",
              checks: healthJson.modules || {},
              timestamp: healthJson.timestamp || new Date().toISOString(),
            }),
            { status: healthRes.status, headers: readyHeaders }
          );
        }

        const responseHeaders = new Headers(upstream.headers);
        responseHeaders.set("X-Content-Type-Options", "nosniff");
        responseHeaders.set("X-DocShield-Backend", "cloudflare-worker");
        attachCorsHeaders(responseHeaders, allowedOrigin);
        return new Response(upstream.body, {
          status: upstream.status,
          statusText: upstream.statusText,
          headers: responseHeaders,
        });
      } catch (_) {
        if (attempt < 2) {
          await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
          continue;
        }
      }
    }
  }

  const err502Headers = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  attachCorsHeaders(err502Headers, allowedOrigin);
  return new Response(
    JSON.stringify({
      detail:
        "Screening backend is temporarily unreachable. Please retry in a few seconds.",
    }),
    {
      status: 502,
      headers: err502Headers,
    }
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;

    if (
      pathname.startsWith("/api/") ||
      pathname === "/health" ||
      pathname === "/ready"
    ) {
      return routeToBackend(request, env, url);
    }

    if (pathname.startsWith("/src/")) {
      return new Response("Not Found", {
        status: 404,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    if (env.ASSETS) {
      const assetResponse = await fetchAssetWithDistFallback(
        env,
        request,
        url,
        pathname
      );
      if (assetResponse.status !== 404) {
        const effectivePath = pathname === "/" ? "/index.html" : pathname;
        return applyResponseHeaders(assetResponse, effectivePath);
      }

      const isStaticAssetRequest =
        pathname.startsWith("/assets/") ||
        pathname.startsWith("/samples/") ||
        STATIC_ASSET_EXT_REGEX.test(pathname);

      if (
        isStaticAssetRequest ||
        (request.method !== "GET" && request.method !== "HEAD")
      ) {
        return new Response("Asset Not Found", {
          status: 404,
          headers: {
            "Content-Type": "text/plain; charset=utf-8",
            "X-Content-Type-Options": "nosniff",
          },
        });
      }

      const indexResponse = await fetchAssetWithDistFallback(
        env,
        request,
        url,
        "/"
      );
      return applyResponseHeaders(indexResponse, "/index.html");
    }

    return new Response("Static assets binding (ASSETS) is not configured.", {
      status: 500,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  },
};

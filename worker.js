/**
 * Cloudflare Worker & Container entrypoint for DocShield Production Frontend & API Gateway.
 *
 * Architecture:
 *   USER -> Cloudflare -> React/Vite Frontend (env.ASSETS)
 *        -> Cloudflare Worker (/api/* routing)
 *        -> Cloudflare Container (DocShieldBackendContainer on port 8000)
 *        -> FastAPI (OCR / OpenCV / dlib / PyTorch / Risk Engine)
 *
 * Responsibilities:
 * 1. Export DocShieldBackendContainer (Cloudflare Container Durable Object running FastAPI on port 8000).
 * 2. Route /api/*, /health, and /ready requests to the Cloudflare Container binding
 *    (env.DOCSHIELD_BACKEND), with optional upstream failover if env.BACKEND_ORIGIN is configured.
 * 3. Serve compiled Vite production assets from frontend/dist via env.ASSETS
 *    with strict, accurate MIME types (application/javascript, text/css, etc.).
 * 4. Never return index.html (text/html) for missing .js/.jsx/.css/image asset requests.
 * 5. Provide SPA fallback (/index.html) only for extensionless client-side routes.
 */

import { Container, getContainer } from "@cloudflare/containers";

const CONTAINER_SINGLETON_NAME = "docshield-api-singleton";

/**
 * Cloudflare Container Durable Object backing the DocShield FastAPI AI/CV backend.
 * Runs the Docker image built from ./backend/Dockerfile on TCP port 8000.
 */
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

  // Fallback if Wrangler was invoked with --assets=. or --assets=frontend
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

async function routeToBackend(request, env, url) {
  const contentLength = Number(request.headers.get("Content-Length") || "0");
  if (contentLength > 10 * 1024 * 1024) {
    return new Response(
      JSON.stringify({
        detail: "File size exceeds maximum allowed limit of 10MB.",
      }),
      {
        status: 413,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "X-Content-Type-Options": "nosniff",
          "X-DocShield-Backend": "cloudflare-worker",
        },
      }
    );
  }

  const proxyHeaders = buildForwardedHeaders(request, env);
  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  // 1. Primary Route: Cloudflare Container (DocShieldBackendContainer on port 8000)
  if (env.DOCSHIELD_BACKEND) {
    const fallbackClone =
      hasBody && env.BACKEND_ORIGIN ? request.clone() : null;
    try {
      const containerStub = getContainer(
        env.DOCSHIELD_BACKEND,
        CONTAINER_SINGLETON_NAME
      );
      const containerUrl = `http://localhost:8000${url.pathname}${url.search}`;
      const containerReq = new Request(containerUrl, {
        method: request.method,
        headers: proxyHeaders,
        body: hasBody ? request.body : undefined,
        redirect: "manual",
      });
      const containerRes = await containerStub.fetch(containerReq);
      if (containerRes.status < 502) {
        const responseHeaders = new Headers(containerRes.headers);
        responseHeaders.set("X-Content-Type-Options", "nosniff");
        responseHeaders.set("X-DocShield-Backend", "cloudflare-container");
        return new Response(containerRes.body, {
          status: containerRes.status,
          statusText: containerRes.statusText,
          headers: responseHeaders,
        });
      }
    } catch (_) {
      // Fall through if optional BACKEND_ORIGIN secret is configured
    }

    if (fallbackClone) {
      request = fallbackClone;
    }
  }

  // 2. Optional Configured Upstream Route (if env.BACKEND_ORIGIN secret/var is provided)
  const backendOrigin = (env.BACKEND_ORIGIN || "").trim().replace(/\/+$/, "");
  if (backendOrigin) {
    const targetUrl = `${backendOrigin}${url.pathname}${url.search}`;
    const init = {
      method: request.method,
      headers: proxyHeaders,
      redirect: "manual",
    };

    if (hasBody) {
      init.body = request.body;
    }

    try {
      const upstream = await fetch(targetUrl, init);
      if (
        url.pathname === "/ready" &&
        (upstream.headers.get("content-type") || "").includes("text/html")
      ) {
        const healthRes = await fetch(`${backendOrigin}/api/health`, {
          method: "GET",
          headers: proxyHeaders,
        });
        const healthJson = await healthRes.json();
        return new Response(
          JSON.stringify({
            status: healthJson.status === "healthy" ? "ready" : "degraded",
            mode: env.DOCSHIELD_MODE || "PROTOTYPE",
            checks: healthJson.modules || {},
            timestamp: healthJson.timestamp || new Date().toISOString(),
          }),
          {
            status: healthRes.status,
            headers: {
              "Content-Type": "application/json; charset=utf-8",
              "X-Content-Type-Options": "nosniff",
              "X-DocShield-Backend": "cloudflare-worker",
            },
          }
        );
      }
      const responseHeaders = new Headers(upstream.headers);
      responseHeaders.set("X-Content-Type-Options", "nosniff");
      responseHeaders.set("X-DocShield-Backend", "cloudflare-worker");
      return new Response(upstream.body, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers: responseHeaders,
      });
    } catch (_) {
      // Fall through to 502 error response
    }
  }

  return new Response(
    JSON.stringify({
      detail:
        "Screening backend is temporarily unreachable. Please retry in a few seconds.",
    }),
    {
      status: 502,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    }
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;

    // 1. Route API & Health endpoints to Cloudflare Container
    if (
      pathname.startsWith("/api/") ||
      pathname === "/health" ||
      pathname === "/ready"
    ) {
      return routeToBackend(request, env, url);
    }

    // 2. Never serve raw development source paths (/src/*) in production
    if (pathname.startsWith("/src/")) {
      return new Response("Not Found", {
        status: 404,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    // 3. Serve built static files from frontend/dist via Cloudflare Workers Static Assets
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

      // 4. Do NOT return index.html for missing JS, CSS, image, or file-extension requests
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

      // 5. SPA Fallback: Serve compiled /index.html for client-side navigation routes
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

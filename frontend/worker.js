/**
 * Cloudflare Worker entrypoint for DocShield Production Frontend & API Gateway.
 * (Located in frontend/worker.js to support Cloudflare Workers Builds when Root directory = "frontend")
 */

const DEFAULT_BACKEND_ORIGIN = "https://docshield-production.up.railway.app";

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
  headers.set("Permissions-Policy", "camera=(self), microphone=(), geolocation=()");

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
    const fallbackRes = await env.ASSETS.fetch(new Request(fallbackUrl, request));
    if (fallbackRes.status !== 404) {
      return fallbackRes;
    }
  }

  return primaryRes;
}

async function proxyBackendRequest(request, env, url) {
  const backendOrigin = (env.BACKEND_ORIGIN || DEFAULT_BACKEND_ORIGIN)
    .trim()
    .replace(/\/+$/, "");

  const targetUrl = `${backendOrigin}${url.pathname}${url.search}`;
  const proxyHeaders = new Headers(request.headers);
  proxyHeaders.delete("host");

  const clientIp = request.headers.get("CF-Connecting-IP");
  if (clientIp) {
    proxyHeaders.set("CF-Connecting-IP", clientIp);
    proxyHeaders.set("X-Forwarded-For", clientIp);
  }
  proxyHeaders.set("X-Forwarded-Proto", "https");

  const init = {
    method: request.method,
    headers: proxyHeaders,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }

  try {
    const upstream = await fetch(targetUrl, init);
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set("X-Content-Type-Options", "nosniff");
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (_) {
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
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;

    // 1. Proxy API & Health endpoints to the FastAPI backend
    if (
      pathname.startsWith("/api/") ||
      pathname === "/health" ||
      pathname === "/ready"
    ) {
      return proxyBackendRequest(request, env, url);
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

    // 3. Serve built static files from dist via Cloudflare Workers Static Assets
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

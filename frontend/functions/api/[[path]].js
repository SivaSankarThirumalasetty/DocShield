/**
 * Optional Cloudflare Pages Function API Gateway Proxy (`/api/*`).
 *
 * Architecture Note:
 * - Primary mode: Frontend calls the Python FastAPI backend directly over HTTPS
 *   using `VITE_API_BASE_URL` (e.g. `https://<actual-production-backend-domain>`).
 * - Optional API Gateway mode: If `VITE_API_BASE_URL` is left blank (same-origin)
 *   and `BACKEND_ORIGIN` is configured in Cloudflare Pages environment variables,
 *   this Pages Function proxies `/api/*` requests at the Cloudflare edge to the
 *   Python/FastAPI backend while preserving multipart uploads and security headers.
 */
export async function onRequest(context) {
  const { request, env } = context;
  const backendOrigin = (env.BACKEND_ORIGIN || "").trim().replace(/\/+$/, "");

  if (!backendOrigin) {
    return new Response(
      JSON.stringify({
        detail:
          "API gateway not configured. Set VITE_API_BASE_URL at build time or BACKEND_ORIGIN in Cloudflare Pages environment variables.",
      }),
      {
        status: 503,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      }
    );
  }

  const incomingUrl = new URL(request.url);
  const targetUrl = `${backendOrigin}${incomingUrl.pathname}${incomingUrl.search}`;

  const proxyHeaders = new Headers(request.headers);
  proxyHeaders.set("X-Forwarded-Host", incomingUrl.host);
  proxyHeaders.set("X-Forwarded-Proto", incomingUrl.protocol.replace(":", ""));

  try {
    const upstreamResponse = await fetch(targetUrl, {
      method: request.method,
      headers: proxyHeaders,
      body:
        request.method !== "GET" && request.method !== "HEAD"
          ? request.body
          : undefined,
      redirect: "manual",
    });

    const responseHeaders = new Headers(upstreamResponse.headers);
    responseHeaders.set(
      "Cache-Control",
      "no-store, no-cache, must-revalidate, private, max-age=0"
    );
    responseHeaders.set("X-Content-Type-Options", "nosniff");

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  } catch (err) {
    return new Response(
      JSON.stringify({
        detail:
          "Screening backend is temporarily unreachable from the Cloudflare edge gateway. Please retry shortly.",
      }),
      {
        status: 502,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      }
    );
  }
}

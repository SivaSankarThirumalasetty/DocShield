// Shared response helpers for the DocShield edge Worker.

export const API_SECURITY_HEADERS = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
};

// The SPA loads only its own bundled JS/CSS plus Google Fonts.
export const HTML_CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: blob:",
  "connect-src 'self'",
  "media-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

export function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...API_SECURITY_HEADERS,
      ...extraHeaders,
    },
  });
}

export function errorJson(status, detail, extraHeaders = {}) {
  return json({ detail }, status, extraHeaders);
}

export function withApiHeaders(response, requestId) {
  const headers = new Headers(response.headers);
  for (const [k, v] of Object.entries(API_SECURITY_HEADERS)) headers.set(k, v);
  headers.delete("Set-Cookie");
  headers.delete("Server");
  if (requestId) headers.set("X-Request-ID", requestId);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

export function clientIp(request) {
  return request.headers.get("CF-Connecting-IP") || "unknown";
}

export function requestIdFor(request) {
  return request.headers.get("CF-Ray") || crypto.randomUUID();
}

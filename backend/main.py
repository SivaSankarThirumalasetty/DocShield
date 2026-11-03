import hmac
import os
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .core.config import settings
from .core.logging import logger
from .api.routes import router, readiness_checks, APP_VERSION
from .services.ocr_service import ocr_service

# Built frontend served by this process only when deployed as a single app (Vercel).
# Elsewhere (Cloudflare Worker, local Vite) the frontend is served separately.
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(Path(__file__).resolve().parent.parent / "webui")))

HTML_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; "
    "media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)

# Multipart framing overhead allowed on top of two maximum-size images.
MAX_REQUEST_BYTES = settings.max_upload_size_bytes * 2 + 64 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.preload_models:
        started = time.time()
        ocr_service.warm_up()
        logger.info(f"Model warm-up finished in {round(time.time() - started, 1)}s")
    result = readiness_checks()
    logger.info(
        f"DocShield API v{APP_VERSION} started [{settings.operating_mode}/{settings.app_env}] "
        f"ready={result['ready']} checks={result['checks']}"
    )
    yield
    logger.info("DocShield API shutting down")


is_production = settings.app_env == "production"

app = FastAPI(
    title="DocShield API",
    description="AI-assisted document screening prototype (advisory only)",
    version=APP_VERSION,
    docs_url=None if is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if is_production else "/api/openapi.json",
    lifespan=lifespan,
)


class RequestGuardMiddleware(BaseHTTPMiddleware):
    """Request ID, body-size ceiling, structured access log, and security headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("cf-ray") or request.headers.get("x-request-id") or uuid.uuid4().hex
        request_id = request_id[:64]

        if settings.edge_shared_secret and request.url.path != "/health":
            supplied = request.headers.get("x-docshield-edge-auth", "")
            if not hmac.compare_digest(supplied.encode("utf-8"), settings.edge_shared_secret.encode("utf-8")):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized."})

        content_length = request.headers.get("content-length")
        if request.method == "POST":
            if content_length is None:
                return JSONResponse(status_code=411, content={"detail": "Content-Length required."})
            try:
                too_large = int(content_length) > MAX_REQUEST_BYTES
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
            if too_large:
                return JSONResponse(status_code=413, content={"detail": "Request body too large."})

        started = time.time()
        response = await call_next(request)
        elapsed = round((time.time() - started) * 1000, 1)
        logger.info(f"request_id={request_id} method={request.method} path={request.url.path} status={response.status_code} ms={elapsed}")

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        path = request.url.path
        if response.status_code == 200 and path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif response.status_code == 200 and path.startswith("/samples/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        else:
            response.headers["Cache-Control"] = "no-store"
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Content-Security-Policy"] = HTML_CSP
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        else:
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response


app.add_middleware(RequestGuardMiddleware)

# CORS is only relevant for local development; production is same-origin via the Worker.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Officer-Key", "X-Session-Token", "Accept"],
)


@app.exception_handler(Exception)
async def safe_exception_handler(request: Request, exc: Exception):
    # Traceback stays server-side (and passes through the PII-redacting formatter).
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {type(exc).__name__}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal processing error. Please try again."}
    )


app.include_router(router)

# Mounted last so every API route above takes precedence. html=True serves index.html for
# "/" only; there is no SPA catch-all, so unknown /api paths still return a JSON 404.
if (FRONTEND_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

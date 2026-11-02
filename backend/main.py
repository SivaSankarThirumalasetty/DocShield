import hmac
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .core.config import settings
from .core.logging import logger
from .api.routes import router, readiness_checks, APP_VERSION
from .services.ocr_service import ocr_service

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
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
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

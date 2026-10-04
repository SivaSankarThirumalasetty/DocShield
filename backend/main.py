import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .core.config import settings
from .core.logging import logger
from .api.routes import router

# ---------------------------------------------------------
# Application Initialization
# ---------------------------------------------------------

app = FastAPI(
    title="DocShield API",
    description="Multi-Layered Identity Credential & Document Screening Platform",
    version="2.0.0",
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url="/api/redoc" if settings.app_env != "production" else None
)

# ---------------------------------------------------------
# Security Headers & Anti-Caching Middleware
# ---------------------------------------------------------

class SecurityAndPrivacyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Anti-Caching Directives: Prevent browser/proxy retention of sensitive identity data
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        # Defensive Security Headers & Font/Script CSP permissions
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' data: blob:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' *; "
            "frame-ancestors 'none';"
        )
        # Ensure static assets are not blocked by browser CORS checks on module scripts
        if request.url.path.startswith(("/assets", "/samples", "/favicon")):
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif "Origin" in request.headers and request.headers["Origin"] in settings.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = request.headers["Origin"]

        is_https = (
            request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "").lower() == "https"
        )
        if is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

app.add_middleware(SecurityAndPrivacyHeadersMiddleware)

# ---------------------------------------------------------
# Configurable CORS Middleware (No Wildcard Credentials)
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Officer-Key", "X-Session-Token", "Cache-Control", "Accept"],
)

# ---------------------------------------------------------
# Safe Global Exception Handler
# ---------------------------------------------------------

@app.exception_handler(Exception)
async def safe_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Verification processing error. Please ensure the document is clear and try again."}
    )

# ---------------------------------------------------------
# API Routes Mounting
# ---------------------------------------------------------

app.include_router(router)

# ---------------------------------------------------------
# Static Frontend Delivery (Single-Container Production)
# ---------------------------------------------------------

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
    if (DIST_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")
    if (DIST_DIR / "samples").exists():
        app.mount("/samples", StaticFiles(directory=str(DIST_DIR / "samples")), name="samples")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = DIST_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")

logger.info(f"DocShield API v2.0.0 started in [{settings.operating_mode}] mode. Environment: [{settings.app_env}]")

import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

def load_dotenv(dotenv_path: Path):
    """Simple, zero-dependency .env loader."""
    if not dotenv_path.exists():
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"[!] Warning: Failed to load .env from {dotenv_path}: {e}")

# Load .env if present
load_dotenv(BASE_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

class Settings(BaseModel):
    # Application Mode
    app_env: str = Field(default_factory=lambda: os.getenv("DOCSHIELD_ENV", "development"))
    operating_mode: str = Field(default_factory=lambda: os.getenv("DOCSHIELD_MODE", "PROTOTYPE"))
    
    # Network Binding
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    
    # Security & CORS
    frontend_origin: str = Field(
        default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "").strip()
    )
    cors_origins_raw: str = Field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,https://docshield.pages.dev"
        )
    )
    cors_origin_regex: str = Field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGIN_REGEX",
            r"^https://([a-z0-9-]+\.)?docshield(-[a-z0-9-]+)?\.pages\.dev$"
        )
    )
    officer_key: str = Field(
        default_factory=lambda: os.getenv("DOCSHIELD_OFFICER_KEY", "docshield-officer-secret-key-change-in-production")
    )
    
    # Upload & Concurrency Constraints
    max_upload_size_bytes: int = Field(
        default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))
    )
    max_image_pixels: int = Field(
        default_factory=lambda: int(os.getenv("MAX_IMAGE_PIXELS", "10000000"))
    )
    upload_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("UPLOAD_TIMEOUT_SECONDS", "30"))
    )
    max_concurrent_analysis: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_ANALYSIS", "2"))
    )
    rate_limit_analyze_per_minute: int = Field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_ANALYZE_PER_MINUTE", "10"))
    )
    
    # Privacy & Storage Settings
    enable_source_image_storage: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_SOURCE_IMAGE_STORAGE", "false").lower() in ("true", "1", "yes")
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'docshield.db'}")
    )
    
    # Diagnostics & Debug
    enable_debug_endpoint: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_DEBUG_ENDPOINT", "false").lower() in ("true", "1", "yes")
    )
    
    # Retention
    data_retention_hours: int = Field(
        default_factory=lambda: int(os.getenv("DATA_RETENTION_HOURS", "24"))
    )

    @property
    def cors_origins(self) -> List[str]:
        origins = [
            origin.strip().rstrip("/")
            for origin in self.cors_origins_raw.split(",")
            if origin.strip() and origin.strip() != "*"
        ]
        if self.frontend_origin and self.frontend_origin != "*":
            clean_fe = self.frontend_origin.rstrip("/")
            if clean_fe not in origins:
                origins.append(clean_fe)
        return origins

settings = Settings()

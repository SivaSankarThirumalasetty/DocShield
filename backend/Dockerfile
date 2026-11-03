# syntax=docker/dockerfile:1.7
# ==========================================================================
# DocShield backend image (FastAPI + Tesseract + OpenCV + dlib + EasyOCR)
# Built by `wrangler deploy` for the Cloudflare Container, and by CI.
# Build context: the backend/ directory.
#   docker build -t docshield-backend backend/
# ==========================================================================

# ---- Stage 1: build wheels (dlib needs a C++ toolchain) and fetch model weights
FROM python:3.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

RUN pip install torch==2.14.1 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Bake the EasyOCR detector/recogniser weights into the image so no model is
# ever downloaded at request time (runtime sets EASYOCR_DOWNLOAD_ENABLED=false).
ENV EASYOCR_MODULE_PATH=/opt/easyocr
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, model_storage_directory='/opt/easyocr/model', download_enabled=True, verbose=False)" \
    && ls -l /opt/easyocr/model

# ---- Stage 2: minimal runtime
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/easyocr /opt/easyocr

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DOCSHIELD_ENV=production \
    DOCSHIELD_MODE=PROTOTYPE \
    PERSISTENCE_MODE=none \
    PRELOAD_MODELS=true \
    REQUIRE_FULL_PIPELINE=true \
    EASYOCR_MODULE_PATH=/opt/easyocr \
    EASYOCR_DOWNLOAD_ENABLED=false \
    MAX_CONCURRENT_ANALYSIS=1 \
    OMP_NUM_THREADS=1

WORKDIR /app
COPY --chown=root:root . /app/backend
RUN rm -rf /app/backend/tests /app/backend/data/*.db* \
    && python -c "import backend.services.face_service as f; assert f.face_service.net is not None, 'face detector weights missing'"

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=4).status == 200 else 1)"

CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --no-server-header --timeout-graceful-shutdown 20 --limit-concurrency 32"]

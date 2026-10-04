# ==========================================
# DocShield Cloudflare Container / Standalone FastAPI Backend
# ==========================================
# Supports building from EITHER:
#   1. backend/ context (Cloudflare Containers default for image = "./backend/Dockerfile"):
#      docker build -t docshield-backend:latest backend/
#   2. Repository root context:
#      docker build -f backend/Dockerfile -t docshield-backend:latest .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    DOCSHIELD_ENV=production \
    DOCSHIELD_MODE=PROTOTYPE \
    EASYOCR_MODULE_PATH=/root/.EasyOCR

# Install system dependencies for OpenCV, Tesseract OCR, dlib, and CMake build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    cmake \
    libsm6 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-optimized PyTorch wheel first
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install Python requirements (cached layer; works from both root and backend/ contexts)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm -f /tmp/requirements.txt

# Copy build context and normalize into /app/backend, /app/models_weights, /app/data, and /root/.EasyOCR/model
COPY . /tmp/ctx
RUN mkdir -p /app/backend /root/.EasyOCR/model && \
    if [ -f /tmp/ctx/backend/main.py ]; then \
        cp -a /tmp/ctx/backend/. /app/backend/; \
    else \
        cp -a /tmp/ctx/. /app/backend/; \
    fi && \
    rm -rf /tmp/ctx && \
    ln -sf /app/backend/models_weights /app/models_weights && \
    ln -sf /app/backend/data /app/data && \
    if [ -d /app/backend/models_weights/easyocr ]; then \
        cp -f /app/backend/models_weights/easyocr/*.pth /root/.EasyOCR/model/ 2>/dev/null || true; \
    fi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

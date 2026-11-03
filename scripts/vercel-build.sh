#!/usr/bin/env bash
# Vercel build step: fetch the exact repository commit named in DEPLOY_SHA (the deploy
# uploads only this bootstrap), the pinned Tesseract English model, and build the UI.
set -euo pipefail

REPO="SivaSankarThirumalasetty/DocShield"
SHA="$(tr -d '[:space:]' < DEPLOY_SHA 2>/dev/null || true)"
if [ -n "$SHA" ] && [ ! -d backend ]; then
  echo "Fetching $REPO@$SHA"
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/$SHA" | tar xz --strip-components=1
fi
test -f backend/main.py

# tessdata_fast eng model (Apache-2.0), pinned by commit and SHA-256.
TESSDATA_COMMIT="87416418657359cb625c412a48b6e1d6d41c29bd"
TESSDATA_SHA256="7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"
mkdir -p backend/tessdata
curl -fsSL -o backend/tessdata/eng.traineddata \
  "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/$TESSDATA_COMMIT/eng.traineddata"
echo "$TESSDATA_SHA256  backend/tessdata/eng.traineddata" | sha256sum -c -

# Frontend: Vercel Functions accept request bodies up to 4.5 MB.
npm --prefix frontend ci --no-audit --no-fund
VITE_MAX_UPLOAD_TOTAL_MB=4.3 npm --prefix frontend run build
rm -rf webui && cp -r frontend/dist webui
echo "Build complete: $(ls webui | tr '\n' ' ')"

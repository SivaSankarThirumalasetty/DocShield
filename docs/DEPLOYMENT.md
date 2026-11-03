# Deployment (₹0 / free tiers)

## Live architecture (2026-11-03)

```
Browser → https://docshield.sivasankar-t1606.workers.dev   (Cloudflare Workers Free: UI, /api routing,
            │                                                rate limits, D1 redacted cases, reviewer tokens)
            └── HTTPS ──→ https://docshield-ss-ec9e.vercel.app   (Vercel Hobby: FastAPI screening backend)
```

* **Primary URL:** `docshield.sivasankar-t1606.workers.dev` — full feature set (cases stored 24 h, reviewer console).
* `docshield-ss-ec9e.vercel.app` also serves the UI directly but without the Worker: no case storage,
  no reviewer features, only the backend's per-instance rate limit.
* Worker deployed with `npx wrangler deploy --var BACKEND_URL:https://docshield-ss-ec9e.vercel.app --var GIT_COMMIT:<sha>`
  after `VITE_MAX_UPLOAD_TOTAL_MB=4.3 npm --prefix frontend run build` (Vercel's 4.5 MB body limit).
* Worker secret `EDGE_SHARED_SECRET` is set, but the Vercel backend does **not** enforce it yet, because doing so
  would disable the direct Vercel UI. To make the Worker the only entry point, set the same value as
  `EDGE_SHARED_SECRET` in the Vercel project env and redeploy (rotate it: `npx wrangler secret put EDGE_SHARED_SECRET`).
* Obsolete Worker secret `BACKEND_ORIGIN` (old tunnel) still exists and is unused; remove with
  `npx wrangler secret delete BACKEND_ORIGIN` once you no longer need it.

## Live now: Vercel Hobby (free) — single app

**https://docshield-ss-ec9e.vercel.app** — Vercel project `docshield` (`prj_Kg2lpIVHR2aRSTQw7HUjBN0WfV86`),
region `sin1`, Hobby plan (no payment method). One FastAPI function serves both the UI
(`webui/`, mounted after all API routes) and `/api/*`.

| Item | Detail |
|---|---|
| Entrypoint | `app.py` → `backend.main:app`; deps in root `requirements.txt` (Python 3.12) |
| OCR | Tesseract 5.5 as a library (`tesserocr`), `tessdata_fast` eng model fetched at build (SHA-256 pinned) |
| Faces | OpenCV SSD detector + dlib 128-d embeddings (prebuilt `dlib-bin`, direct embedder) |
| Not available | EasyOCR/PyTorch (bundle size); case storage, reviewer sign-in and case history (no D1 without the Cloudflare Worker) — the UI says "not stored" |
| Limits | 4.5 MB request body (UI enforces 4.3 MB total), 60 s per request, Hobby usage quotas; Hobby is for non-commercial use |
| Env (project settings) | `DOCSHIELD_ENV=production`, `PERSISTENCE_MODE=none`, `READY_REQUIRES=ocr_tesseract,face_detector,face_embedding,demo_registry`, `MAX_UPLOAD_SIZE_BYTES=4508876`, rate/concurrency limits |
| Protection | Production domain public; per-deployment and preview URLs require Vercel login |

**Redeploy** (any pushed commit): with the Vercel CLI from the repo root, `npx vercel deploy --prod`
(the build script uses the local checkout); or upload the bootstrap files (`app.py`, `requirements.txt`,
`vercel.json`, `.python-version`, `scripts/vercel-build.sh`) plus a `DEPLOY_SHA` file containing the commit —
the build then fetches exactly that commit from GitHub. **Rollback:** Vercel dashboard → Deployments →
promote an earlier deployment.

## Alternative: Cloudflare Worker (free) + Render (free)

The sections below describe the Cloudflare-fronted setup (D1 case storage, reviewer tokens). It needs
the owner actions listed under *One-time setup*; it is implemented and tested in CI but not live.

```
Browser → Cloudflare Worker "docshield" (Workers Free) → static UI, /api routing, D1 (free)
                     └── HTTPS + X-DocShield-Edge-Auth ──→ Render free web service (Docker)
                                                           FastAPI + Tesseract + OpenCV + dlib
```

No paid plan, payment method or billable resource is required. Nothing depends on a personal PC.

## Free-tier limits that shape behaviour

| Service | Limit (provider docs, Nov 2026) | Effect on DocShield |
|---|---|---|
| Cloudflare Workers Free | 100,000 requests/day, **10 ms CPU per request**, 50 external subrequests | Worker streams the backend body without parsing it; stores a small pre-redacted record |
| Cloudflare D1 Free | Daily row read/write limits (queries fail until midnight UTC when exceeded) | 24 h retention keeps the table tiny |
| Render Free web service | **512 MB RAM, 0.1 CPU**, sleeps after 15 min idle (~1 min to wake), 750 instance-hours/month, ephemeral disk, "not for production" | EasyOCR/PyTorch excluded (need >1 GB); slow screenings; UI shows "Engine starting…" while waking |

If Render's 750 hours or bandwidth run out without a payment method on file, Render suspends the
service until next month — the site stays up and honestly reports the engine as unavailable.
**Do not add a payment method to Render or upgrade the Cloudflare plan** if the bill must stay at ₹0.

## One-time setup (owner actions)

1. **Render** (free account, no card): Dashboard → *New* → *Blueprint* → select this repository
   (`render.yaml`). When prompted, set `EDGE_SHARED_SECRET` to a long random value, e.g. from:

   ```bash
   node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
   ```

   Note the service URL (e.g. `https://docshield-backend.onrender.com`). Check `GET <url>/health` returns 200.
   If Render asks for a payment method to create a *free* service, stop: that breaks the ₹0 requirement.
2. **Cloudflare API token** (free): My Profile → API Tokens → custom token with
   *Account · Workers Scripts · Edit*, *Account · D1 · Edit*, *User · User Details · Read*.
3. **GitHub** (repo → Settings):
   * Secrets → Actions: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `EDGE_SHARED_SECRET` (same value as Render).
   * Variables → Actions: `BACKEND_URL` = the Render https URL.
   * Environments: create `production` (optionally with required reviewers).
4. Merge the PR into `master`.

Already created on the Cloudflare account: D1 `docshield-db`
(`ccbed719-5867-444d-8c21-22aceca7a284`, migration `0001` applied).

## What a release does (`.github/workflows/deploy.yml`)

1. Full CI (lint, unit/contract tests, both images, free image under 512 MB / 0.1 CPU, audits, gitleaks).
2. Wakes the Render backend; checks `/health` = 200 and `/api/ready` without the secret = 401.
3. `wrangler d1 migrations apply`, `wrangler deploy --var BACKEND_URL:… --var GIT_COMMIT:<sha>`,
   `wrangler secret put EDGE_SHARED_SECRET`.
4. Waits for `/api/ready` = 200 reporting the new commit, then live smoke tests: static 200,
   missing asset 404, unknown API 404, `/api/cases` 401, real screening of
   `sample_data/aadhaar_invalid_checksum.png` (OCR must complete, checksum must fail, record stored),
   case retrieval with/without token (200/404).

Render redeploys the backend itself on every push to `master` (`autoDeploy`). The first Worker
deploy after this change applies migration `v2`, deleting the unused container Durable Object class.

## Reviewer accounts

```bash
node scripts/create-officer-token.mjs --id REV-001 --name "A. Reviewer" --days 30 --apply
```

## Optional paid mode (not used)

`wrangler.containers.jsonc` runs the full image (incl. EasyOCR/PyTorch) on Cloudflare Containers.
It needs Workers Paid and Docker, and a new migration re-adding the Durable Object class
(e.g. `{ "tag": "v3", "new_sqlite_classes": ["DocShieldBackendContainer"] }`).

## Troubleshooting

| Symptom | Check |
|---|---|
| UI "Engine starting…" for 1–2 min | Render waking from sleep; expected on the free tier |
| `/api/ready` 503, `backend.status = "unreachable"` | `BACKEND_URL` var, Render service state/suspension, `EDGE_SHARED_SECRET` mismatch (backend returns 401) |
| 503 "engine is busy" | One screening at a time on 0.1 CPU; retry after `Retry-After` |
| `persistence.status = "FAILED"` | D1 daily free limit or migration; `npx wrangler d1 migrations list docshield-db --remote` |
| Worker error 1102 / exceeded CPU | Should not happen (body is streamed); check Workers logs |

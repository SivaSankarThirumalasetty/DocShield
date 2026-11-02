# Deployment (₹0 / free tiers)

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

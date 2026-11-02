# Deployment

## Prerequisites (owner actions)

1. **Workers Paid plan** on the Cloudflare account (Containers are not available on Free).
2. **GitHub repository secrets** (Settings → Secrets and variables → Actions):
   * `CLOUDFLARE_ACCOUNT_ID`
   * `CLOUDFLARE_API_TOKEN` — create a *custom* token with only:
     * Account · Workers Scripts · Edit
     * Account · Containers · Edit
     * Account · D1 · Edit
     * Account · Workers Observability · Read (optional, for logs)
     * User · User Details · Read (Wrangler identity check)
3. **GitHub Environment** named `production` with required reviewers (gates every deploy).
4. **Branch protection** on `master`: require the CI checks and a pull-request review.

Resources already created on the account (2026-11-02):

| Resource | Name | ID |
|---|---|---|
| Worker | `docshield` | existing (`workers.dev` URL below) |
| D1 | `docshield-db` | `ccbed719-5867-444d-8c21-22aceca7a284` (migration `0001` applied) |

Production URL: `https://docshield.sivasankar-t1606.workers.dev`

## Normal release

1. Open a PR into `master`. CI (`.github/workflows/ci.yml`) runs: frontend lint/build/audit,
   Worker unit tests and wrangler config validation, backend tests + API contract test +
   pip-audit, Docker image build with full-pipeline tests inside the image, gitleaks.
2. Merge. `deploy.yml` re-runs CI, then (after environment approval):
   `npm run build` → `wrangler d1 migrations apply` → `wrangler deploy --var GIT_COMMIT:<sha>`
   (builds and pushes the container image, uploads assets, rolls out the container).
3. The job polls `/api/ready` until it returns 200 **and** reports the new commit, then runs
   live smoke tests: static 200, missing asset 404, unknown API JSON 404, `/api/cases` 401,
   a real screening of `sample_data/aadhaar_invalid_checksum.png` (OCR must complete,
   checksum must fail, record must be stored), retrieval with/without the token (200/404).
4. Any failed step fails the workflow. See [ROLLBACK.md](ROLLBACK.md).

Note: `wrangler deploy` activates the new Worker before the container rollout finishes, and
the steps are not transactional. The readiness gate catches a broken rollout; it cannot
prevent the brief window in which new Worker code talks to the old container.

## Manual deploy (owner machine)

Requires Docker running and `npx wrangler login`.

```bash
npm ci && npm run build
```

```bash
npx wrangler d1 migrations apply docshield-db --remote
```

```bash
npx wrangler deploy --var GIT_COMMIT:$(git rev-parse HEAD)
```

## Reviewer accounts

```bash
node scripts/create-officer-token.mjs --id REV-001 --name "A. Reviewer" --days 30 --apply
```

The token is printed once. Revoke with the command in the script header.

## Configuration

| Name | Where | Purpose |
|---|---|---|
| `DOCSHIELD_MODE` | `wrangler.jsonc` vars | Mode label (`PROTOTYPE`) |
| `CASE_RETENTION_HOURS` | vars | D1 case retention (1–720, default 24) |
| `APP_VERSION`, `GIT_COMMIT` | vars / deploy flag | Reported by `/api/ready` |
| Container env | `worker/src/index.js`, `backend/Dockerfile` | `PERSISTENCE_MODE=none`, `PRELOAD_MODELS=true`, `REQUIRE_FULL_PIPELINE=true`, `EASYOCR_DOWNLOAD_ENABLED=false` |

No secrets are required by the Worker at runtime. Never put secrets in `VITE_*` variables.

## Troubleshooting

| Symptom | Check |
|---|---|
| `/api/ready` 503 with `backend.status = "timeout"` | First request after deploy or after sleep; model load takes ~1–2 min. `npx wrangler containers list`, Workers logs. |
| `/api/ready` 503 with a `checks` entry `false` | That model/binary is missing from the image; inspect CI container job logs. |
| `persistence.status = "FAILED"` | D1 binding/migration. `npx wrangler d1 migrations list docshield-db --remote`. |
| 429 | Edge rate limit (10/min/IP per location). |
| Deploy fails "Docker CLI is needed" | Run from CI or start Docker locally. |

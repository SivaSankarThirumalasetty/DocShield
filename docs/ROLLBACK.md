# Rollback

## Worker + container image

```bash
npx wrangler deployments list
```

```bash
npx wrangler rollback <VERSION_ID> --message "rollback: <reason>"
```

`wrangler rollback` restores a previous Worker version. Verify afterwards that the
container serves the matching image:

```bash
npx wrangler containers list
```

If the container image must also go back, check out the last known good commit and
redeploy it (CI or manual):

```bash
git checkout <GOOD_SHA>
```

```bash
npm ci && npm run build && npx wrangler deploy --var GIT_COMMIT:<GOOD_SHA>
```

Then confirm `curl https://docshield.sivasankar-t1606.workers.dev/api/ready` returns 200 with
`edge.commit` equal to `<GOOD_SHA>`.

## Backend on Render

Render keeps previous deploys: Dashboard → docshield-backend → *Events* → choose an earlier
successful deploy → *Rollback*. Or revert the commit on `master`; Render auto-deploys it.
After rollback, confirm `/api/ready` on the site returns 200.

## D1

Migrations are additive (`CREATE … IF NOT EXISTS`). Do not roll back by dropping tables.
D1 Time Travel can restore the database to a point in time if data is corrupted:

```bash
npx wrangler d1 time-travel info docshield-db
```

```bash
npx wrangler d1 time-travel restore docshield-db --timestamp <UNIX_TS>
```

Restoring overwrites newer data; record the reason in the incident log first.

## Previous hosting

The old Railway service and the tunnel-to-PC setup are **not** deleted by this change.
Do not retire them until Cloudflare is independently verified and the owner approves.
The Worker no longer routes to them, so restoring them would require redeploying an
older commit (pre-`cloudflare-migration` rewrite), which reintroduces finding C1
(authentication bypass). Prefer rolling back within Cloudflare/Render.

#!/usr/bin/env node
// Creates a per-reviewer bearer token. The raw token is printed ONCE to stdout;
// only its SHA-256 hash is written to D1.
//
//   node scripts/create-officer-token.mjs --id REV-001 --name "A. Reviewer" \
//        [--tenant public-demo] [--role reviewer] [--days 30] [--apply]
//
// Without --apply it prints the wrangler command instead of running it.
// Revoke with:
//   npx wrangler d1 execute docshield-db --remote --command \
//     "UPDATE officers SET revoked_at = datetime('now') WHERE officer_id = 'REV-001'"
import { randomBytes, createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => {
    if (a.startsWith("--")) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith("--") ? all[i + 1] : true]);
    return acc;
  }, [])
);

const id = String(args.id || "");
const name = String(args.name || "");
const tenant = String(args.tenant || "public-demo");
const role = String(args.role || "reviewer");
const days = Number(args.days || 30);

if (!/^[A-Za-z0-9_-]{1,64}$/.test(id) || !name || name.length > 128 || !/^[a-z0-9-]{1,64}$/.test(tenant)) {
  console.error("Usage: --id <A-Za-z0-9_- up to 64> --name <display name> [--tenant <slug>] [--role reviewer|admin] [--days N] [--apply]");
  process.exit(2);
}
if (!["reviewer", "admin"].includes(role) || !(days > 0 && days <= 365)) {
  console.error("--role must be reviewer|admin and --days 1-365");
  process.exit(2);
}

const token = randomBytes(32).toString("base64url");
const hash = createHash("sha256").update(token).digest("hex");
const now = new Date();
const expires = new Date(now.getTime() + days * 86400_000);
const q = (s) => `'${s.replace(/'/g, "''")}'`;
const sql =
  "INSERT INTO officers (officer_id, tenant_id, display_name, role, token_hash, created_at, expires_at) VALUES (" +
  [id, tenant, name, role, hash, now.toISOString(), expires.toISOString()].map(q).join(", ") +
  ")";
const wranglerArgs = ["wrangler", "d1", "execute", "docshield-db", "--remote", "--command", sql];

if (args.apply) {
  execFileSync("npx", wranglerArgs, { stdio: ["ignore", "ignore", "inherit"], shell: process.platform === "win32" });
  console.error(`Stored hash for ${id} (tenant ${tenant}, expires ${expires.toISOString()}).`);
} else {
  console.error("Run this to store the token hash:\n  npx " + wranglerArgs.slice(0, -1).join(" ") + ` "${sql}"`);
}
console.error("\nBearer token (shown once; deliver over a secure channel):");
console.log(token);

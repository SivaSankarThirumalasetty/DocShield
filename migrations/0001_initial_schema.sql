-- DocShield D1 schema. Applied with: wrangler d1 migrations apply docshield-db --remote
-- Stores only minimised (redacted) screening records; never images or OCR text.

CREATE TABLE IF NOT EXISTS cases (
  case_id                TEXT PRIMARY KEY,
  tenant_id              TEXT NOT NULL,
  created_at             TEXT NOT NULL,
  expires_at             TEXT NOT NULL,
  session_token_hash     TEXT NOT NULL,
  document_type          TEXT NOT NULL,
  document_number_masked TEXT,
  risk_score             INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
  risk_level             TEXT NOT NULL,
  verdict                TEXT NOT NULL,
  review_json            TEXT,
  result_json            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_tenant_created ON cases (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_expires ON cases (expires_at);

-- One row per reviewer credential. Tokens are random 256-bit values; only the
-- SHA-256 hash is stored. Created with scripts/create-officer-token.mjs.
CREATE TABLE IF NOT EXISTS officers (
  officer_id   TEXT PRIMARY KEY,
  tenant_id    TEXT NOT NULL,
  display_name TEXT NOT NULL,
  role         TEXT NOT NULL CHECK (role IN ('reviewer', 'admin')),
  token_hash   TEXT NOT NULL UNIQUE,
  created_at   TEXT NOT NULL,
  expires_at   TEXT NOT NULL,
  revoked_at   TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT NOT NULL,
  tenant_id  TEXT NOT NULL,
  case_id    TEXT,
  actor      TEXT NOT NULL,
  action     TEXT NOT NULL,
  detail     TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log (case_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log (ts);

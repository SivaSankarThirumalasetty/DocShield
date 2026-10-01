# DOCSHIELD SECURITY & PRIVACY SPECIFICATION
**Document Version:** 1.0.0  
**Classification:** Technical Security Architecture & Privacy Policy  
**System:** DocShield Multi-Layered Document Screening & Forensics Engine  
**Target Environment:** Public Demonstration / Prototype Hosting  

---

## 1. EXECUTIVE SUMMARY & THREAT MODEL

DocShield processes identity documents (passports, national ID cards, driver licenses) and live traveller photographs. Under international and national data protection standards (including the Indian Digital Personal Data Protection Act 2023, the Indian Aadhaar Act 2016, and the European Union General Data Protection Regulation - GDPR), identity documents and facial imagery are classified as **Special Category & Sensitive Personal Data**.

This document outlines the defense-in-depth security perimeter, privacy guardrails, and cryptographic controls implemented in DocShield to protect users, prevent automated exploitation, and guarantee data minimization.

---

## 2. 24-POINT SECURITY & PRIVACY AUDIT MATRIX

| # | Domain | Threat / Vulnerability | Implemented Defense & Architecture | Status |
|---|---|---|---|---|
| **1** | **Authentication** | Unauthorized access to administrative & review functions | Officer endpoints require `X-Officer-Key` header token. Anonymous users cannot access officer review workflows. | **HARDENED** |
| **2** | **Authorization** | BOLA / IDOR on case dockets | Submitters receive a cryptographically random `session_token`. Case retrieval requires matching session token or officer authorization. | **HARDENED** |
| **3** | **Rate Limiting** | Automated resource exhaustion & scraping | Per-IP sliding-window rate limiter restricts `/api/analyze-document` to 10 requests / minute / IP. | **HARDENED** |
| **4** | **CORS** | Cross-Origin Data Theft / CSRF exploitation | Restrictive whitelist configured via `CORS_ORIGINS`. Wildcard `*` origins with credentials are strictly prohibited. | **HARDENED** |
| **5** | **CSRF** | Cross-Site Request Forgery | All state-mutating endpoints (`/api/analyze-document`, `/api/case/{id}/review`) require custom headers (`Content-Type: multipart/form-data`, `Content-Type: application/json`, and `X-Session-Token`). | **HARDENED** |
| **6** | **Security Headers** | Clickjacking, MIME-sniffing, XSS | Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and Content Security Policy (`frame-ancestors 'none'`). | **HARDENED** |
| **7** | **Upload Validation** | Disguised executable / Polyglot file attacks | Strict magic-byte signature validation (JPEG `\xff\xd8\xff`, PNG `\x89PNG\r\n\x1a\n`, WebP `RIFF...WEBP`). Filenames and `Content-Type` headers are never trusted. | **HARDENED** |
| **8** | **Request Size Limits** | Buffer overflow / Memory exhaustion | Starlette middleware rejects payloads exceeding 10MB with HTTP 413. PIL dimensions capped at 10 megapixels to neutralize decompression bombs. | **HARDENED** |
| **9** | **Timeout Protection** | Slowloris / Hung ML inference blocking threads | Async pipeline bounds CPU tasks; request execution times out cleanly with structured error responses. | **HARDENED** |
| **10**| **Path Traversal** | Dot-dot-slash (`../`) directory climbing | All filenames pass through `sanitize_filename()`, stripping directory paths and non-alphanumeric characters. | **HARDENED** |
| **11**| **File Handling** | Malformed image parser exploitation | In-memory stream validation using PIL `verify()` and safe matrix conversion (`cv2.imdecode`) prior to deep processing. | **HARDENED** |
| **12**| **Temp File Cleanup** | Orphaned disk accumulation of identity documents | Images are processed ephemerally in RAM. No unencrypted raw source files are left lingering on disk. | **HARDENED** |
| **13**| **Case Authorization**| Public enumeration of previous users' screening results | `GET /api/cases` is restricted exclusively to authenticated officers (`X-Officer-Key`). Anonymous access returns HTTP 401. | **HARDENED** |
| **14**| **ID Enumeration** | Sequential case ID harvesting (`/api/case/1`, `/api/case/2`) | Case IDs use randomized UUIDv4 hex tokens (`DS-YYYYMMDD-XXXXXXXX`). Session tokens prevent guessing. | **HARDENED** |
| **15**| **Error Messages** | Internal stack trace & directory disclosure | Global exception interceptor catches all faults, logs tracebacks server-side, and serves sanitized generic messages to clients. | **HARDENED** |
| **16**| **Logging** | Leakage of sensitive PII into syslog / cloud logs | Custom `PIIRedactingFilter` automatically scrubs Aadhaar numbers (`XXXX-XXXX-1234`), PANs, passport numbers, and auth tokens from logs. | **HARDENED** |
| **17**| **Database Access** | SQL Injection & Lock Contention | Managed via SQLAlchemy 2.0 parameterized ORM. SQLite configured with Write-Ahead Logging (WAL) for thread-safe concurrent access. | **HARDENED** |
| **18**| **Secrets Management**| Hardcoded credentials in source code | All credentials, keys, and URLs are loaded dynamically from environment variables (`.env`). | **HARDENED** |
| **19**| **Dependencies** | Vulnerable transitive libraries | PyTorch/DeepFace removed in favor of lightweight, secure, and audited standard libraries. | **HARDENED** |
| **20**| **Sensitive Fields** | Full 12-digit Aadhaar disclosure | Enforced Aadhaar masking (`XXXX-XXXX-1234`) at extraction boundary; unmasked 12 digits are never stored or rendered. | **HARDENED** |
| **21**| **Data Retention** | Indefinite hoarding of biometric/identity data | Raw uploaded image previews are scrubbed from database records. Database retention policy auto-purges stale records. | **HARDENED** |
| **22**| **Browser Caching** | Local disk caching of identity documents on shared terminals | Enforced `Cache-Control: no-store, no-cache, must-revalidate, private, max-age=0`, `Pragma: no-cache`, `Expires: 0`. | **HARDENED** |
| **23**| **Image Caching** | Static reverse-proxy caching of passport scans | Verification previews are served with no-cache headers; no public static URLs are generated for user-submitted credentials. | **HARDENED** |
| **24**| **API Abuse & DoS** | CPU saturation via multi-threaded verification requests | Global asynchronous concurrency semaphore (`MAX_CONCURRENT_ANALYSIS = 2`) queues or rejects excess concurrent CV jobs. | **HARDENED** |

---

## 3. DATA FLOW & PRIVACY ARCHITECTURE

```
[USER BROWSER]
      │
      │ 1. Uploads Document Scan & Live Selfie (HTTPS)
      ▼
[SECURITY PERIMETER (backend/main.py & core/security.py)]
      │
      ├─► Magic Byte Check (JPEG / PNG / WebP only)
      ├─► Size Limit Guard (Max 10MB)
      ├─► Decompression Bomb Guard (Max 10 MP)
      ├─► Rate Limiter (Max 10 req/min/IP)
      └─► Concurrency Semaphore (Max 2 concurrent CV analyses)
      │
      ▼
[IN-MEMORY PROCESSING PIPELINE]
      │
      ├─► OCR Service: Extracts fields; immediately masks Aadhaar -> XXXX-XXXX-1234
      ├─► Tampering Forensics: Computes local ELA compression anomalies (non-definitive advisory)
      ├─► Face Biometrics: Compares 128-d facial embeddings (Strict: MATCH / MISMATCH / INDETERMINATE)
      ├─► Watchlist Service: Queries DEMO_WATCHLIST (7 sample records; marked non-authoritative)
      └─► Risk Engine: Balanced multi-factor scoring (Biometric Imposter > Expired Document)
      │
      ▼
[EPHEMERAL DATABASE STORAGE (backend/services/storage_service.py)]
      │
      ├─► Raw document image bytes: DISCARDED FROM RAM
      ├─► Raw person photo bytes: DISCARDED FROM RAM
      ├─► Base64 full-res previews: STRIPPED FROM PERSISTENT DATABASE RECORD
      ├─► Stored record: Case ID, Masked Document Number, Forensic Scores, Timestamp
      └─► Access Key: SHA-256 hash of random session_token (Client holds raw token)
      │
      ▼
[RESPONSE TO SUBMITTER]
      │
      ├─► Headers: Cache-Control: no-store, no-cache, private
      ├─► Body: ScreeningResult JSON + session_token
      └─► Browser renders interactive report (Memory revoked on tab close)
```

---

## 4. PROTOTYPE LIMITATIONS & WHAT USERS MUST NOT DO

### 1. Do NOT Upload Real Government Credentials
DocShield is currently configured as a **Public Prototype Demonstration** for the Smart India Hackathon (SIH 2026). Although strict security controls and memory-scrubbing mechanisms are active, **users should never submit real, unredacted passports, Aadhaar cards, or driver licenses to any public demonstration website**.

### 2. How to Safely Test the System
- **Use Sample Presets:** The frontend includes built-in synthetic presets (Valid Indian Passport, Tampered Passport, Stolen Passport). These presets allow full end-to-end testing of OCR, MRZ checksums, ELA forensics, face matching, and risk aggregation without any sensitive data.
- **Use Synthetic Test Cards:** When uploading custom files, use watermarked mock documents or black out your personal name, address, and document numbers.

### 3. Non-Authoritative Status
- The watchlist service queries `DEMO_WATCHLIST`, a static JSON dataset containing exactly 7 fictional test records.
- DocShield does not connect to live UIDAI CIDR, Interpol I-24/7, or state border databases in Prototype Mode.
- All risk scores and flags are automated algorithmic signals for officer decision-support and do not constitute legal determinations.

---

## 5. ITEMS REQUIRING PROFESSIONAL LEGAL & COMPLIANCE REVIEW

Prior to deploying DocShield in an **Authorized Operational Environment** (e.g. government border checkpoints, immigration desks, or law enforcement stations), the following formal reviews and certifications are mandatory:

1. **UIDAI / Aadhaar Act Statutory Certification:** Formal legal review under Section 29 of the Aadhaar Act 2016 and UIDAI Authentication User Agency (AUA) / KYC User Agency (KUA) guidelines.
2. **DPDP Act (2023) Data Protection Impact Assessment (DPIA):** Comprehensive DPIA under the Indian Digital Personal Data Protection Act 2023 evaluating consent mechanisms and automated processing.
3. **NIST FRVT Biometric Accuracy Certification:** Independent algorithmic benchmarking of facial recognition algorithms against National Institute of Standards and Technology (NIST) Face Recognition Vendor Test standards to verify False Match Rates (FMR) and demographic parity.
4. **Third-Party CREST / CERT-In Penetration Testing:** External black-box and white-box penetration testing and vulnerability assessment by CERT-In empaneled security auditors.
5. **Hardware Security Module (HSM) Key Management:** Integration of FIPS 140-2 Level 3 HSMs for cryptographic key storage when managing official digital certificates and officer signing keys.

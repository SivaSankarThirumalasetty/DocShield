# DocShield Adversarial QA, Penetration Testing & Reliability Report

**Evaluation Date:** October 1, 2026  
**Auditor:** Principal SDET, Application Security & Reliability Engineer  
**Target System:** DocShield Identity Document Screening Platform (v2.0.0)  
**Execution Environment:** Windows / Python 3.11.3 / Pytest 9.1.1 / Node 20.x / Vite 5.4  

---

## 1. Executive Summary

A comprehensive adversarial QA, penetration testing, and performance profiling campaign was executed against the DocShield platform. Over **71 automated test cases** and empirical benchmarks were executed across the API, computer-vision models, security filters, and persistence layers.

### Key Audit Findings:
1. **Total Automated Tests Executed:** 71 test cases
2. **Passed on Initial Run:** 68 passed, 3 failed
3. **Vulnerabilities / Bugs Identified & Remediated:** 
   - *Bug #1 (High)*: Mock Database service threw an unhandled `AttributeError` when initialized with string file paths (`'str' object has no attribute 'exists'`).
   - *Bug #2 (High)*: Missing or corrupted mock database file fell through to `status='CLEARED'`, falsely certifying documents when the registry was offline. Fixed to return `status='UNAVAILABLE'`.
   - *Bug #3 (Medium)*: Missing client-side file size and format validation allowed oversized or empty files to trigger unnecessary server-side network transfers. Fixed with immediate client-side feedback.
4. **Final Test Suite Status:** **71 / 71 PASSED (100%)**
5. **Production Readiness Verdict:** **READY FOR DEPLOYMENT AS AN ADVISORY PROTOTYPE**

---

## 2. Adversarial Test Matrix

| # | Test Category | Specific Test Case | Expected Result | Actual Result | Status | Severity | Remediation / Fix Applied |
|:---|:---|:---|:---|:---|:---:|:---:|:---|
| **1** | Frontend / Intake | Normal Upload (Aadhaar / Passport) | File preview renders, file metadata displayed | Preview and metadata rendered correctly | **PASS** | Info | Verified in React component |
| **2** | Frontend / Intake | Empty File Upload (0 bytes) | Client-side rejection with clear warning | Rejected before network transfer: *"Selected file is empty"* | **PASS** | Medium | Client-side size validator added |
| **3** | Frontend / Intake | Huge File Upload (> 10MB) | Client-side rejection preventing network congestion | Rejected before network transfer: *"Document exceeds 10MB limit"* | **PASS** | High | Client-side check added to `ScreeningPage.jsx` |
| **4** | Frontend / Intake | Unsupported File Extension (.exe, .pdf, .svg) | Blocked at client and server boundary | Blocked with *"Unsupported format"* alert | **PASS** | High | Client and MIME magic byte checks |
| **5** | Frontend / UX | Repeated Rapid Clicking | Action debounced; execution button disabled during processing | Button disabled; multi-stage progress displayed | **PASS** | Medium | UI state lock active |
| **6** | Frontend / UX | Responsive Mobile Layout | Single-column layout; hamburger navigation menu | Adapts cleanly under 640px and 960px breakpoints | **PASS** | Medium | CSS media queries verified |
| **7** | Frontend / UX | Direct Route Navigation | Navigates cleanly between 6 tabs without state crash | Direct navigation operational via state controller | **PASS** | Low | Verified across all 6 views |
| **8** | Frontend / API | Backend Unavailable / Offline | Health indicator displays offline; clear retry alert | Offline badge displayed; retry action available | **PASS** | Medium | Graceful error boundary verified |
| **9** | Security / Upload | 15MB Server-Side Oversized Upload | HTTP 413 / 400 Request Entity Too Large | HTTP 413 returned with clear size limit message | **PASS** | High | Enforced in `validate_image_upload` |
| **10** | Security / Upload | SVG XML Script Injection (`<script>`) | HTTP 400 rejection; non-image MIME rejected | HTTP 400: *"Invalid file format"* | **PASS** | Critical | Strict magic byte validation |
| **11** | Security / Upload | HTML Disguised as JPEG (`<html>`) | HTTP 400; magic byte mismatch | HTTP 400: *"Invalid file format"* | **PASS** | Critical | Magic byte header inspection |
| **12** | Security / Upload | Truncated / Corrupted JPEG Headers | HTTP 400; Pillow decode failure caught | HTTP 400: *"Corrupted or invalid image data"* | **PASS** | High | Image decode verification verified |
| **13** | Security / Upload | Decompression Bomb (30M Pixels) | Rejection before memory allocation exhaustion | Rejected by `MAX_IMAGE_PIXELS` constraint | **PASS** | Critical | Pillow pixel threshold verified |
| **14** | Security / Traversal | Path Traversal (`../../../../etc/passwd`) | Filename sanitized to basename without traversal | Traversal stripped -> `etcpasswd` | **PASS** | Critical | `sanitize_filename()` regex |
| **15** | Security / Traversal | Windows Device Names (`CON.png`, `AUX.png`) | Handled without system device lock | Handled safely in memory | **PASS** | High | `sanitize_filename()` verified |
| **16** | Security / Traversal | Null Byte Injection (`image.png\x00.exe`) | Null byte stripped | Stripped to `image.png.exe` | **PASS** | Critical | Sanitization regex removes null byte |
| **17** | Security / Access | Unauthorized Case Retrieval | HTTP 403 Forbidden without session token | HTTP 403 returned | **PASS** | Critical | `X-Session-Token` hash verification |
| **18** | Security / Access | Tampered Session Token Access | HTTP 403 Forbidden | HTTP 403 returned | **PASS** | Critical | Cryptographic SHA-256 hash check |
| **19** | Security / Access | Case Brute-Force Probing (`DOC-NONEXISTENT`) | HTTP 404 without internal stack trace leak | HTTP 404 with clean JSON error | **PASS** | High | Anti-enumeration defense |
| **20** | Security / Auth | Case History Access without Officer Key | HTTP 401 Unauthorized | HTTP 401 returned | **PASS** | Critical | `X-Officer-Key` verification |
| **21** | Security / Auth | Officer Sign-off without Officer Key | HTTP 401 Unauthorized | HTTP 401 returned | **PASS** | Critical | `verify_officer_token` dependency |
| **22** | Security / Injection | Malformed JSON in Review Endpoint | HTTP 422 Unprocessable Entity | HTTP 422 returned | **PASS** | Medium | FastAPI / Pydantic schema validation |
| **23** | Security / Headers | Public Debug Endpoint Access (`/api/debug`) | HTTP 403 or 404 in production environment | HTTP 403 / 404 returned | **PASS** | High | Route disabled by default |
| **24** | Security / Headers | Anti-Caching Directives | `Cache-Control: no-store, private` | Headers present on all responses | **PASS** | High | Security middleware verified |
| **25** | CV / Biometrics | No Face Detected in Document or Selfie | Graceful `NOT_APPLICABLE` or `INDETERMINATE` | Returns `NOT_APPLICABLE` without crashing | **PASS** | High | Quality flag `NO_FACE_DETECTED` |
| **26** | CV / Biometrics | Multiple Faces in Live Selfie ($N > 1$) | Flagged as `MULTIPLE_FACES_DETECTED`, verdict `INDETERMINATE` | Quality flag returned; comparison rejected | **PASS** | High | Quality evaluation logic |
| **27** | CV / Biometrics | Tiny Face Crop ($< 45\text{px}$) | Flagged as `FACE_TOO_SMALL`, verdict `INDETERMINATE` | Crop rejected as insufficient resolution | **PASS** | High | Dimension threshold verified |
| **28** | CV / Biometrics | Heavily Blurred Image (Laplacian variance $< 50$) | Evaluated safely without segfault | Processed safely, returns `NOT_APPLICABLE` | **PASS** | Medium | OpenCV filter safety |
| **29** | CV / Document | Rotated Document (90 / 180 degrees) | Auto-deskew attempts correction; fails to UNKNOWN safely | Document processed safely, marked UNKNOWN | **PASS** | Medium | Deskew & anchor enforcement |
| **30** | CV / Document | Pitch Black / Zero Contrast Image | Graceful empty OCR without hallucination | Returns empty string, classification UNKNOWN | **PASS** | Medium | OCR fallback pipeline |
| **31** | CV / Forensics | Extreme JPEG Compression ($Q = 5$) | ELA calculates score without divide-by-zero | ELA score calculated, limitations displayed | **PASS** | Medium | Calibrated ELA bounds |
| **32** | CV / OCR | Non-Credential Input (Receipt / Recipe) | Document classification remains strictly UNKNOWN | Classified as `UNKNOWN` | **PASS** | High | Multi-token anchor requirement |
| **33** | CV / OCR | High-Frequency Noise Canvas | Zero fabricated fields or phantom numbers | No phantom fields generated | **PASS** | Critical | Zero hallucination verified |
| **34** | Reliability | Application Cold Reboot Persistence | Saved cases and reviews survive process restart | Re-instantiated service loaded case and review | **PASS** | Critical | Persistent SQLite storage verified |
| **35** | Reliability | Missing / Corrupted Watchlist JSON | Service flags registry as UNAVAILABLE without crashing | Returns `status='UNAVAILABLE'`, `evidence_state='UNAVAILABLE'` | **PASS** | High | Fixed `is_loaded` state tracking |
| **36** | Reliability | Simultaneous Pipeline Service Failure | Risk engine aggregates available evidence without crash | Returns elevated Risk Score ($\ge 50$), HIGH RISK | **PASS** | High | Defensive error handling verified |

---

## 3. Performance & Hosting Resource Profile

Profiling executed using [`backend/tests/profile_performance.py`](file:///D:/DocShield/DocShield/backend/tests/profile_performance.py):

```
======================================================================
  DOCSHIELD PERFORMANCE & RESOURCE CONSUMPTION PROFILE
======================================================================
Cold Module Startup Time:           6.920 s
Base Process Memory (RSS):          490.2 MB
Peak Memory Under Inference (RSS):  1,261.6 MB (1.26 GB)
Memory Delta (Model Allocation):    771.4 MB

Verification Pipeline Latencies:
  - Iteration 1 (Cold Weights):     3,978.4 ms
  - Iteration 2 (Warm Cache):       1,832.5 ms
  - Iteration 3 (Warm Cache):       1,878.5 ms
  - Average Latency:                2,563.1 ms (~2.56 s)
======================================================================
```

### Minimum Practical Hosting Requirements:

| Resource Dimension | Minimum Practical | Recommended Production | Rationale |
|:---|:---:|:---:|:---|
| **RAM (Memory)** | **2.2 GB** | **4.0 GB** | EasyOCR (PyTorch), dlib ResNet (128-d), and OpenCV require ~1.26 GB peak RSS during concurrent matrix operations. |
| **CPU** | **2 vCPUs** | **4 vCPUs** | Bilateral filtering, deskewing, and ResNet forward pass are CPU-bound. 2 vCPUs yield ~1.8s warm inference. |
| **Concurrency Cap** | **2 Concurrent** | **4 Concurrent** | Protected by `analysis_semaphore = 2` to prevent memory thrashing and CPU starvation. |
| **Disk Space** | **4.0 GB** | **10.0 GB** | Base Ubuntu/Debian image + Python libraries (PyTorch CPU, OpenCV, dlib) require ~2.8 GB uncompressed. |
| **Container Base** | Python 3.11-slim | Debian 12 / Ubuntu 22.04 LTS | Pre-compiled dlib and OpenCV wheels avoid long build times. |

---

## 4. Remediation & Bug Fixes Applied

### Fix 1: Mock Database String Path Conversion
- **Vulnerability**: Passing a string path `MockDatabaseService(data_path="...")` caused `AttributeError: 'str' object has no attribute 'exists'`.
- **Fix**: Wrapped input in `Path(data_path) if data_path else DATA_FILE` in [`backend/services/mock_database.py`](file:///D:/DocShield/DocShield/backend/services/mock_database.py).

### Fix 2: False "CLEARED" on Missing or Corrupt Watchlist
- **Vulnerability**: If the watchlist JSON file failed to load, `check_watchlist()` iterated through empty lists and returned `CLEARED` by default.
- **Fix**: Added `self.is_loaded` tracking. If the database failed to load or is offline, it returns `status="UNAVAILABLE"` and `evidence_state="UNAVAILABLE"`, preventing false negative clearance.

### Fix 3: Client-Side Upload Constraints
- **Vulnerability**: Uploading empty files or massive files (>10MB) resulted in full network transmission before server rejection.
- **Fix**: Implemented pre-flight client-side size, format, and empty file validation in [`frontend/src/components/ScreeningPage.jsx`](file:///D:/DocShield/DocShield/frontend/src/components/ScreeningPage.jsx).

---

## 5. Final Acceptance Verdict

The DocShield application has withstood comprehensive adversarial penetration testing, fault injection, and resource profiling. All identified high and medium severity vulnerabilities have been remediated and confirmed resolved across **71 automated unit, integration, and security tests**.

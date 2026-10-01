# DOCSHIELD AI & COMPUTER VISION LIMITATIONS SPECIFICATION
**Document Version:** 1.0.0  
**Status:** Official ML Validation & Technical Capability Disclosure  
**Audit Statement:** *Not validated for production accuracy. Prototype sample evaluation only.*  

---

## 1. EXECUTIVE TECHNICAL REALITY STATEMENT

DocShield utilizes an ensemble of Optical Character Recognition (OCR), Rule-Based Parsing, Convolutional Neural Networks (CNNs), and Error Level Analysis (ELA) to provide decision-support signals for identity credential screening.

> [!WARNING]
> **STATUTORY DISCLAIMER:** This system is an engineering prototype developed for demonstration. It has **not** undergone NIST FRVT biometric benchmarking, ISO/IEC 19794 compliance auditing, or large-scale statistical validation across diverse global populations and lighting environments. Under no circumstances should these algorithmic signals be treated as legal proof of identity or automated clearance.

---

## 2. MODULE-BY-MODULE AUDIT & SPECIFICATION

### 1. Optical Character Recognition (OCR)
- **INPUT:** Preprocessed, deskewed RGB document crop (PIL Image, max 1600px).
- **PROCESSING:** 
  1. Primary: PyTesseract (`--oem 3 --psm 6`) with adaptive Otsu binarization.
  2. Fallback: EasyOCR deep-learning text detection (CRAFT) and recognition (CRNN/ResNet).
- **OUTPUT:** Raw UTF-8 text string, word tokens with bounding boxes `[x, y, w, h]`, and token confidence scores.
- **CONFIDENCE:** Mean character/word confidence percentage ($0.0 - 100.0\%$).
- **FAILURE STATE:** When no text is detected or confidence $< 30\%$, returns `success=False`, `raw_text=""`, and `evidence_state="UNAVAILABLE"`. Fields are **never fabricated**.

### 2. Document Classification
- **INPUT:** Extracted OCR text string, optional client hint.
- **PROCESSING:** Strict multi-token anchor verification.
  - Aadhaar: Requires UIDAI terms AND (12-digit number OR "Government of India").
  - PAN: Requires Income Tax terms OR (10-char PAN regex AND "Govt. of India").
  - Passport: Requires "Passport" / "Republic of India" OR valid ICAO MRZ start sequence (`P<`).
- **OUTPUT:** Classification string: `PASSPORT`, `AADHAAR`, `PAN`, `VOTER_ID`, or `UNKNOWN`.
- **CONFIDENCE:** Binary deterministic classification based on anchor matches.
- **FAILURE STATE:** Ambiguous or generic documents strictly remain `UNKNOWN` (`evidence_state="INDETERMINATE"`).

### 3. Field Extraction
- **INPUT:** Raw OCR text string, document classification.
- **PROCESSING:** Regular expression parsing with post-OCR character substitution (e.g. `O` $\rightarrow$ `0` in numbers, `1` $\rightarrow$ `I` in names).
- **OUTPUT:** Structured `ExtractedFields` (document number, name, DOB, gender, expiry).
- **CONFIDENCE:** Field completeness metric: percentage of mandatory fields populated ($0.0 - 100.0\%$).
- **FAILURE STATE:** Missing fields remain `None`. Aadhaar numbers are masked to `XXXX-XXXX-1234` before model instantiation.

### 4. Machine Readable Zone (MRZ) Parsing
- **INPUT:** Detected candidate text lines from passport lower third.
- **PROCESSING:** ICAO Doc 9303 Part 4 TD3 standard parsing (2 lines $\times$ 44 characters). Validates syntax and character set `[A-Z0-9<]`.
- **OUTPUT:** Structured MRZ dictionary (issuing state, surname, given names, doc number, nationality, DOB, sex, expiry, optional data).
- **CONFIDENCE:** Direct parity between extracted text and standard ICAO structure.
- **FAILURE STATE:** If lines $< 2$ or syntax invalid, returns `None` and sets `evidence_state="INDETERMINATE"`.

### 5. Checksum Validation
- **INPUT:** Extracted document numbers and MRZ fields.
- **PROCESSING:**
  - Passports: ICAO Doc 9303 modulo 10 algorithm with repeating $[7, 3, 1]$ weighting on Document Number, Date of Birth, Expiry Date, and Composite string.
  - Aadhaar: Verhoeff algorithm ($D_{10}$ dihedral group multiplication and permutation matrices).
- **OUTPUT:** Boolean flags per checksum.
- **CONFIDENCE:** Mathematical certainty ($100\%$ algorithmic validity for tested string).
- **FAILURE STATE:** Checksum mismatch triggers `FAIL` flag with `critical` severity.

### 6. Document Expiration Verification
- **INPUT:** Extracted ISO date string (`YYYY-MM-DD`).
- **PROCESSING:** Temporal comparison against current UTC date `datetime.date.today()`.
- **OUTPUT:** Boolean validity flag and elapsed / remaining days.
- **CONFIDENCE:** High (dependent on OCR date extraction accuracy).
- **FAILURE STATE:** If date is past, flags `FAIL` (`DOCUMENT_EXPIRED`). If date is unreadable, flags `INDETERMINATE`.

### 7. Face Detection
- **INPUT:** Full document image or traveller live photograph.
- **PROCESSING:**
  1. Primary: OpenCV Caffe SSD face detector (`res10_300x300_ssd_iter_140000_fp16.caffemodel`).
  2. Fallback: OpenCV Haar Cascade (`haarcascade_frontalface_default.xml`).
- **OUTPUT:** Face bounding boxes `(x, y, w, h)`, face count, and cropped face matrix.
- **CONFIDENCE:** Caffe SSD softmax detection confidence ($0.0 - 1.0$).
- **FAILURE STATE:**
  - Multiple faces detected ($>1$): Flags `MULTIPLE_FACES_DETECTED` $\rightarrow$ `INDETERMINATE`.
  - Tiny face crop ($< 45\times 45$ px): Flags `FACE_TOO_SMALL` $\rightarrow$ `INDETERMINATE`.
  - Zero faces detected: Flags `NO_FACE_DETECTED` $\rightarrow$ `INDETERMINATE`.

### 8. Biometric Face Verification
- **INPUT:** Cropped document portrait and live traveller face image.
- **PROCESSING:**
  - Deep 128-dimensional facial feature embedding via dlib ResNet-34 (`face_recognition.face_encodings`).
  - Metric: Euclidean distance between normalized feature vectors:
    $$D(\mathbf{u}, \mathbf{v}) = \|\mathbf{u} - \mathbf{v}\|_2$$
  - Threshold: Statutory match threshold at $D \le 0.60$.
- **OUTPUT:** Similarity score ($0 - 100\%$), Euclidean distance, match verdict (`MATCH`, `MISMATCH`).
- **CONFIDENCE:** Linear confidence scale inversely proportional to distance.
- **FAILURE STATE:**
  - If model weights missing: Emits `NOT_AVAILABLE` $\rightarrow$ Never substitutes 2D template matching!
  - If faces unreadable: Emits `INDETERMINATE`.

### 9. Digital Image Forensics (Tamper Analysis)
- **INPUT:** Document image (PIL Image).
- **PROCESSING:** Error Level Analysis (ELA) resaving image in RAM at 90% JPEG quality; computes difference matrix, standard deviation, and localized anomaly patches ($> 3\sigma$).
- **OUTPUT:** ELA anomaly score ($0 - 100$), bounding boxes of compression discrepancies, and advisory notes.
- **CONFIDENCE:** Calibrated against image resolution (low-resolution images $< 400\times 300$ receive lower analysis confidence).
- **LIMITATIONS:** ELA evaluates JPEG compression quantization artifacts only. Cannot detect analog forgery, physical cut-and-paste on paper before scanning, or advanced generative AI re-sampling.

### 10. Confidence Handling
- Every module outputs an explicit confidence metric.
- Confidence scores are never combined via arbitrary averaging; instead, each signal is evaluated against its domain threshold.

### 11. Fallback Behavior
- All fallbacks are strictly defensive:
  - If deep biometrics are offline $\rightarrow$ Verdict is `NOT_AVAILABLE`, forcing officer review.
  - If MRZ is unreadable $\rightarrow$ Checksum status is `INDETERMINATE`.
  - If watchlist database is offline $\rightarrow$ Status is `UNAVAILABLE`, **never `CLEARED`**.

### 12. Multi-Factor Risk Aggregation
- **INPUT:** All evidence outputs from modules 1 through 9.
- **PROCESSING:** Transparent weighted additive penalty scoring reflecting national security priorities:
  - Watchlist Alert: $+75$
  - Biometric Impersonation (`MISMATCH`): $+65$
  - Document Format/Checksum Failure: $+35$
  - Document Expired: $+25$
  - Biometric Inconclusive (`INDETERMINATE`): $+25$
  - Service Offline (`UNAVAILABLE`): $+20$
- **OUTPUT:** Score ($0 - 100$), Risk Tier (`LOW`, `MEDIUM`, `HIGH`), and Officer Recommendation.
- **EVIDENCE STATES:** Preserves exact provenance: `PASS`, `FAIL`, `INDETERMINATE`, `UNAVAILABLE`, `DEMO`.

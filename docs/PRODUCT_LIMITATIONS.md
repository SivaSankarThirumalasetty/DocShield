# Product Limitations

DocShield is an **AI-assisted document screening prototype**. It is not a government
verification service, an identity database, or a certified fraud detector. Every
output is advisory; a qualified human reviewer is responsible for every consequential
decision. The application never authorises, denies, or detains anyone.

## What each signal can and cannot tell you

| Signal | What it is | What it is not |
|---|---|---|
| OCR + parsing | Tesseract / EasyOCR text with rule-based field extraction | Reliable on real-world photos; validated per document type |
| Classification | Anchor-word rules; defaults to `UNKNOWN` | A layout/security-feature check |
| Verhoeff (Aadhaar) | Arithmetic check digit on the extracted number | Proof a number was issued or belongs to the holder |
| ICAO MRZ check digits | 7-3-1 checks on MRZ fields | Proof a passport is genuine |
| Registry check | **SIMULATED** 7-record demo JSON | A UIDAI, passport, police, stolen-document or watchlist lookup. No live registry is integrated. |
| ELA | JPEG re-compression difference heuristic | Proof of forgery or of authenticity. Screenshots, re-saves and messaging apps cause false signals. |
| Face comparison | dlib 128-d embedding distance vs a fixed 0.60 threshold | A calibrated probability of identity; liveness or anti-spoofing; validated across demographics |
| Score 0–100 | Sum of fixed heuristic penalties, bands at 30 / 65 | A probability of fraud. Not calibrated or validated on any representative dataset. |

## Outcome rules

* `NO_ADVERSE_INDICATORS` is possible only when OCR, validation and ELA each produced a
  conclusive result and no applicable signal was unavailable.
* Missing models, failed OCR, unavailable registry, failed face processing produce
  `UNAVAILABLE` / `INDETERMINATE` states and add penalties; they never lower the score.
* A missing person photo is `NOT_APPLICABLE`, never a match.

## Evidence base

The only test data are four synthetic cartoon images. There has been **no evaluation** on
representative, consented data. Before any commercial or operational use:

1. Collect a representative, consented dataset per document type, capture device and population.
2. Independent evaluation: false-positive / false-negative rates at the chosen thresholds,
   with confidence intervals.
3. Bias evaluation of face comparison and OCR across age, skin tone, gender, script and image quality.
4. Calibrate or replace the heuristic score; document the validation study.
5. Domain-expert (document examiner) review of the ELA and classification logic.
6. Legal review: Aadhaar Act and regulations, DPDP Act 2023, sector rules, model licences.

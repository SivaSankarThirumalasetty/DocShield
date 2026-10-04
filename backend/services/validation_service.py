import re
from datetime import datetime, date
from typing import List, Optional, Tuple
from ..models.schemas import ValidationFlag, ValidationResult, ExtractedFields

# Verhoeff algorithm multiplication and permutation matrices
VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
]

VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
]

def validate_verhoeff(number_str: str) -> bool:
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) != 12:
        return False
    c = 0
    reversed_digits = digits[::-1]
    for i, num in enumerate(reversed_digits):
        c = VERHOEFF_D[c][VERHOEFF_P[i % 8][num]]
    return c == 0

def parse_iso_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    cleaned = date_str.strip().replace('/', '-').replace('.', '-')
    patterns = ['%Y-%m-%d', '%d-%m-%Y', '%d-%m-%y', '%m-%d-%Y', '%Y%m%d']
    for p in patterns:
        try:
            return datetime.strptime(cleaned, p).date()
        except ValueError:
            continue
    return None

class ValidationService:
    def validate_document(self, doc_info: ExtractedFields) -> ValidationResult:
        flags: List[ValidationFlag] = []
        doc_type = (doc_info.document_type or "UNKNOWN").upper()
        doc_num = (doc_info.document_number or "").replace(" ", "").upper()

        # 1. Document Format & Checksum Verification
        if doc_type == "AADHAAR":
            if doc_num.startswith("XXXX-XXXX-"):
                # Masked for statutory compliance
                flags.append(ValidationFlag(
                    check_name="Aadhaar Privacy Redaction",
                    field="document_number",
                    passed=True,
                    message="Aadhaar first 8 digits redacted per Section 29 Aadhaar Act 2016",
                    severity="info",
                    evidence_state="PASS"
                ))
                if doc_info.verhoeff_valid is not None:
                    is_verhoeff = bool(doc_info.verhoeff_valid)
                    flags.append(ValidationFlag(
                        check_name="Verhoeff Checksum",
                        field="document_number",
                        passed=is_verhoeff,
                        message="Aadhaar Verhoeff checksum algorithm verified (evaluated prior to redaction)" if is_verhoeff else "Aadhaar Verhoeff checksum failed: invalid card structure",
                        severity="info" if is_verhoeff else "critical",
                        evidence_state="PASS" if is_verhoeff else "FAIL"
                    ))
            else:
                digits_only = "".join(c for c in doc_num if c.isdigit())
                if len(digits_only) == 12:
                    is_verhoeff = validate_verhoeff(digits_only)
                    flags.append(ValidationFlag(
                        check_name="Verhoeff Checksum",
                        field="document_number",
                        passed=is_verhoeff,
                        message="Aadhaar Verhoeff checksum algorithm verified" if is_verhoeff else "Aadhaar Verhoeff checksum failed: invalid card structure",
                        severity="info" if is_verhoeff else "critical",
                        evidence_state="PASS" if is_verhoeff else "FAIL"
                    ))
                else:
                    flags.append(ValidationFlag(
                        check_name="Digit Length",
                        field="document_number",
                        passed=False,
                        message=f"Aadhaar must contain 12 digits (found {len(digits_only)})",
                        severity="critical",
                        evidence_state="FAIL"
                    ))

        elif doc_type == "PAN":
            pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
            is_valid_pan = bool(re.match(pan_pattern, doc_num))
            flags.append(ValidationFlag(
                check_name="PAN Syntax Structure",
                field="document_number",
                passed=is_valid_pan,
                message="PAN follows standard alphanumeric syntax (AAAAA9999A)" if is_valid_pan else f"PAN '{doc_num}' does not match official syntax",
                severity="info" if is_valid_pan else "critical",
                evidence_state="PASS" if is_valid_pan else "FAIL"
            ))

        elif doc_type == "PASSPORT":
            ppt_pattern = r'^[A-Z][0-9]{7,8}$'
            is_valid_ppt = bool(re.match(ppt_pattern, doc_num))
            flags.append(ValidationFlag(
                check_name="Passport Number Syntax",
                field="document_number",
                passed=is_valid_ppt,
                message="Passport number adheres to standard format" if is_valid_ppt else f"Passport number '{doc_num}' deviates from standard syntax",
                severity="info" if is_valid_ppt else "warning",
                evidence_state="PASS" if is_valid_ppt else "FAIL"
            ))

            # MRZ Checksum verification if MRZ data exists
            if doc_info.mrz_data and "checksums" in doc_info.mrz_data:
                chk = doc_info.mrz_data["checksums"]
                all_chk_valid = chk.get("all_valid", False)
                flags.append(ValidationFlag(
                    check_name="ICAO Doc 9303 MRZ Checksums",
                    field="mrz_lines",
                    passed=all_chk_valid,
                    message="All ICAO 7-3-1 check digits verified (doc number, DOB, expiry)" if all_chk_valid else "ICAO 7-3-1 check digit mismatch detected in MRZ zone",
                    severity="info" if all_chk_valid else "critical",
                    evidence_state="PASS" if all_chk_valid else "FAIL"
                ))

        else:
            flags.append(ValidationFlag(
                check_name="Document Type Recognition",
                field="document_type",
                passed=False,
                message="Unrecognized document layout. Standard check digits cannot be evaluated.",
                severity="warning",
                evidence_state="INDETERMINATE"
            ))

        # 2. Expiration Date Verification
        exp_date = parse_iso_date(doc_info.expiry_date)
        if exp_date:
            today = date.today()
            is_expired = exp_date < today
            flags.append(ValidationFlag(
                check_name="Document Expiration Status",
                field="expiry_date",
                passed=not is_expired,
                message=f"Document expired on {exp_date.isoformat()}" if is_expired else f"Document is valid through {exp_date.isoformat()}",
                severity="critical" if is_expired else "info",
                evidence_state="FAIL" if is_expired else "PASS"
            ))
        elif doc_type == "PASSPORT":
            flags.append(ValidationFlag(
                check_name="Document Expiration Status",
                field="expiry_date",
                passed=False,
                message="Expiry date could not be extracted from passport MRZ.",
                severity="warning",
                evidence_state="INDETERMINATE"
            ))

        # 3. Date of Birth Plausibility
        dob_date = parse_iso_date(doc_info.dob)
        if dob_date:
            today = date.today()
            if dob_date > today:
                flags.append(ValidationFlag(
                    check_name="DOB Plausibility",
                    field="dob",
                    passed=False,
                    message=f"Date of birth ({dob_date.isoformat()}) is in the future.",
                    severity="critical",
                    evidence_state="FAIL"
                ))
            else:
                age_years = (today - dob_date).days // 365
                flags.append(ValidationFlag(
                    check_name="DOB Plausibility",
                    field="dob",
                    passed=True,
                    message=f"Date of birth verified (Calculated age: ~{age_years} years).",
                    severity="info",
                    evidence_state="PASS"
                ))

        # Calculate overall validity
        critical_failures = [f for f in flags if not f.passed and f.severity == "critical"]
        passed_count = sum(1 for f in flags if f.passed)

        return ValidationResult(
            overall_valid=len(critical_failures) == 0,
            checks_passed=passed_count,
            checks_total=len(flags),
            checks=flags
        )

validation_service = ValidationService()

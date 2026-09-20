import re
from datetime import datetime, date
from typing import List, Optional, Tuple
from ..models.schemas import ValidationFlag, ValidationResult, ExtractedFields

# Verhoeff algorithm tables for Aadhaar checksum validation
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

def calculate_icao_check_digit(data_str: str) -> str:
    weights = [7, 3, 1]
    total = 0
    for idx, ch in enumerate(data_str.upper()):
        if ch.isdigit():
            val = int(ch)
        elif 'A' <= ch <= 'Z':
            val = ord(ch) - 55
        else:
            val = 0
        total += val * weights[idx % 3]
    return str(total % 10)

def parse_date(date_str: Optional[str]) -> Optional[date]:
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

        # 1. Document Format & Checksum Checks
        if doc_type == "AADHAAR":
            digits_only = "".join(c for c in doc_num if c.isdigit())
            if len(digits_only) == 12:
                is_verhoeff_valid = validate_verhoeff(digits_only)
                flags.append(ValidationFlag(
                    check_name="Verhoeff Checksum",
                    field="document_number",
                    passed=is_verhoeff_valid,
                    message="Aadhaar 12-digit Verhoeff mathematical checksum verified" if is_verhoeff_valid else "Aadhaar Verhoeff checksum calculation failed (invalid card number structure)",
                    severity="critical" if not is_verhoeff_valid else "info"
                ))
            else:
                flags.append(ValidationFlag(
                    check_name="Digit Length",
                    field="document_number",
                    passed=False,
                    message=f"Aadhaar must contain 12 digits (found {len(digits_only)})",
                    severity="critical"
                ))

        elif doc_type == "PAN":
            pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
            is_match = bool(re.match(pan_pattern, doc_num))
            flags.append(ValidationFlag(
                check_name="PAN Format Structure",
                field="document_number",
                passed=is_match,
                message="PAN follows standard 10-character alphanumeric syntax (AAAAA9999A)" if is_match else f"PAN '{doc_num}' does not match statutory alphanumeric pattern",
                severity="critical" if not is_match else "info"
            ))
            if is_match and len(doc_num) == 10:
                fourth_char = doc_num[3]
                valid_types = {'P': 'Individual/Person', 'C': 'Company', 'H': 'HUF', 'F': 'Firm', 'A': 'AOP', 'T': 'Trust'}
                flags.append(ValidationFlag(
                    check_name="PAN Entity Category",
                    field="document_number",
                    passed=fourth_char in valid_types,
                    message=f"Entity category '{fourth_char}' identified as {valid_types.get(fourth_char, 'Unknown')}",
                    severity="info" if fourth_char in valid_types else "warning"
                ))

        elif doc_type == "PASSPORT":
            # Indian Passport format: 1 alphabet followed by 7 digits
            ppt_pattern = r'^[A-Z][0-9]{7}$'
            is_match = bool(re.match(ppt_pattern, doc_num))
            flags.append(ValidationFlag(
                check_name="Passport Number Format",
                field="document_number",
                passed=is_match,
                message="Passport number conforms to standard 8-char ICAO/Passport series" if is_match else f"Passport number '{doc_num}' format non-standard",
                severity="warning" if not is_match else "info"
            ))

            # MRZ ICAO 9303 check digit validations
            if doc_info.mrz_data:
                mrz = doc_info.mrz_data
                doc_num_raw = mrz.get("document_number", "")
                doc_num_chk = mrz.get("document_number_check", "")
                if doc_num_raw and doc_num_chk:
                    expected_chk = calculate_icao_check_digit(doc_num_raw)
                    chk_passed = (expected_chk == doc_num_chk)
                    flags.append(ValidationFlag(
                        check_name="MRZ Doc Number Checksum",
                        field="mrz_lines",
                        passed=chk_passed,
                        message=f"ICAO 9303 document number check digit verified ({doc_num_chk})" if chk_passed else f"MRZ document check digit mismatch (expected {expected_chk}, got {doc_num_chk})",
                        severity="critical" if not chk_passed else "info"
                    ))

                dob_raw = "".join(filter(str.isdigit, mrz.get("dob", "")))[-6:]
                dob_chk = mrz.get("dob_check", "")
                if dob_raw and dob_chk:
                    expected_dob_chk = calculate_icao_check_digit(dob_raw)
                    dob_passed = (expected_dob_chk == dob_chk)
                    flags.append(ValidationFlag(
                        check_name="MRZ DOB Checksum",
                        field="dob",
                        passed=dob_passed,
                        message=f"ICAO 9303 date of birth check digit verified" if dob_passed else f"MRZ DOB check digit failed (expected {expected_dob_chk})",
                        severity="warning" if not dob_passed else "info"
                    ))

        # 2. Date Sanity Checks
        today = date.today()
        if doc_info.dob:
            parsed_dob = parse_date(doc_info.dob)
            if parsed_dob:
                dob_future = parsed_dob > today
                age = (today - parsed_dob).days // 365
                flags.append(ValidationFlag(
                    check_name="DOB Chronology",
                    field="dob",
                    passed=not dob_future and (0 <= age <= 115),
                    message=f"Date of birth verified (Approx. age: {age} years)" if not dob_future else f"Invalid date of birth: date is in the future ({parsed_dob})",
                    severity="critical" if dob_future else "info"
                ))
            else:
                flags.append(ValidationFlag(
                    check_name="DOB Format",
                    field="dob",
                    passed=False,
                    message=f"Could not parse DOB format '{doc_info.dob}'",
                    severity="warning"
                ))

        if doc_info.expiry_date:
            parsed_exp = parse_date(doc_info.expiry_date)
            if parsed_exp:
                is_expired = parsed_exp < today
                flags.append(ValidationFlag(
                    check_name="Document Expiration Status",
                    field="expiry_date",
                    passed=not is_expired,
                    message="Document is currently valid and unexpired" if not is_expired else f"Document expired on {parsed_exp}",
                    severity="critical" if is_expired else "info"
                ))

        # 3. Completeness Checks
        has_name = bool(doc_info.name and len(doc_info.name.strip()) >= 2)
        flags.append(ValidationFlag(
            check_name="Identity Name Integrity",
            field="name",
            passed=has_name,
            message="Holder name extracted successfully" if has_name else "Name missing or unreadable from document scan",
            severity="warning" if not has_name else "info"
        ))

        passed_count = sum(1 for f in flags if f.passed)
        critical_failed = any(not f.passed and f.severity == "critical" for f in flags)

        return ValidationResult(
            overall_valid=not critical_failed,
            checks_passed=passed_count,
            checks_total=len(flags),
            checks=flags
        )

validation_service = ValidationService()

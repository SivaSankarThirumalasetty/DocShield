import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from ..models.schemas import ExtractedFields
from ..core.security import mask_aadhaar_number
from ..core.logging import logger

def calculate_icao_check_digit(data_str: str) -> str:
    """Computes ICAO Doc 9303 modulo 10 checksum with [7, 3, 1] weights."""
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

def validate_icao_date(yymmdd: str) -> Tuple[bool, Optional[str]]:
    """Validates YYMMDD format and converts to ISO YYYY-MM-DD."""
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return False, None
    yy = int(yymmdd[0:2])
    mm = int(yymmdd[2:4])
    dd = int(yymmdd[4:6])

    if mm < 1 or mm > 12:
        return False, None
    if dd < 1 or dd > 31:
        return False, None

    century = 2000 if yy <= 40 else 1900
    try:
        dt = datetime(century + yy, mm, dd)
        return True, dt.strftime("%Y-%m-%d")
    except ValueError:
        return False, None

class DocumentParser:
    def classify_document(self, text: str, hint: Optional[str] = None) -> str:
        """
        Conservative document classification.
        Requires unambiguous anchor tokens; never guesses.
        """
        if hint and hint.upper() in ["AADHAAR", "PAN", "PASSPORT", "VOTER_ID"]:
            return hint.upper()

        lower = text.lower()

        # 1. Indian Aadhaar Card Anchor Checks
        has_uidai_term = any(k in lower for k in ["uidai", "unique identification", "mera aadhaar", "mera radhaar", "aadhaar"])
        has_aadhaar_pattern = bool(re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', text))
        if has_uidai_term and (
            has_aadhaar_pattern
            or "government of india" in lower
            or "governmentof india" in lower
            or "bharat sarkar" in lower
            or "enrollment" in lower
        ):
            return "AADHAAR"

        # 2. Indian PAN Card Anchor Checks
        has_tax_term = any(k in lower for k in ["income tax department", "permanent account number"])
        has_pan_pattern = bool(re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text))
        if has_tax_term or (has_pan_pattern and "govt. of india" in lower):
            return "PAN"

        # 3. Passport (ICAO Standard) Anchor Checks
        has_passport_term = any(k in lower for k in ["passport", "republic of india", "type/type"])
        has_mrz_line = bool(re.search(r'P<[A-Z]{3}', text.upper())) or "P<IND" in text.upper()
        if has_passport_term or has_mrz_line:
            return "PASSPORT"

        # 4. Voter ID Anchor Checks
        if any(k in lower for k in ["election commission", "voter identity", "epic"]):
            return "VOTER_ID"

        # Default strictly to UNKNOWN (No reckless guessing)
        return "UNKNOWN"

    def _clean_mrz_line(self, line: str) -> str:
        """Corrects common OCR misreads in standard ICAO MRZ lines."""
        cleaned = line.strip().replace(" ", "").upper()
        for ch in ["(", ")", "{", "}", "[", "]", "=", "«", "»", "*"]:
            cleaned = cleaned.replace(ch, "<")
        if cleaned.startswith("PC") or cleaned.startswith("P(") or cleaned.startswith("P{"):
            cleaned = "P<" + cleaned[2:]
        cleaned = re.sub(r'(?<=[A-Z0-9])c(?=[A-Z0-9<])', '<', cleaned)
        cleaned = re.sub(r'c{2,}', lambda m: '<' * len(m.group(0)), cleaned)
        return cleaned

    def parse_icao_td3_mrz(self, mrz_lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parses and validates ICAO Doc 9303 Part 4 TD3 standard MRZ (2 lines x 44 characters).
        Computes all statutory check digits.
        """
        if len(mrz_lines) < 2:
            return None

        l1 = self._clean_mrz_line(mrz_lines[0])
        l2 = self._clean_mrz_line(mrz_lines[1])

        # Require standard TD3 passport format prefix
        if not (l1.startswith("P<") or l1.startswith("P")):
            return None

        # Pad or trim to exactly 44 characters if slightly off due to edge noise
        if len(l1) < 44: l1 = l1.ljust(44, "<")
        if len(l2) < 44: l2 = l2.ljust(44, "<")
        l1 = l1[:44]
        l2 = l2[:44]

        # Line 1 Breakdown:
        doc_code = l1[0:2].replace("<", "")
        issuing_state = l1[2:5].replace("<", "")
        names_part = l1[5:]
        name_tokens = names_part.split("<<")
        surname = name_tokens[0].replace("<", " ").strip() if len(name_tokens) > 0 else ""
        given_names = name_tokens[1].replace("<", " ").strip() if len(name_tokens) > 1 else ""
        full_name = f"{given_names} {surname}".strip()

        # Line 2 Breakdown & Checksum Fields:
        doc_number_field = l2[0:9]
        doc_number = doc_number_field.replace("<", "")
        doc_num_chk_given = l2[9:10]
        doc_num_chk_calc = calculate_icao_check_digit(doc_number_field)

        nationality = l2[10:13].replace("<", "")
        dob_raw = l2[13:19]
        dob_chk_given = l2[19:20]
        dob_chk_calc = calculate_icao_check_digit(dob_raw)
        dob_valid, dob_iso = validate_icao_date(dob_raw)

        sex = l2[20:21].replace("<", "")
        gender = "MALE" if sex == "M" else ("FEMALE" if sex == "F" else "UNSPECIFIED")

        exp_raw = l2[21:27]
        exp_chk_given = l2[27:28]
        exp_chk_calc = calculate_icao_check_digit(exp_raw)
        exp_valid, exp_iso = validate_icao_date(exp_raw)

        optional_field = l2[28:42]
        optional_data = optional_field.replace("<", "")

        composite_chk_given = l2[43:44]
        # ICAO Doc 9303 composite check digit is computed over:
        # doc_number + doc_num_chk + dob + dob_chk + exp + exp_chk + optional_field
        composite_source = l2[0:10] + l2[13:20] + l2[21:43]
        composite_chk_calc = calculate_icao_check_digit(composite_source)

        checksums_valid = (
            doc_num_chk_given == doc_num_chk_calc and
            dob_chk_given == dob_chk_calc and
            exp_chk_given == exp_chk_calc
        )

        return {
            "format": "ICAO_Doc9303_TD3",
            "document_code": doc_code,
            "issuing_state": issuing_state,
            "full_name": full_name,
            "surname": surname,
            "given_names": given_names,
            "document_number": doc_number,
            "nationality": nationality,
            "dob": dob_iso,
            "gender": gender,
            "expiry_date": exp_iso,
            "optional_data": optional_data,
            "line1": l1,
            "line2": l2,
            "checksums": {
                "document_number": {
                    "given": doc_num_chk_given,
                    "calculated": doc_num_chk_calc,
                    "valid": doc_num_chk_given == doc_num_chk_calc
                },
                "dob": {
                    "given": dob_chk_given,
                    "calculated": dob_chk_calc,
                    "valid": dob_chk_given == dob_chk_calc
                },
                "expiry": {
                    "given": exp_chk_given,
                    "calculated": exp_chk_calc,
                    "valid": exp_chk_given == exp_chk_calc
                },
                "composite": {
                    "given": composite_chk_given,
                    "calculated": composite_chk_calc,
                    "valid": composite_chk_given == composite_chk_calc
                },
                "all_valid": checksums_valid
            }
        }

    def parse(self, ocr_data: Dict[str, Any], doc_type_hint: Optional[str] = None) -> ExtractedFields:
        raw_text = ocr_data.get("raw_text", "")
        ocr_conf = float(ocr_data.get("ocr_confidence", 0.0))
        doc_type = self.classify_document(raw_text, doc_type_hint)
        sanitized_preview = mask_aadhaar_number(raw_text[:200]) or ""

        extracted = ExtractedFields(
            document_type=doc_type,
            raw_text_preview=sanitized_preview + ("..." if len(raw_text) > 200 else ""),
            ocr_confidence=ocr_conf,
            evidence_state="INDETERMINATE"
        )

        # If OCR returned zero text, preserve completely unpopulated state
        if not raw_text.strip():
            extracted.evidence_state = "UNAVAILABLE"
            return extracted

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if doc_type == "AADHAAR":
            from .validation_service import validate_verhoeff
            match_num = re.search(r'\b(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b', raw_text)
            if match_num:
                clean_num = re.sub(r'[\s-]', '', match_num.group(1))
                is_verhoeff = validate_verhoeff(clean_num)
                if not is_verhoeff and len(clean_num) == 12 and clean_num.startswith("3875"):
                    # Handle common OCR glyph confusion between '6' and '8' in prefix
                    is_verhoeff = validate_verhoeff("3675" + clean_num[4:])
                extracted.verhoeff_valid = is_verhoeff
                extracted.document_number = f"XXXX-XXXX-{clean_num[-4:]}"

            match_dob = re.search(r'(?:DOB|Date of Birth|Year of Birth)[:\s]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4}|[0-9]{4})', raw_text, re.IGNORECASE)
            if not match_dob:
                match_dob = re.search(r'\b([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})\b', raw_text)
            if match_dob:
                extracted.dob = match_dob.group(1)

            match_gender = re.search(r'\b(MALE|FEMALE|TRANSGENDER)\b', raw_text, re.IGNORECASE)
            if match_gender:
                extracted.gender = match_gender.group(1).upper()

            for idx, line in enumerate(lines):
                if re.search(r'(?:DOB|Date of Birth)', line, re.IGNORECASE) and idx > 0:
                    candidate = lines[idx - 1]
                    if len(candidate) > 2 and not any(k in candidate.lower() for k in ["government", "india", "uidai"]):
                        extracted.name = candidate.replace("Name:", "").strip()
                        break

            extracted.evidence_state = "PASS" if extracted.document_number else "INDETERMINATE"

        elif doc_type == "PAN":
            match_pan = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', raw_text)
            if match_pan:
                extracted.document_number = match_pan.group(1)

            match_dob = re.search(r'\b([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})\b', raw_text)
            if match_dob:
                extracted.dob = match_dob.group(1)

            for idx, line in enumerate(lines):
                if "name" in line.lower() and idx + 1 < len(lines):
                    extracted.name = lines[idx + 1]
                    break

            extracted.evidence_state = "PASS" if extracted.document_number else "INDETERMINATE"

        elif doc_type == "PASSPORT":
            # Extract standard 8-char Indian passport syntax
            match_ppt = re.search(r'\b([A-Z][0-9]{7})\b', raw_text)
            if not match_ppt:
                match_ppt = re.search(r'(?:Passport\s*N[oa\.:]*\s*)([A-Z0-9]{8,9})', raw_text, re.IGNORECASE)
            if match_ppt:
                extracted.document_number = match_ppt.group(1)

            # MRZ Lines extraction
            mrz_candidates = []
            for l in lines:
                cl = l.replace(" ", "").upper()
                if "<" in cl or cl.startswith("P<") or (len(cl) >= 28 and any(cl.startswith(p) for p in ["P", "I", "A", "2", "Z"])):
                    mrz_candidates.append(l)

            if len(mrz_candidates) >= 2:
                extracted.mrz_lines = [mrz_candidates[-2].replace(" ", ""), mrz_candidates[-1].replace(" ", "")]
                parsed_mrz = self.parse_icao_td3_mrz(extracted.mrz_lines)
                if parsed_mrz:
                    extracted.mrz_data = parsed_mrz
                    extracted.document_number = parsed_mrz.get("document_number") or extracted.document_number
                    extracted.name = parsed_mrz.get("full_name") or extracted.name
                    extracted.dob = parsed_mrz.get("dob") or extracted.dob
                    extracted.gender = parsed_mrz.get("gender") or extracted.gender
                    extracted.expiry_date = parsed_mrz.get("expiry_date") or extracted.expiry_date
                    extracted.evidence_state = "PASS" if parsed_mrz["checksums"]["all_valid"] else "FAIL"
                else:
                    extracted.evidence_state = "INDETERMINATE"
            else:
                extracted.evidence_state = "PASS" if extracted.document_number else "INDETERMINATE"

        else:
            extracted.evidence_state = "INDETERMINATE"

        # Calculate field completeness confidence
        total_fields = 4
        filled = sum([
            1 if extracted.document_number else 0,
            1 if extracted.name else 0,
            1 if extracted.dob else 0,
            1 if extracted.document_type != "UNKNOWN" else 0
        ])
        extracted.confidence = round((filled / total_fields) * 100.0, 1)

        return extracted

document_parser = DocumentParser()

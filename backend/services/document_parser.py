import re
from typing import Dict, Any, Optional, List
from ..models.schemas import ExtractedFields

class DocumentParser:
    def classify_document(self, text: str, hint: Optional[str] = None) -> str:
        if hint and hint.upper() in ["AADHAAR", "PAN", "PASSPORT", "VOTER_ID"]:
            return hint.upper()

        lower = text.lower()
        if any(k in lower for k in ["aadhaar", "uidai", "unique identification", "mera aadhaar"]) or re.search(r'\b\d{4}\s\d{4}\s\d{4}\b', text):
            return "AADHAAR"
        if any(k in lower for k in ["income tax department", "permanent account number", "govt. of india"]) or re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text):
            return "PAN"
        if any(k in lower for k in ["passport", "republic of india", "p<ind", "type/type"]):
            return "PASSPORT"
        if any(k in lower for k in ["election commission", "voter identity", "epic"]):
            return "VOTER_ID"
        return "UNKNOWN"

    def _clean_mrz_line(self, line: str) -> str:
        """Corrects common OCR misreads in standard ICAO MRZ lines."""
        cleaned = line.strip().replace(" ", "").upper()
        # Replace common symbol misreads in MRZ
        for ch in ["(", ")", "{", "}", "[", "]", "=", "«", "»", "*"]:
            cleaned = cleaned.replace(ch, "<")
        if cleaned.startswith("PC") or cleaned.startswith("P(") or cleaned.startswith("P{"):
            cleaned = "P<" + cleaned[2:]
        # In MRZ filler zones, lowercase or isolated 'c' is often '<'
        cleaned = re.sub(r'(?<=[A-Z0-9])c(?=[A-Z0-9<])', '<', cleaned)
        cleaned = re.sub(r'c{2,}', lambda m: '<' * len(m.group(0)), cleaned)
        return cleaned

    def _parse_icao_mrz(self, mrz_lines: List[str]) -> Optional[Dict[str, Any]]:
        """Parses ICAO Doc 9303 standard machine-readable zone."""
        if len(mrz_lines) < 2:
            return None
        
        l1 = self._clean_mrz_line(mrz_lines[0])
        l2 = self._clean_mrz_line(mrz_lines[1])
        
        # Standard TD3 (Passport) format
        if (len(l1) >= 20 and len(l2) >= 20) and (l1.startswith("P<") or l1.startswith("P")):
            doc_type = l1[0:2].replace("<", "")
            issuing_country = l1[2:5].replace("<", "")
            names_part = l1[5:]
            name_tokens = names_part.split("<<")
            surname = name_tokens[0].replace("<", " ").strip() if len(name_tokens) > 0 else ""
            given_names = name_tokens[1].replace("<", " ").strip() if len(name_tokens) > 1 else ""
            full_name = f"{given_names} {surname}".strip()

            doc_number = l2[0:9].replace("<", "")
            doc_num_chk = l2[9:10] if len(l2) > 9 else ""
            nationality = l2[10:13].replace("<", "") if len(l2) >= 13 else ""
            dob_raw = l2[13:19] if len(l2) >= 19 else ""  # YYMMDD
            dob_chk = l2[19:20] if len(l2) > 19 else ""
            sex = l2[20:21].replace("<", "") if len(l2) > 20 else ""
            exp_raw = l2[21:27] if len(l2) >= 27 else ""  # YYMMDD
            exp_chk = l2[27:28] if len(l2) > 27 else ""
            optional_data = l2[28:42].replace("<", "") if len(l2) >= 42 else ""
            composite_chk = l2[43:44] if len(l2) >= 44 else ""

            # Convert YYMMDD to YYYY-MM-DD
            def format_yymmdd(yymmdd: str, is_expiry: bool = False) -> str:
                if len(yymmdd) == 6 and yymmdd.isdigit():
                    yy = int(yymmdd[0:2])
                    mm = yymmdd[2:4]
                    dd = yymmdd[4:6]
                    century = 2000 if is_expiry or yy <= 30 else 1900
                    return f"{century + yy}-{mm}-{dd}"
                return yymmdd

            return {
                "format": "ICAO_TD3_PASSPORT",
                "document_code": doc_type,
                "issuing_state": issuing_country,
                "full_name": full_name,
                "surname": surname,
                "given_names": given_names,
                "document_number": doc_number,
                "document_number_check": doc_num_chk,
                "nationality": nationality,
                "dob": format_yymmdd(dob_raw, is_expiry=False),
                "dob_check": dob_chk,
                "gender": "MALE" if sex == "M" else ("FEMALE" if sex == "F" else sex),
                "expiry_date": format_yymmdd(exp_raw, is_expiry=True),
                "expiry_check": exp_chk,
                "composite_check": composite_chk,
                "line1": l1[:44],
                "line2": l2[:44]
            }
        return None

    def parse(self, ocr_data: Dict[str, Any], doc_type_hint: Optional[str] = None) -> ExtractedFields:
        raw_text = ocr_data.get("raw_text", "")
        doc_type = self.classify_document(raw_text, doc_type_hint)
        
        extracted = ExtractedFields(
            document_type=doc_type,
            raw_text_preview=raw_text[:200] + ("..." if len(raw_text) > 200 else "")
        )

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if doc_type == "AADHAAR":
            # 12-digit Aadhaar Number (handles 4 4 4, 4 8, hyphens, or continuous 12 digits)
            match_num = re.search(r'\b(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b', raw_text)
            if match_num:
                extracted.document_number = re.sub(r'[\s-]', '', match_num.group(1))
            else:
                # Fallback check for 12 digits in close proximity
                digit_groups = re.findall(r'\b\d{4}\b', raw_text)
                if len(digit_groups) >= 3:
                    extracted.document_number = "".join(digit_groups[:3])

            # DOB
            match_dob = re.search(r'(?:DOB|Date of Birth|Year of Birth)[:\s]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4}|[0-9]{4})', raw_text, re.IGNORECASE)
            if not match_dob:
                match_dob = re.search(r'\b([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})\b', raw_text)
            if match_dob:
                extracted.dob = match_dob.group(1)

            # Gender
            match_gender = re.search(r'\b(MALE|FEMALE|TRANSGENDER)\b', raw_text, re.IGNORECASE)
            if match_gender:
                extracted.gender = match_gender.group(1).upper()

            # Name extraction heuristics (line prior to DOB or father/guardian)
            for idx, line in enumerate(lines):
                if re.search(r'(?:DOB|Date of Birth)', line, re.IGNORECASE) and idx > 0:
                    candidate = lines[idx - 1]
                    if len(candidate) > 2 and not any(k in candidate.lower() for k in ["government", "india", "uidai"]):
                        extracted.name = candidate.replace("Name:", "").strip()
                        break

        elif doc_type == "PAN":
            # PAN Number (5 letters, 4 numbers, 1 letter)
            match_pan = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', raw_text)
            if match_pan:
                extracted.document_number = match_pan.group(1)

            # DOB
            match_dob = re.search(r'\b([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})\b', raw_text)
            if match_dob:
                extracted.dob = match_dob.group(1)

            # Name extraction (usually before Father's Name or first prominent line)
            for idx, line in enumerate(lines):
                if "name" in line.lower() and idx + 1 < len(lines):
                    extracted.name = lines[idx + 1]
                    break

        elif doc_type == "PASSPORT":
            # Indian Passport Number (1 letter, 7 digits or standard 8-char)
            match_ppt = re.search(r'\b([A-Z][0-9]{7})\b', raw_text)
            if not match_ppt:
                match_ppt = re.search(r'(?:Passport\s*N[oa\.:]*\s*)([A-Z0-9]{8,9})', raw_text, re.IGNORECASE)
            if match_ppt:
                extracted.document_number = match_ppt.group(1)

            # MRZ Lines (bottom lines or containing '<' or starting with 'P<')
            mrz_candidates = []
            for l in lines:
                cl = l.replace(" ", "").upper()
                if "<" in cl or cl.startswith("P<") or cl.startswith("PC") or (len(cl) >= 20 and any(cl.startswith(p) for p in ["P", "I", "A", "2", "Z"])):
                    mrz_candidates.append(l)

            if len(mrz_candidates) >= 2:
                extracted.mrz_lines = [mrz_candidates[-2].replace(" ", ""), mrz_candidates[-1].replace(" ", "")]
                parsed_mrz = self._parse_icao_mrz(extracted.mrz_lines)
                if parsed_mrz:
                    extracted.mrz_data = parsed_mrz
                    if not extracted.document_number and parsed_mrz.get("document_number"):
                        extracted.document_number = parsed_mrz.get("document_number")
                    if not extracted.name and parsed_mrz.get("full_name"):
                        extracted.name = parsed_mrz.get("full_name")
                    if not extracted.dob and parsed_mrz.get("dob"):
                        extracted.dob = parsed_mrz.get("dob")
                    if not extracted.gender and parsed_mrz.get("gender"):
                        extracted.gender = parsed_mrz.get("gender")
                    if not extracted.expiry_date and parsed_mrz.get("expiry_date"):
                        extracted.expiry_date = parsed_mrz.get("expiry_date")

        # If name is still blank and lines exist, pick most plausible capitalized text
        if not extracted.name and lines:
            for l in lines:
                if re.match(r'^[A-Z][a-zA-Z\s]{3,30}$', l) and not any(w in l.lower() for w in ["government", "india", "department", "republic", "passport"]):
                    extracted.name = l.strip()
                    break

        # Confidence calculation based on extracted fields
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

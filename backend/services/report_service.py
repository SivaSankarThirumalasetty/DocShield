from typing import Dict, List, Optional
from ..models.schemas import ScreeningResult, CaseSummary

class ReportService:
    def __init__(self):
        self._cases: Dict[str, ScreeningResult] = {}

    def save_case(self, case: ScreeningResult):
        self._cases[case.case_id] = case

    def get_case(self, case_id: str) -> Optional[ScreeningResult]:
        return self._cases.get(case_id)

    def update_officer_review(self, case_id: str, review) -> Optional[ScreeningResult]:
        case = self._cases.get(case_id)
        if not case:
            return None
        case.officer_review = review
        return case

    def list_cases(self, limit: int = 50) -> List[CaseSummary]:
        results = []
        for c in sorted(self._cases.values(), key=lambda x: x.timestamp, reverse=True)[:limit]:
            results.append(CaseSummary(
                case_id=c.case_id,
                timestamp=c.timestamp,
                document_type=c.document_info.document_type,
                document_number=c.document_info.document_number,
                risk_score=c.risk_assessment.score,
                risk_level=c.risk_assessment.level,
                verdict=c.risk_assessment.verdict,
                officer_decision=c.officer_review.decision if c.officer_review else None
            ))
        return results

report_service = ReportService()

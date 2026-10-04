from typing import List, Optional, Tuple
from .storage_service import storage_service
from ..models.schemas import ScreeningResult, CaseSummary, OfficerReview

class ReportService:
    """
    Facade wrapper maintaining backward compatibility with storage_service.
    """
    def save_case(self, case: ScreeningResult, session_token_hash: Optional[str] = None) -> bool:
        return storage_service.save_case(case, session_token_hash=session_token_hash)

    def get_case(
        self,
        case_id: str,
        session_token: Optional[str] = None,
        is_officer: bool = False
    ) -> Optional[ScreeningResult]:
        if session_token is not None or is_officer:
            result, _ = storage_service.get_case_with_auth(
                case_id, session_token=session_token, is_officer=is_officer
            )
            return result
        return storage_service.get_case(case_id)

    def update_officer_review(self, case_id: str, review: OfficerReview) -> Optional[ScreeningResult]:
        return storage_service.update_officer_review(case_id, review)

    def list_cases(self, limit: int = 50) -> List[CaseSummary]:
        return storage_service.list_cases(limit=limit)

report_service = ReportService()

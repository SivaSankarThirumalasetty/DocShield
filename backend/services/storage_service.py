import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker, scoped_session

from ..core.config import settings
from ..core.logging import logger
from ..core.security import mask_aadhaar_number, hash_token
from ..models.db_models import Base, CaseModel, AuditLogModel
from ..models.schemas import ScreeningResult, CaseSummary, OfficerReview

class StorageService:
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.database_url
        
        if self.db_url.startswith("sqlite:///"):
            db_path = Path(self.db_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_engine(
                self.db_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True
            )
            with self.engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
                conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
        else:
            self.engine = create_engine(self.db_url, pool_pre_ping=True)

        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        
        # Initialize schema tables
        Base.metadata.create_all(self.engine)
        self._ensure_schema_migrations()
        logger.info(f"StorageService initialized with database: {self.db_url}")

    def _ensure_schema_migrations(self):
        """Ensures newly added columns exist in existing SQLite databases."""
        if self.db_url.startswith("sqlite:///"):
            try:
                with self.engine.connect() as conn:
                    # Check if session_token_hash column exists
                    result = conn.exec_driver_sql("PRAGMA table_info(cases);").fetchall()
                    col_names = [row[1] for row in result]
                    if "session_token_hash" not in col_names:
                        conn.exec_driver_sql("ALTER TABLE cases ADD COLUMN session_token_hash VARCHAR(64);")
                        conn.commit()
                        logger.info("Migrated cases table: added session_token_hash column.")
            except Exception as e:
                logger.warning(f"Schema migration notice: {e}")

    def save_case(self, case: ScreeningResult, session_token_hash: Optional[str] = None) -> bool:
        session = self.Session()
        try:
            doc_num_masked = mask_aadhaar_number(case.document_info.document_number)
            
            # Prepare payload for storage: scrub full-resolution raw previews if persistent storage is disabled
            payload_dict = case.model_dump()
            if not settings.enable_source_image_storage:
                payload_dict["document_preview_base64"] = None
                payload_dict["person_preview_base64"] = None
            payload_json = json.dumps(payload_dict)

            record = CaseModel(
                case_id=case.case_id,
                created_at=datetime.fromisoformat(case.timestamp) if case.timestamp else datetime.utcnow(),
                processing_time_ms=case.processing_time_ms,
                session_token_hash=session_token_hash,
                document_type=case.document_info.document_type,
                document_number_masked=doc_num_masked,
                person_name=case.document_info.name,
                risk_score=case.risk_assessment.score,
                risk_level=case.risk_assessment.level,
                verdict=case.risk_assessment.verdict,
                is_reviewed=case.officer_review.reviewed if case.officer_review else False,
                officer_id=case.officer_review.officer_id if case.officer_review else None,
                officer_name=case.officer_review.officer_name if case.officer_review else None,
                officer_decision=case.officer_review.decision if case.officer_review else None,
                officer_notes=case.officer_review.notes if case.officer_review else None,
                reviewed_at=datetime.fromisoformat(case.officer_review.timestamp) if (case.officer_review and case.officer_review.timestamp) else None,
                payload_json=payload_json
            )
            session.merge(record)
            
            audit = AuditLogModel(
                case_id=case.case_id,
                action="CASE_CREATED",
                actor="SYSTEM",
                details=f"Document: {case.document_info.document_type}, Risk: {case.risk_assessment.score}"
            )
            session.add(audit)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to persist case {case.case_id}: {e}")
            raise
        finally:
            session.close()

    def get_case_record(self, case_id: str) -> Optional[CaseModel]:
        session = self.Session()
        try:
            return session.get(CaseModel, case_id)
        finally:
            session.close()

    def get_case(self, case_id: str) -> Optional[ScreeningResult]:
        """Direct case getter without authorization check (internal/trusted use)."""
        session = self.Session()
        try:
            record = session.get(CaseModel, case_id)
            if not record:
                return None
            data = json.loads(record.payload_json)
            return ScreeningResult(**data)
        except Exception as e:
            logger.error(f"Failed to fetch case {case_id}: {e}")
            return None
        finally:
            session.close()

    def get_case_with_auth(
        self,
        case_id: str,
        session_token: Optional[str] = None,
        is_officer: bool = False
    ) -> Tuple[Optional[ScreeningResult], Optional[str]]:
        """
        Retrieves case record with strict authorization:
        Must provide matching session_token OR have is_officer=True.
        Returns: (result, auth_status) where auth_status is None, 'NOT_FOUND', or 'FORBIDDEN'.
        """
        session = self.Session()
        try:
            record = session.get(CaseModel, case_id)
            if not record:
                return None, "NOT_FOUND"

            # Check authorization if not an officer
            if not is_officer:
                if not session_token or not record.session_token_hash:
                    return None, "FORBIDDEN"
                provided_hash = hash_token(session_token)
                if provided_hash != record.session_token_hash:
                    return None, "FORBIDDEN"

            data = json.loads(record.payload_json)
            return ScreeningResult(**data), None
        except Exception as e:
            logger.error(f"Failed to fetch case {case_id}: {e}")
            return None, "ERROR"
        finally:
            session.close()

    def update_officer_review(self, case_id: str, review: OfficerReview) -> Optional[ScreeningResult]:
        session = self.Session()
        try:
            record = session.get(CaseModel, case_id)
            if not record:
                return None

            record.is_reviewed = True
            record.officer_id = review.officer_id
            record.officer_name = review.officer_name
            record.officer_decision = review.decision
            record.officer_notes = review.notes
            record.reviewed_at = datetime.utcnow()

            payload = json.loads(record.payload_json)
            payload["officer_review"] = review.model_dump()
            record.payload_json = json.dumps(payload)

            audit = AuditLogModel(
                case_id=case_id,
                action="OFFICER_REVIEW_SUBMITTED",
                actor=review.officer_id or "OFFICER",
                details=f"Decision: {review.decision}, Notes: {review.notes}"
            )
            session.add(audit)
            session.commit()

            return ScreeningResult(**payload)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update officer review for {case_id}: {e}")
            return None
        finally:
            session.close()

    def list_cases(self, limit: int = 50, offset: int = 0) -> List[CaseSummary]:
        session = self.Session()
        try:
            stmt = select(CaseModel).order_by(desc(CaseModel.created_at)).offset(offset).limit(limit)
            records = session.scalars(stmt).all()
            results = []
            for r in records:
                results.append(CaseSummary(
                    case_id=r.case_id,
                    timestamp=r.created_at.isoformat() if r.created_at else "",
                    document_type=r.document_type,
                    document_number=r.document_number_masked,
                    risk_score=r.risk_score,
                    risk_level=r.risk_level,
                    verdict=r.verdict,
                    officer_decision=r.officer_decision
                ))
            return results
        except Exception as e:
            logger.error(f"Failed to list cases: {e}")
            return []
        finally:
            session.close()

# Global Singleton
storage_service = StorageService()

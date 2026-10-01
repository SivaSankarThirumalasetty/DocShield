import json
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class CaseModel(Base):
    __tablename__ = "cases"

    case_id = Column(String(64), primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processing_time_ms = Column(Float, default=0.0)
    
    # Ownership & Session Token Hash (Prevents ID Enumeration)
    session_token_hash = Column(String(64), nullable=True, index=True)
    
    # Classification & Extracted Summary
    document_type = Column(String(32), default="UNKNOWN")
    document_number_masked = Column(String(64), nullable=True)
    person_name = Column(String(128), nullable=True)
    
    # Risk Metrics
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(16), default="LOW")
    verdict = Column(String(32), default="CLEARED")
    
    # Officer Review Fields
    is_reviewed = Column(Boolean, default=False)
    officer_id = Column(String(64), nullable=True)
    officer_name = Column(String(128), nullable=True)
    officer_decision = Column(String(32), nullable=True)
    officer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Complete Serialized Screening Payload (JSON)
    payload_json = Column(Text, nullable=False)

    def to_dict(self):
        return json.loads(self.payload_json)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    case_id = Column(String(64), index=True, nullable=True)
    action = Column(String(64), nullable=False)
    actor = Column(String(64), default="SYSTEM")
    details = Column(Text, nullable=True)

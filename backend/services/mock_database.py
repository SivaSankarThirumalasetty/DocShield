import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from difflib import SequenceMatcher
from ..models.schemas import WatchlistHit

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "mock_database.json"

class MockDatabaseService:
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or DATA_FILE
        self.data: Dict[str, Any] = {"verified_registry": [], "stolen_or_lost": [], "watchlist": []}
        self.load_data()

    def load_data(self):
        if self.data_path.exists():
            try:
                with open(self.data_path, "r", encoding="utf-8-sig") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[!] Warning: Failed to load mock database: {e}")
        else:
            print(f"[!] Warning: Mock database file not found at {self.data_path}")

    def normalize(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return "".join(c.lower() for c in text if c.isalnum())

    def check_watchlist(self, name: Optional[str] = None, doc_number: Optional[str] = None) -> WatchlistHit:
        norm_doc = self.normalize(doc_number)
        norm_name = self.normalize(name)

        # 1. Check Stolen / Lost Documents
        if norm_doc:
            for item in self.data.get("stolen_or_lost", []):
                if self.normalize(item.get("document_number")) == norm_doc:
                    return WatchlistHit(
                        is_flagged=True,
                        status="STOLEN_ID_ALERT",
                        matched_record_id=item.get("document_number"),
                        matched_name=item.get("reported_by"),
                        watchlist_category="REPORTED_STOLEN_OR_LOST",
                        details=f"Document flagged as stolen/lost: {item.get('reason')} (Reported: {item.get('reported_date')})"
                    )

        # 2. Check Watchlist (LOC / Security Alerts)
        for item in self.data.get("watchlist", []):
            # Check doc numbers
            for d in item.get("document_numbers", []):
                if norm_doc and self.normalize(d) == norm_doc:
                    return WatchlistHit(
                        is_flagged=True,
                        status="WATCHLIST_HIT",
                        matched_record_id=item.get("watchlist_id"),
                        matched_name=item.get("name"),
                        watchlist_category=item.get("category"),
                        details=f"Watchlist alert issued by {item.get('issuing_agency')}: {item.get('instructions')}"
                    )
            # Check name fuzzy similarity
            if norm_name:
                item_name_norm = self.normalize(item.get("name"))
                sim = SequenceMatcher(None, norm_name, item_name_norm).ratio()
                if sim > 0.85:
                    return WatchlistHit(
                        is_flagged=True,
                        status="WATCHLIST_HIT",
                        matched_record_id=item.get("watchlist_id"),
                        matched_name=item.get("name"),
                        watchlist_category=item.get("category"),
                        details=f"Name match ({int(sim*100)}% similarity) on {item.get('issuing_agency')} alert: {item.get('instructions')}"
                    )
                for alias in item.get("alias", []):
                    if SequenceMatcher(None, norm_name, self.normalize(alias)).ratio() > 0.85:
                        return WatchlistHit(
                            is_flagged=True,
                            status="WATCHLIST_HIT",
                            matched_record_id=item.get("watchlist_id"),
                            matched_name=f"{item.get('name')} (alias: {alias})",
                            watchlist_category=item.get("category"),
                            details=f"Alias match on {item.get('issuing_agency')} alert: {item.get('instructions')}"
                        )

        # 3. Check Verified Registry for mismatches
        if norm_doc:
            for item in self.data.get("verified_registry", []):
                if self.normalize(item.get("document_number")) == norm_doc:
                    if norm_name:
                        reg_name_norm = self.normalize(item.get("full_name"))
                        sim = SequenceMatcher(None, norm_name, reg_name_norm).ratio()
                        if sim < 0.60:
                            return WatchlistHit(
                                is_flagged=True,
                                status="IMPOSTER_ALERT",
                                matched_record_id=item.get("document_number"),
                                matched_name=item.get("full_name"),
                                watchlist_category="REGISTRY_NAME_MISMATCH",
                                details=f"Document number belongs to '{item.get('full_name')}' in registry, but presented name is '{name}'"
                            )
                    return WatchlistHit(
                        is_flagged=False,
                        status="CLEARED",
                        matched_record_id=item.get("document_number"),
                        matched_name=item.get("full_name"),
                        watchlist_category="VERIFIED_REGISTRY_RECORD",
                        details="Document number matches active, verified citizen registry record."
                    )

        return WatchlistHit(
            is_flagged=False,
            status="CLEARED",
            details="No hits found in SSB look-out circulars or stolen document registry."
        )

# Global singleton
db_service = MockDatabaseService()

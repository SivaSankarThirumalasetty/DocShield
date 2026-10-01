import json
from pathlib import Path
from typing import Optional, Dict, Any
from difflib import SequenceMatcher
from ..models.schemas import WatchlistHit
from ..core.logging import logger

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "mock_database.json"

class MockDatabaseService:
    """
    DEMO_WATCHLIST Service.
    Queries a local synthetic/sample dataset (7 records) for prototyping and demonstration.
    DISCLAIMER: This is a static demonstration database and is NOT connected to any
    official government or law-enforcement registry.
    """
    def __init__(self, data_path: Optional[Any] = None):
        self.data_path = Path(data_path) if data_path else DATA_FILE
        self.data: Dict[str, Any] = {"verified_registry": [], "stolen_or_lost": [], "watchlist": []}
        self.is_loaded: bool = False
        self.load_data()

    def load_data(self):
        self.is_loaded = False
        if self.data_path.exists():
            try:
                with open(self.data_path, "r", encoding="utf-8-sig") as f:
                    self.data = json.load(f)
                self.is_loaded = True
                logger.info(f"DEMO_WATCHLIST loaded {len(self.data.get('watchlist', []))} alert records from {self.data_path.name}")
            except Exception as e:
                logger.error(f"Failed to load DEMO_WATCHLIST database: {e}")
                self.is_loaded = False
        else:
            logger.warning(f"DEMO_WATCHLIST file not found at {self.data_path}")
            self.is_loaded = False

    def normalize(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return "".join(c.lower() for c in text if c.isalnum())

    def check_watchlist(self, name: Optional[str] = None, doc_number: Optional[str] = None) -> WatchlistHit:
        if not self.is_loaded:
            return WatchlistHit(
                is_flagged=False,
                status="UNAVAILABLE",
                details="[DEMO_WATCHLIST] Registry database unavailable or failed to load.",
                evidence_state="UNAVAILABLE"
            )

        norm_doc = self.normalize(doc_number)
        norm_name = self.normalize(name)

        # 1. Check Stolen / Lost Documents (DEMO Registry)
        if norm_doc:
            for item in self.data.get("stolen_or_lost", []):
                if self.normalize(item.get("document_number")) == norm_doc:
                    return WatchlistHit(
                        is_flagged=True,
                        status="STOLEN_ID_ALERT",
                        matched_record_id=item.get("document_number"),
                        matched_name=item.get("reported_by"),
                        watchlist_category="DEMO_STOLEN_OR_LOST_RECORD",
                        details=f"[DEMO_WATCHLIST] Document flagged in sample database: {item.get('reason')} (Reported: {item.get('reported_date')})"
                    )

        # 2. Check Watchlist Alerts (DEMO Security Alerts)
        for item in self.data.get("watchlist", []):
            # Check doc numbers
            for d in item.get("document_numbers", []):
                if norm_doc and self.normalize(d) == norm_doc:
                    return WatchlistHit(
                        is_flagged=True,
                        status="WATCHLIST_HIT",
                        matched_record_id=item.get("watchlist_id"),
                        matched_name=item.get("name"),
                        watchlist_category=f"DEMO_{item.get('category', 'ALERT')}",
                        details=f"[DEMO_WATCHLIST] Alert record match (Sample ID: {item.get('watchlist_id')}): {item.get('instructions')}"
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
                        watchlist_category=f"DEMO_{item.get('category', 'ALERT')}",
                        details=f"[DEMO_WATCHLIST] Name match ({int(sim*100)}% fuzzy similarity) on sample alert: {item.get('instructions')}"
                    )
                for alias in item.get("alias", []):
                    if SequenceMatcher(None, norm_name, self.normalize(alias)).ratio() > 0.85:
                        return WatchlistHit(
                            is_flagged=True,
                            status="WATCHLIST_HIT",
                            matched_record_id=item.get("watchlist_id"),
                            matched_name=f"{item.get('name')} (alias: {alias})",
                            watchlist_category=f"DEMO_{item.get('category', 'ALERT')}",
                            details=f"[DEMO_WATCHLIST] Alias match on sample alert: {item.get('instructions')}"
                        )

        # 3. Check Verified Registry for mismatches (DEMO Registry)
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
                                watchlist_category="DEMO_REGISTRY_NAME_MISMATCH",
                                details=f"[DEMO_WATCHLIST] Document number matches sample record for '{item.get('full_name')}', but presented name is '{name}'"
                            )
                    return WatchlistHit(
                        is_flagged=False,
                        status="CLEARED",
                        matched_record_id=item.get("document_number"),
                        matched_name=item.get("full_name"),
                        watchlist_category="DEMO_VERIFIED_SAMPLE",
                        details="[DEMO_WATCHLIST] Document number matched active sample registry entry."
                    )

        return WatchlistHit(
            is_flagged=False,
            status="CLEARED",
            details="[DEMO_WATCHLIST] No matches found in the 7-record prototype database (Non-authoritative)."
        )

# Global singleton
db_service = MockDatabaseService()

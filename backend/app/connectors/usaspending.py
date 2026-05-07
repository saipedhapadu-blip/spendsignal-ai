"""USAspending.gov contract awards connector."""
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

USASPENDING_BASE = "https://api.usaspending.gov/api/v2"

FORCED_SPEND_NAICS = [
    "541512",  # Computer Systems Design
    "541519",  # Other Computer Related Services
    "541611",  # Mgmt Consulting
    "541690",  # Other Scientific/Technical Consulting
    "541715",  # R&D Physical/Engineering
    "562910",  # Remediation Services
    "562112",  # Hazardous Waste Collection
    "621111",  # Offices of Physicians
    "923120",  # Health/Human Services
    "922120",  # Police Protection
    "541380",  # Testing Laboratories
    "541990",  # Other Professional/Scientific
]


class USASpendingConnector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=60,
            headers={
                "User-Agent": settings.SEC_USER_AGENT,
                "Content-Type": "application/json",
            },
        )

    def search_awards(
        self,
        naics_codes: List[str],
        date_start: str,
        date_end: str,
        limit: int = 100,
        page: int = 1,
    ) -> Dict[str, Any]:
        payload = {
            "filters": {
                "naics_codes": naics_codes,
                "time_period": [{"start_date": date_start, "end_date": date_end}],
                "award_type_codes": ["A", "B", "C", "D"],  # contracts
            },
            "fields": [
                "Award ID", "Recipient Name", "Recipient UEI",
                "Awarding Agency", "Funding Agency", "NAICS Code",
                "PSC Code", "Award Amount", "Award Date",
                "Period of Performance Start Date",
                "Period of Performance Current End Date",
                "Description", "Contract Award Type",
                "Place of Performance State Code",
            ],
            "limit": limit,
            "page": page,
            "sort": "Award Amount",
            "order": "desc",
        }
        resp = self.client.post(
            f"{USASPENDING_BASE}/search/spending_by_award/", json=payload
        )
        resp.raise_for_status()
        time.sleep(0.3)
        return resp.json()

    def fetch_expiring_contracts(
        self,
        days_ahead: int = 180,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Fetch contracts expiring within days_ahead window."""
        today = datetime.utcnow()
        end_window = today + timedelta(days=days_ahead)
        results: List[Dict[str, Any]] = []

        payload = {
            "filters": {
                "naics_codes": FORCED_SPEND_NAICS,
                "time_period": [{
                    "start_date": today.strftime("%Y-%m-%d"),
                    "end_date": end_window.strftime("%Y-%m-%d"),
                    "date_type": "action_date",
                }],
                "award_type_codes": ["A", "B", "C", "D"],
            },
            "fields": [
                "Award ID", "Recipient Name", "Recipient UEI",
                "Awarding Agency", "NAICS Code", "Award Amount",
                "Period of Performance Current End Date",
                "Description",
            ],
            "limit": min(limit, 100),
            "page": 1,
            "sort": "Period of Performance Current End Date",
            "order": "asc",
        }
        try:
            resp = self.client.post(
                f"{USASPENDING_BASE}/search/spending_by_award/", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
        except Exception as e:
            logger.error(f"USAspending expiring contracts error: {e}")

        return results

    def normalize_record(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a USAspending award record."""
        return {
            "source": "usaspending",
            "external_id": raw.get("Award ID"),
            "recipient_name": raw.get("Recipient Name"),
            "recipient_uei": raw.get("Recipient UEI"),
            "awarding_agency": raw.get("Awarding Agency"),
            "funding_agency": raw.get("Funding Agency"),
            "naics_code": raw.get("NAICS Code"),
            "psc_code": raw.get("PSC Code"),
            "award_amount": raw.get("Award Amount"),
            "award_date": raw.get("Award Date"),
            "period_start": raw.get("Period of Performance Start Date"),
            "period_end": raw.get("Period of Performance Current End Date"),
            "description": raw.get("Description", ""),
            "contract_type": raw.get("Contract Award Type"),
            "place_of_performance": raw.get("Place of Performance State Code"),
        }

    def ingest_recent_awards(self, days_back: int = 90) -> List[Dict[str, Any]]:
        """Ingest recent awards in forced-spend NAICS categories."""
        date_end = datetime.utcnow().strftime("%Y-%m-%d")
        date_start = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        results: List[Dict[str, Any]] = []
        try:
            data = self.search_awards(FORCED_SPEND_NAICS, date_start, date_end, limit=100)
            for r in data.get("results", []):
                results.append(self.normalize_record(r))
        except Exception as e:
            logger.error(f"USAspending ingest error: {e}")
        return results

    def ingest_all(self) -> List[Dict[str, Any]]:
        """Main ingestion: recent awards + expiring contracts."""
        records = self.ingest_recent_awards()
        expiring = self.fetch_expiring_contracts()
        for r in expiring:
            records.append(self.normalize_record(r))
        return records

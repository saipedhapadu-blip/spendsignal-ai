"""EPA ECHO enforcement and compliance connector."""
import time
import logging
from typing import List, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

ECHO_BASE = "https://echo.epa.gov/api"

TRIGGER_CATEGORIES = {
    "air_violation": ["CAA", "air", "emission", "stack"],
    "water_violation": ["CWA", "water", "discharge", "effluent", "stormwater"],
    "hazardous_waste": ["RCRA", "hazardous", "waste", "storage"],
    "significant_noncompliance": ["SNC", "significant noncompliance"],
    "formal_enforcement": ["formal", "order", "penalty", "consent"],
}


class EPAECHOConnector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=60,
            headers={"User-Agent": settings.SEC_USER_AGENT},
        )

    def fetch_facilities_with_violations(
        self,
        state: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Fetch facilities with recent violations from ECHO API."""
        params = {
            "output": "JSON",
            "p_qnc": "1",  # has violations
            "p_act": "Y",  # active facilities
            "responseset": limit,
            "pageno": max(1, offset // limit + 1),
        }
        if state:
            params["p_st"] = state
        try:
            resp = self.client.get(
                f"{ECHO_BASE}/rest/facilities/search", params=params
            )
            resp.raise_for_status()
            time.sleep(0.5)
            return resp.json()
        except Exception as e:
            logger.error(f"EPA ECHO facility search error: {e}")
            return {}

    def fetch_enforcement_actions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Fetch recent enforcement actions."""
        params = {
            "output": "JSON",
            "p_enf_type": "formal",
            "responseset": limit,
            "pageno": max(1, offset // limit + 1),
        }
        try:
            resp = self.client.get(
                f"{ECHO_BASE}/rest/facilities/search", params=params
            )
            resp.raise_for_status()
            time.sleep(0.5)
            return resp.json()
        except Exception as e:
            logger.error(f"EPA ECHO enforcement fetch error: {e}")
            return {}

    def _classify_trigger(self, facility: Dict[str, Any]) -> List[str]:
        """Classify enforcement triggers for a facility."""
        categories = []
        programs = str(facility.get("ProgramSystemAcronyms", "")).upper()
        if "CAA" in programs:
            categories.append("air_violation")
        if "CWA" in programs:
            categories.append("water_violation")
        if "RCRA" in programs:
            categories.append("hazardous_waste")
        if facility.get("SNCStatus") == "Y":
            categories.append("significant_noncompliance")
        if float(facility.get("FormalEnfActCount", 0) or 0) > 0:
            categories.append("formal_enforcement")
        return categories or ["compliance_issue"]

    def normalize_record(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an EPA ECHO facility record."""
        trigger_cats = self._classify_trigger(raw)
        penalty = 0.0
        try:
            penalty = float(raw.get("TotalPenalties", 0) or 0)
        except (ValueError, TypeError):
            pass
        return {
            "source": "epa_echo",
            "external_id": raw.get("RegistryID"),
            "facility_name": raw.get("FacilityName"),
            "address": raw.get("FacilityStreet"),
            "city": raw.get("FacilityCity"),
            "state": raw.get("FacilityState"),
            "zip": raw.get("FacilityZip"),
            "latitude": raw.get("FacilityLatitude"),
            "longitude": raw.get("FacilityLongitude"),
            "industry_codes": raw.get("NAICSCodes"),
            "sic_codes": raw.get("SICCodes"),
            "program_systems": raw.get("ProgramSystemAcronyms"),
            "compliance_status": raw.get("ComplianceStatus"),
            "snc_status": raw.get("SNCStatus"),
            "inspection_count": raw.get("InspectionCount"),
            "formal_enforcement_count": raw.get("FormalEnfActCount"),
            "total_penalties": penalty,
            "violation_count": raw.get("ViolationCount"),
            "trigger_categories": trigger_cats,
            "parent_company": raw.get("FacilityParentCompany"),
            "registry_id": raw.get("RegistryID"),
        }

    def ingest_all(
        self,
        states: List[str] = None,
        limit_per_state: int = 100,
    ) -> List[Dict[str, Any]]:
        """Ingest EPA ECHO violation data."""
        results: List[Dict[str, Any]] = []
        if states:
            for state in states:
                data = self.fetch_facilities_with_violations(
                    state=state, limit=limit_per_state
                )
                facilities = data.get("Results", {}).get("Facilities", [])
                for f in facilities:
                    results.append(self.normalize_record(f))
        else:
            data = self.fetch_facilities_with_violations(limit=limit_per_state)
            facilities = data.get("Results", {}).get("Facilities", [])
            for f in facilities:
                results.append(self.normalize_record(f))
        return results

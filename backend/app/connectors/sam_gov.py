"""SAM.gov contract opportunities connector."""
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

SAM_API_BASE = "https://api.sam.gov/opportunities/v2/search"

CYBER_KEYWORDS = [
    "cybersecurity", "cyber security", "information security", "SIEM",
    "SOC", "penetration testing", "vulnerability", "zero trust", "CMMC",
    "FedRAMP", "FISMA", "data breach", "incident response", "EDR", "XDR"
]

COMPLIANCE_KEYWORDS = [
    "compliance", "GRC", "risk management", "audit", "regulatory",
    "NIST", "ISO 27001", "SOC 2", "governance", "internal controls",
    "remediation", "corrective action", "consent decree"
]

HEALTH_KEYWORDS = [
    "HIPAA", "healthcare", "health IT", "EHR", "EMR", "patient data",
    "medical device", "FDA", "clinical", "pharmacy", "health information"
]

ENV_KEYWORDS = [
    "environmental", "EPA", "remediation", "hazardous waste", "cleanup",
    "Superfund", "CERCLA", "air quality", "water treatment", "spill response"
]

SAFETY_KEYWORDS = [
    "OSHA", "workplace safety", "safety management", "EHS", "occupational health",
    "accident prevention", "safety training", "PPE", "hazard analysis"
]

QUALITY_KEYWORDS = [
    "quality management", "QMS", "ISO 9001", "quality assurance",
    "quality control", "FDA inspection", "GMP", "cGMP", "21 CFR",
    "corrective action", "CAPA", "nonconformance"
]

LEGAL_KEYWORDS = [
    "legal services", "litigation", "outside counsel", "law firm",
    "contract management", "regulatory counsel", "settlement", "arbitration"
]

ALL_KEYWORD_GROUPS = {
    "cybersecurity": CYBER_KEYWORDS,
    "compliance_grc": COMPLIANCE_KEYWORDS,
    "healthcare_hipaa": HEALTH_KEYWORDS,
    "environmental": ENV_KEYWORDS,
    "safety_ehs": SAFETY_KEYWORDS,
    "quality_fda": QUALITY_KEYWORDS,
    "legal_audit": LEGAL_KEYWORDS,
}


class SAMGovConnector:
    def __init__(self):
        self.api_key = settings.SAM_GOV_API_KEY
        self.client = httpx.Client(
            timeout=30,
            headers={"User-Agent": settings.SEC_USER_AGENT},
        )

    def _search_opportunities(
        self,
        keyword: str,
        posted_from: str,
        posted_to: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params = {
            "api_key": self.api_key,
            "keyword": keyword,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "limit": limit,
            "offset": offset,
            "active": "true",
        }
        resp = self.client.get(SAM_API_BASE, params=params)
        resp.raise_for_status()
        time.sleep(0.5)
        return resp.json()

    def fetch_opportunities(
        self,
        days_back: int = 30,
        limit_per_keyword: int = 200,
    ) -> List[Dict[str, Any]]:
        posted_to = datetime.utcnow().strftime("%m/%d/%Y")
        posted_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")
        seen_ids: set = set()
        results: List[Dict[str, Any]] = []

        for category, keywords in ALL_KEYWORD_GROUPS.items():
            for kw in keywords[:3]:  # top 3 per group to stay within rate limits
                try:
                    data = self._search_opportunities(kw, posted_from, posted_to, limit=100)
                    opps = data.get("opportunitiesData", [])
                    for opp in opps:
                        notice_id = opp.get("noticeId") or opp.get("solicitationNumber")
                        if notice_id and notice_id not in seen_ids:
                            seen_ids.add(notice_id)
                            opp["_matched_category"] = category
                            opp["_matched_keyword"] = kw
                            results.append(opp)
                    if len(results) >= limit_per_keyword:
                        break
                except Exception as e:
                    logger.error(f"SAM.gov fetch error for keyword '{kw}': {e}")
                    continue

        return results

    def normalize_record(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a SAM.gov opportunity record."""
        active = raw.get("active", "Yes")
        return {
            "source": "sam_gov",
            "external_id": raw.get("noticeId") or raw.get("solicitationNumber"),
            "title": raw.get("title", ""),
            "solicitation_number": raw.get("solicitationNumber"),
            "department": raw.get("department"),
            "sub_tier": raw.get("subTier"),
            "office": raw.get("office"),
            "notice_type": raw.get("type"),
            "naics_code": raw.get("naicsCode"),
            "psc_code": raw.get("classificationCode"),
            "set_aside": raw.get("typeOfSetAsideDescription"),
            "posted_date": raw.get("postedDate"),
            "response_deadline": raw.get("responseDeadLine"),
            "description": raw.get("description", ""),
            "place_of_performance": raw.get("placeOfPerformance"),
            "archive_date": raw.get("archiveDate"),
            "is_active": active == "Yes" or active is True,
            "matched_category": raw.get("_matched_category"),
            "matched_keyword": raw.get("_matched_keyword"),
            "ui_link": raw.get("uiLink"),
            "point_of_contact": raw.get("pointOfContact", []),
        }

    def ingest_all(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Fetch and normalize all relevant SAM.gov opportunities."""
        raw_records = self.fetch_opportunities(days_back=days_back)
        return [self.normalize_record(r) for r in raw_records]

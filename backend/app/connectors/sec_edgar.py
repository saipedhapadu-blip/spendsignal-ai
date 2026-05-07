"""SEC EDGAR connector for SpendSignal AI."""
import hashlib
import time
import json
from datetime import datetime
from typing import List, Dict, Optional
import httpx
from app.config import settings


SEC_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"

TARGET_FORM_TYPES = ["8-K", "10-K", "10-Q"]

SEC_KEYWORDS = [
    "material weakness", "cybersecurity incident", "data breach",
    "regulatory investigation", "subpoena", "consent order",
    "environmental remediation", "product recall", "FDA warning",
    "OSHA", "EPA", "HIPAA", "privacy", "litigation",
    "internal controls", "compliance program", "remediation plan",
    "restatement", "audit committee investigation", "enforcement action",
    "penalty", "settlement", "securities class action"
]


class SECEDGARConnector:
    """Connector for SEC EDGAR filings."""
    
    def __init__(self):
        self.headers = {
            "User-Agent": settings.SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }
        self.rate_limit = settings.SEC_RATE_LIMIT
        self._last_request = 0
    
    def _rate_limit_wait(self):
        """Respect SEC rate limits."""
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()
    
    def get_company_submissions(self, cik: str) -> Optional[Dict]:
        """Get company submissions from SEC EDGAR."""
        cik_padded = cik.zfill(10)
        url = f"{SEC_BASE_URL}/submissions/CIK{cik_padded}.json"
        self._rate_limit_wait()
        try:
            with httpx.Client() as client:
                resp = client.get(url, headers=self.headers, timeout=30)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            print(f"Error fetching submissions for CIK {cik}: {e}")
            return None
    
    def get_recent_filings(self, cik: str, form_types: List[str] = None) -> List[Dict]:
        """Get recent filings for a CIK."""
        if form_types is None:
            form_types = TARGET_FORM_TYPES
        
        data = self.get_company_submissions(cik)
        if not data:
            return []
        
        filings = []
        recent = data.get("filings", {}).get("recent", {})
        
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        
        for i, form in enumerate(forms):
            if form in form_types:
                filing = {
                    "cik": cik,
                    "company_name": data.get("name", ""),
                    "ticker": data.get("tickers", [None])[0] if data.get("tickers") else None,
                    "form_type": form,
                    "accession_number": accession_numbers[i] if i < len(accession_numbers) else None,
                    "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                    "primary_document": primary_docs[i] if i < len(primary_docs) else None,
                }
                
                if filing["accession_number"] and filing["primary_document"]:
                    acc_no_clean = filing["accession_number"].replace("-", "")
                    cik_no_lead = str(int(cik))
                    filing["filing_url"] = (
                        f"{SEC_ARCHIVES_URL}/{cik_no_lead}/"
                        f"{acc_no_clean}/{filing['primary_document']}"
                    )
                
                filings.append(filing)
        
        return filings
    
    def extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract SEC-relevant keywords from filing text."""
        if not text:
            return []
        text_lower = text.lower()
        found = []
        for kw in SEC_KEYWORDS:
            if kw.lower() in text_lower:
                found.append(kw)
        return found
    
    def compute_content_hash(self, content: Dict) -> str:
        """Compute a hash of the content for deduplication."""
        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def ingest_filings_for_cik(self, cik: str) -> List[Dict]:
        """Full ingestion flow for a single CIK."""
        filings = self.get_recent_filings(cik)
        records = []
        
        for filing in filings:
            record = {
                "external_id": filing.get("accession_number"),
                "source_url": filing.get("filing_url"),
                "source_published_at": filing.get("filing_date"),
                "raw_json": filing,
                "raw_text": f"{filing.get('company_name')} {filing.get('form_type')} filed {filing.get('filing_date')}",
                "content_hash": self.compute_content_hash(filing),
                "metadata": {
                    "cik": cik,
                    "ticker": filing.get("ticker"),
                    "company_name": filing.get("company_name"),
                    "form_type": filing.get("form_type"),
                }
            }
            records.append(record)
        
        return records

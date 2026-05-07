"""openFDA connector for SpendSignal AI."""
import hashlib
import json
from typing import List, Dict, Optional
import httpx
from app.config import settings


OPENFDA_BASE = settings.OPENFDA_BASE_URL

FDA_ENDPOINTS = {
    "food": f"{OPENFDA_BASE}/food/enforcement.json",
    "drug": f"{OPENFDA_BASE}/drug/enforcement.json",
    "device": f"{OPENFDA_BASE}/device/enforcement.json",
}

CLASS_SEVERITY = {
    "Class I": "critical",
    "Class II": "high",
    "Class III": "medium",
}

FDA_TRIGGER_CATEGORIES = {
    "Class I": "FDA_RECALL",
    "Class II": "FDA_RECALL",
    "contamination": "FDA_WARNING_SIGNAL",
    "undeclared allergen": "FDA_WARNING_SIGNAL",
    "labeling": "FDA_WARNING_SIGNAL",
    "sterility": "FDA_WARNING_SIGNAL",
    "device malfunction": "FDA_RECALL",
    "GMP": "FDA_WARNING_SIGNAL",
}


class OpenFDAConnector:
    """Connector for openFDA enforcement/recall data."""
    
    def fetch_recalls(self, product_type: str, limit: int = 100, skip: int = 0) -> List[Dict]:
        """Fetch recall enforcement records from openFDA."""
        url = FDA_ENDPOINTS.get(product_type)
        if not url:
            raise ValueError(f"Unknown product type: {product_type}")
        
        params = {
            "limit": limit,
            "skip": skip,
        }
        
        try:
            with httpx.Client() as client:
                resp = client.get(url, params=params, timeout=30)
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
                data = resp.json()
                return data.get("results", [])
        except Exception as e:
            print(f"Error fetching {product_type} recalls: {e}")
            return []
    
    def classify_severity(self, record: Dict) -> str:
        """Classify severity based on recall classification."""
        classification = record.get("classification", "")
        return CLASS_SEVERITY.get(classification, "low")
    
    def classify_trigger(self, record: Dict) -> str:
        """Classify trigger type based on recall data."""
        reason = record.get("reason_for_recall", "").lower()
        classification = record.get("classification", "")
        
        if classification in ["Class I", "Class II"]:
            return "FDA_RECALL"
        
        for keyword, trigger_type in FDA_TRIGGER_CATEGORIES.items():
            if keyword.lower() in reason:
                return trigger_type
        
        return "FDA_RECALL"
    
    def compute_content_hash(self, content: Dict) -> str:
        """Compute content hash for deduplication."""
        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def normalize_record(self, record: Dict, product_type: str) -> Dict:
        """Normalize an openFDA recall record."""
        return {
            "external_id": record.get("recall_number", ""),
            "source_url": f"https://api.fda.gov/{product_type}/enforcement.json",
            "source_published_at": record.get("report_date"),
            "raw_json": record,
            "raw_text": (
                f"{record.get('recalling_firm', '')} "
                f"Recall: {record.get('product_description', '')} "
                f"Reason: {record.get('reason_for_recall', '')} "
                f"Classification: {record.get('classification', '')}"
            ),
            "content_hash": self.compute_content_hash(record),
            "metadata": {
                "product_type": product_type,
                "classification": record.get("classification"),
                "recalling_firm": record.get("recalling_firm"),
                "recall_number": record.get("recall_number"),
                "severity": self.classify_severity(record),
                "trigger_type": self.classify_trigger(record),
                "status": record.get("status"),
                "state": record.get("state"),
                "country": record.get("country"),
            }
        }
    
    def ingest_all(self, limit_per_type: int = 100) -> List[Dict]:
        """Ingest recalls from all product types."""
        records = []
        for product_type in FDA_ENDPOINTS.keys():
            raw_records = self.fetch_recalls(product_type, limit=limit_per_type)
            for record in raw_records:
                normalized = self.normalize_record(record, product_type)
                records.append(normalized)
        return records

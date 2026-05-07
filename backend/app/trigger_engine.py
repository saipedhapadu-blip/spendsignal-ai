"""Trigger extraction engine - Layer 1 deterministic, Layer 2 AI."""
import re
import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Layer 1: Deterministic trigger patterns
TRIGGER_PATTERNS: Dict[str, List[str]] = {
    "cybersecurity_incident": [
        r"cybersecurity incident", r"data breach", r"ransomware", r"cyber attack",
        r"unauthorized access", r"security incident", r"network intrusion",
        r"phishing", r"malware", r"data theft", r"information security incident",
    ],
    "material_weakness": [
        r"material weakness", r"significant deficiency", r"internal control",
        r"restatement", r"audit committee investigation", r"going concern",
    ],
    "regulatory_investigation": [
        r"regulatory investigation", r"subpoena", r"SEC investigation",
        r"DOJ investigation", r"CFTC", r"FINRA", r"consent order",
        r"enforcement action", r"civil investigative demand",
    ],
    "environmental_liability": [
        r"environmental remediation", r"EPA", r"CERCLA", r"Superfund",
        r"environmental liability", r"hazardous waste", r"contamination",
        r"air quality violation", r"water discharge violation",
    ],
    "product_recall": [
        r"product recall", r"FDA warning letter", r"Class I recall",
        r"Class II recall", r"voluntary recall", r"market withdrawal",
        r"GMP violation", r"manufacturing defect", r"quality system failure",
    ],
    "compliance_program": [
        r"compliance program", r"remediation plan", r"corrective action plan",
        r"compliance officer", r"ethics investigation", r"whistleblower",
    ],
    "litigation": [
        r"litigation", r"class action", r"lawsuit", r"legal proceedings",
        r"settlement", r"judgment", r"arbitration", r"indemnification",
    ],
    "hipaa_privacy": [
        r"HIPAA", r"HITECH", r"protected health information", r"PHI",
        r"privacy breach", r"health data", r"patient data breach",
    ],
    "osha_safety": [
        r"OSHA", r"workplace safety", r"serious violation", r"willful violation",
        r"worker injury", r"fatality", r"safety citation",
    ],
}

SEVERITY_WEIGHTS = {
    "cybersecurity_incident": 9,
    "material_weakness": 8,
    "regulatory_investigation": 8,
    "product_recall": 7,
    "environmental_liability": 7,
    "hipaa_privacy": 8,
    "osha_safety": 6,
    "litigation": 5,
    "compliance_program": 4,
}

FORCED_SPEND_MAP: Dict[str, List[str]] = {
    "cybersecurity_incident": ["cybersecurity", "incident_response", "GRC_software"],
    "material_weakness": ["audit", "GRC_software", "compliance_consulting"],
    "regulatory_investigation": ["legal", "compliance_consulting", "audit"],
    "environmental_liability": ["environmental_remediation", "EHS_consulting", "EHS_software"],
    "product_recall": ["QMS_software", "quality_consulting", "regulatory_affairs"],
    "compliance_program": ["GRC_software", "compliance_consulting", "training"],
    "litigation": ["legal", "eDiscovery", "compliance_consulting"],
    "hipaa_privacy": ["HIPAA_consulting", "healthcare_IT", "privacy_software"],
    "osha_safety": ["safety_consulting", "EHS_software", "training"],
}


def extract_triggers_deterministic(text: str) -> List[Dict[str, Any]]:
    """Layer 1: Extract triggers using pattern matching."""
    if not text:
        return []
    text_lower = text.lower()
    found_triggers = []

    for category, patterns in TRIGGER_PATTERNS.items():
        matched_phrases = []
        for pattern in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            matched_phrases.extend(matches)
        if matched_phrases:
            found_triggers.append({
                "category": category,
                "matched_phrases": list(set(matched_phrases)),
                "severity": SEVERITY_WEIGHTS.get(category, 5),
                "forced_spend_categories": FORCED_SPEND_MAP.get(category, []),
                "method": "deterministic",
                "confidence": 0.95,
            })

    return found_triggers


def extract_triggers_ai(text: str, max_chars: int = 3000) -> Optional[Dict[str, Any]]:
    """Layer 2: AI-based trigger extraction. Only called when deterministic finds nothing."""
    if not settings.OPENAI_API_KEY:
        return None
    if not text:
        return None

    truncated = text[:max_chars]
    prompt = (
        "You are a regulatory intelligence analyst. Analyze the following text and extract "
        "any signals that suggest an organization may be forced to spend money on "
        "compliance, remediation, cybersecurity, legal, audit, safety, quality, environmental, "
        "or risk-management solutions.\n\n"
        "Rules:\n"
        "- Do NOT invent facts. Only use what is stated in the text.\n"
        "- Use neutral commercial language: 'may need', 'likely needs', 'potentially exposed to'.\n"
        "- Return ONLY valid JSON matching this schema:\n"
        "{\"triggers\": [{\"category\": string, \"summary\": string, \"severity\": 1-10, "
        "\"forced_spend_categories\": [string], \"confidence\": 0.0-1.0}]}\n\n"
        f"Text:\n{truncated}"
    )

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 800,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        for t in parsed.get("triggers", []):
            t["method"] = "ai"
        return parsed
    except Exception as e:
        logger.error(f"AI trigger extraction error: {e}")
        return None


def extract_triggers(text: str) -> List[Dict[str, Any]]:
    """Main entry: deterministic first, AI fallback if nothing found."""
    triggers = extract_triggers_deterministic(text)
    if triggers:
        return triggers
    # Fallback to AI
    ai_result = extract_triggers_ai(text)
    if ai_result:
        return ai_result.get("triggers", [])
    return []


def score_opportunity(triggers: List[Dict[str, Any]], source: str = "") -> int:
    """Score 0-100 based on trigger severity and count."""
    if not triggers:
        return 0
    max_severity = max(t.get("severity", 0) for t in triggers)
    trigger_count = len(triggers)
    base_score = (max_severity / 10) * 60
    count_bonus = min(trigger_count * 5, 30)
    source_bonus = 10 if source in ["sec_edgar", "epa_echo"] else 5
    return min(int(base_score + count_bonus + source_bonus), 100)

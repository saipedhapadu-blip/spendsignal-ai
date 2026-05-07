from typing import List, Optional
from dataclasses import dataclass

# Severity weights for scoring
SEVERITY_WEIGHTS = {
    "critical": 30,
    "high": 20,
    "medium": 10,
    "low": 5,
}

# Category urgency multipliers
CATEGORY_URGENCY = {
    "cybersecurity": 1.3,
    "data_privacy": 1.2,
    "environmental": 1.1,
    "product_recall": 1.2,
    "financial_fraud": 1.3,
    "workplace_safety": 1.1,
    "compliance_grc": 1.0,
    "healthcare_hipaa": 1.2,
    "legal_proceedings": 1.1,
    "audit": 1.0,
}

# Source credibility weights
SOURCE_WEIGHTS = {
    "sec_edgar": 1.2,
    "epa_echo": 1.1,
    "openfda": 1.1,
    "sam_gov": 1.0,
    "usaspending": 0.9,
}


@dataclass
class TriggerInput:
    category: str
    severity: str
    source: str
    recency_days: int  # days since trigger event
    confirmed: bool = True  # deterministic vs AI-inferred


def compute_opportunity_score(
    triggers: List[TriggerInput],
    organization_size_hint: Optional[str] = None,
) -> dict:
    """
    Compute a 0-100 forced-spend opportunity score based on triggers.
    Uses deterministic rules only - no AI fabrication.
    Returns score and breakdown for transparency.
    """
    if not triggers:
        return {"score": 0, "breakdown": [], "confidence": "low"}

    raw_score = 0.0
    breakdown = []

    for t in triggers:
        base = SEVERITY_WEIGHTS.get(t.severity, 5)
        category_mult = CATEGORY_URGENCY.get(t.category, 1.0)
        source_mult = SOURCE_WEIGHTS.get(t.source, 1.0)

        # Recency decay: events older than 180 days get half score
        recency_factor = 1.0
        if t.recency_days > 360:
            recency_factor = 0.3
        elif t.recency_days > 180:
            recency_factor = 0.6
        elif t.recency_days > 90:
            recency_factor = 0.85

        # Confidence factor: AI-inferred triggers count less
        confidence_factor = 1.0 if t.confirmed else 0.7

        contribution = base * category_mult * source_mult * recency_factor * confidence_factor
        raw_score += contribution

        breakdown.append({
            "category": t.category,
            "severity": t.severity,
            "source": t.source,
            "contribution": round(contribution, 2),
        })

    # Normalize to 0-100 scale (cap at 100)
    # Multiple high triggers stack but cap at 100
    normalized = min(100, round(raw_score, 1))

    # Confidence assessment
    confirmed_count = sum(1 for t in triggers if t.confirmed)
    if confirmed_count >= 2:
        confidence = "high"
    elif confirmed_count == 1:
        confidence = "medium"
    else:
        confidence = "low"

    # Priority label
    if normalized >= 70:
        priority = "high"
    elif normalized >= 40:
        priority = "medium"
    else:
        priority = "low"

    return {
        "score": normalized,
        "priority": priority,
        "confidence": confidence,
        "trigger_count": len(triggers),
        "breakdown": breakdown,
    }


def score_from_raw_triggers(raw_triggers: list) -> dict:
    """
    Convert raw trigger dicts (from DB) to TriggerInput and score.
    """
    from datetime import datetime, timezone
    inputs = []
    for rt in raw_triggers:
        try:
            event_date = rt.get("event_date")
            if event_date:
                if isinstance(event_date, str):
                    event_date = datetime.fromisoformat(event_date)
                now = datetime.now(timezone.utc)
                if event_date.tzinfo is None:
                    from datetime import timezone as tz
                    event_date = event_date.replace(tzinfo=tz.utc)
                recency_days = (now - event_date).days
            else:
                recency_days = 90  # default if no date

            inputs.append(TriggerInput(
                category=rt.get("category", "compliance_grc"),
                severity=rt.get("severity", "medium"),
                source=rt.get("source", "sec_edgar"),
                recency_days=recency_days,
                confirmed=rt.get("confirmed", True),
            ))
        except Exception:
            continue

    return compute_opportunity_score(inputs)

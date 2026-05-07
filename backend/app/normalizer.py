"""Name normalization and entity resolution layer."""
import re
import logging
from typing import Optional, Dict, Any, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Suffixes to strip during normalization
CORPORATE_SUFFIXES = [
    r"\binc\.?\b", r"\bllc\.?\b", r"\bltd\.?\b", r"\bcorp\.?\b",
    r"\bcorporation\b", r"\bcompany\b", r"\bco\.?\b", r"\blp\b",
    r"\bllp\b", r"\bplc\b", r"\bpllc\b", r"\bpa\b", r"\bpc\b",
    r"\bgroup\b", r"\bholdings?\b", r"\benterprises?\b",
]

CONFIDENCE_EXACT = 0.98
CONFIDENCE_STRONG = 0.90
CONFIDENCE_PROBABLE = 0.77
CONFIDENCE_THRESHOLD = 0.70


def normalize_name(name: str) -> str:
    """Normalize an organization name for matching."""
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    for suffix in CORPORATE_SUFFIXES:
        name = re.sub(suffix, " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_address(address: str) -> str:
    """Normalize a street address."""
    if not address:
        return ""
    address = address.lower()
    replacements = {
        r"\bstreet\b": "st", r"\bavenue\b": "ave", r"\bboulevard\b": "blvd",
        r"\bdrive\b": "dr", r"\broad\b": "rd", r"\blane\b": "ln",
        r"\bcourt\b": "ct", r"\bplace\b": "pl", r"\bsuite\b": "ste",
    }
    for pattern, repl in replacements.items():
        address = re.sub(pattern, repl, address, flags=re.IGNORECASE)
    address = re.sub(r"[^a-z0-9\s]", " ", address)
    return re.sub(r"\s+", " ", address).strip()


def name_similarity(a: str, b: str) -> float:
    """Compute similarity between two normalized names."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def token_sort_similarity(a: str, b: str) -> float:
    """Token-sorted similarity."""
    if not a or not b:
        return 0.0
    a_sorted = " ".join(sorted(a.split()))
    b_sorted = " ".join(sorted(b.split()))
    return SequenceMatcher(None, a_sorted, b_sorted).ratio()


def resolve_entity(
    name: str,
    candidates: list,
    deterministic_id: Optional[str] = None,
    id_field: str = "external_id",
) -> Tuple[Optional[Dict[str, Any]], float, str]:
    """
    Resolve an entity against a list of candidates.
    Returns (best_match, confidence, method).
    Confidence bands:
      0.95-1.00 exact official identifier
      0.85-0.94 strong name+location
      0.70-0.84 probable fuzzy
      <0.70     do not auto-link
    """
    if deterministic_id:
        for candidate in candidates:
            if candidate.get(id_field) == deterministic_id:
                return candidate, CONFIDENCE_EXACT, "exact_id"

    norm_name = normalize_name(name)
    best_match = None
    best_score = 0.0
    best_method = "none"

    for candidate in candidates:
        cand_name = normalize_name(candidate.get("name", "") or "")
        if not cand_name:
            continue

        seq_score = name_similarity(norm_name, cand_name)
        tok_score = token_sort_similarity(norm_name, cand_name)
        score = max(seq_score, tok_score)

        if score > best_score:
            best_score = score
            best_match = candidate
            best_method = "fuzzy_name"

    if best_score >= 0.85:
        confidence = CONFIDENCE_STRONG
    elif best_score >= 0.70:
        confidence = CONFIDENCE_PROBABLE
    else:
        confidence = best_score

    if confidence < CONFIDENCE_THRESHOLD:
        return None, confidence, "below_threshold"

    return best_match, confidence, best_method


def should_auto_link(confidence: float) -> bool:
    """Returns True if confidence is high enough to auto-link entities."""
    return confidence >= CONFIDENCE_THRESHOLD


def extract_ticker(text: str) -> Optional[str]:
    """Try to extract a stock ticker from text."""
    if not text:
        return None
    match = re.search(r"\(([A-Z]{1,5})\)", text)
    if match:
        return match.group(1)
    return None

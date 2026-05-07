"""Search router - full-text search across leads."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, text
from app.db import get_db
from app.models import Lead

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/leads")
def search_leads(
    q: str = Query(..., min_length=2, description="Search query"),
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    trigger_category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Full-text search across lead cards."""
    query = db.query(Lead)

    # Text search across org_name, trigger_text, sales_angle, why_now
    search_filter = or_(
        Lead.org_name.ilike(f"%{q}%"),
        Lead.trigger_text.ilike(f"%{q}%"),
        Lead.sales_angle.ilike(f"%{q}%"),
        Lead.why_now.ilike(f"%{q}%"),
    )
    query = query.filter(search_filter)

    if source:
        query = query.filter(Lead.source == source)
    if min_score is not None:
        query = query.filter(Lead.opportunity_score >= min_score)

    query = query.order_by(desc(Lead.opportunity_score))
    total = query.count()
    results = query.offset(skip).limit(limit).all()

    return {
        "query": q,
        "total": total,
        "results": [
            {
                "id": str(lead.id),
                "org_name": lead.org_name,
                "source": lead.source,
                "trigger_categories": lead.trigger_categories,
                "forced_spend_categories": lead.forced_spend_categories,
                "opportunity_score": lead.opportunity_score,
                "sales_angle": lead.sales_angle,
                "why_now": lead.why_now,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            }
            for lead in results
        ],
    }


@router.get("/filters")
def get_filter_options(db: Session = Depends(get_db)):
    """Get available filter options for the UI."""
    sources = [r[0] for r in db.query(Lead.source).distinct().all()]
    return {
        "sources": sources,
        "trigger_categories": [
            "cybersecurity_incident", "material_weakness", "regulatory_investigation",
            "environmental_liability", "product_recall", "compliance_program",
            "litigation", "hipaa_privacy", "osha_safety",
        ],
        "score_ranges": [
            {"label": "High Priority (70+)", "min": 70},
            {"label": "Medium Priority (40-69)", "min": 40},
            {"label": "All Leads", "min": 0},
        ],
    }

"""Leads API router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.db import get_db
from app.models import Lead, Trigger, Organization

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("/")
def list_leads(
    skip: int = 0,
    limit: int = 50,
    min_score: Optional[int] = None,
    source: Optional[str] = None,
    trigger_category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List leads with filtering and pagination."""
    query = db.query(Lead)
    if min_score is not None:
        query = query.filter(Lead.opportunity_score >= min_score)
    if source:
        query = query.filter(Lead.source == source)
    query = query.order_by(desc(Lead.opportunity_score))
    total = query.count()
    leads = query.offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "results": [
            {
                "id": str(lead.id),
                "org_name": lead.org_name,
                "source": lead.source,
                "trigger_categories": lead.trigger_categories,
                "forced_spend_categories": lead.forced_spend_categories,
                "opportunity_score": lead.opportunity_score,
                "severity": lead.severity,
                "sales_angle": lead.sales_angle,
                "why_now": lead.why_now,
                "buyer_segments": lead.buyer_segments,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "external_id": lead.external_id,
            }
            for lead in leads
        ],
    }


@router.get("/{lead_id}")
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    """Get a specific lead card by ID."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {
        "id": str(lead.id),
        "org_name": lead.org_name,
        "source": lead.source,
        "external_id": lead.external_id,
        "trigger_categories": lead.trigger_categories,
        "trigger_text": lead.trigger_text,
        "forced_spend_categories": lead.forced_spend_categories,
        "opportunity_score": lead.opportunity_score,
        "severity": lead.severity,
        "sales_angle": lead.sales_angle,
        "why_now": lead.why_now,
        "buyer_segments": lead.buyer_segments,
        "ai_summary": lead.ai_summary,
        "source_url": lead.source_url,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


@router.get("/stats/summary")
def leads_summary(db: Session = Depends(get_db)):
    """Summary statistics for the leads dashboard."""
    total = db.query(func.count(Lead.id)).scalar()
    by_source = (
        db.query(Lead.source, func.count(Lead.id))
        .group_by(Lead.source)
        .all()
    )
    avg_score = db.query(func.avg(Lead.opportunity_score)).scalar()
    high_priority = db.query(func.count(Lead.id)).filter(
        Lead.opportunity_score >= 70
    ).scalar()
    return {
        "total_leads": total,
        "high_priority_leads": high_priority,
        "avg_opportunity_score": round(float(avg_score or 0), 1),
        "by_source": {src: cnt for src, cnt in by_source},
    }

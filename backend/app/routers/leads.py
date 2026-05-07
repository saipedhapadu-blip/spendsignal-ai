"""Leads API router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db import get_db
from app.models import Lead

router = APIRouter()


@router.get("/")
async def list_leads(
    skip: int = 0,
    limit: int = 50,
    min_score: Optional[int] = None,
    source: Optional[str] = None,
    trigger_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List leads with filtering and pagination."""
    try:
        stmt = select(Lead)
        if min_score is not None:
            stmt = stmt.where(Lead.opportunity_score >= min_score)
        if source:
            stmt = stmt.where(Lead.source == source)
        stmt = stmt.order_by(desc(Lead.opportunity_score)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        leads = result.scalars().all()

        count_stmt = select(func.count(Lead.id))
        if min_score is not None:
            count_stmt = count_stmt.where(Lead.opportunity_score >= min_score)
        if source:
            count_stmt = count_stmt.where(Lead.source == source)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "results": [
                {
                    "id": str(lead.id),
                    "org_name": lead.org_name,
                    "source": lead.source,
                    "trigger_categories": lead.trigger_categories or [],
                    "forced_spend_categories": lead.forced_spend_categories or [],
                    "opportunity_score": lead.opportunity_score,
                    "severity": lead.severity,
                    "sales_angle": lead.sales_angle,
                    "why_now": lead.why_now,
                    "buyer_segments": lead.buyer_segments or [],
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                    "external_id": lead.external_id,
                }
                for lead in leads
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def leads_summary(db: AsyncSession = Depends(get_db)):
    """Leads Summary"""
    try:
        result = await db.execute(select(Lead))
        all_leads = result.scalars().all()
        total = len(all_leads)
        high_priority = sum(1 for l in all_leads if l.opportunity_score >= 70)
        avg_score = sum(l.opportunity_score for l in all_leads) / total if total > 0 else 0
        by_source: dict = {}
        for l in all_leads:
            by_source[l.source] = by_source.get(l.source, 0) + 1
        return {
            "total_leads": total,
            "high_priority_leads": high_priority,
            "avg_opportunity_score": avg_score,
            "by_source": by_source,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lead_id}")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific lead card by ID."""
    try:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return {
            "id": str(lead.id),
            "org_name": lead.org_name,
            "source": lead.source,
            "trigger_categories": lead.trigger_categories or [],
            "forced_spend_categories": lead.forced_spend_categories or [],
            "opportunity_score": lead.opportunity_score,
            "severity": lead.severity,
            "sales_angle": lead.sales_angle,
            "why_now": lead.why_now,
            "buyer_segments": lead.buyer_segments or [],
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "external_id": lead.external_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

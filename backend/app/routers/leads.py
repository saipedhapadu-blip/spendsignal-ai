"""Leads API router."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db import get_db
from app.models import Lead

router = APIRouter()


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Return dashboard summary stats."""
    try:
        total_result = await db.execute(select(func.count(Lead.id)))
        total = total_result.scalar() or 0

        high_result = await db.execute(
            select(func.count(Lead.id)).where(Lead.opportunity_score >= 70)
        )
        high = high_result.scalar() or 0

        avg_result = await db.execute(select(func.avg(Lead.opportunity_score)))
        avg_score = float(avg_result.scalar() or 0)

        src_result = await db.execute(
            select(Lead.source, func.count(Lead.id)).group_by(Lead.source)
        )
        by_source = {row[0]: row[1] for row in src_result.fetchall()}

        return {
            "total_leads": total,
            "high_priority_leads": high,
            "avg_opportunity_score": round(avg_score, 1),
            "by_source": by_source,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_leads(
    skip: int = 0,
    limit: int = 50,
    offset: int = 0,
    min_score: Optional[int] = None,
    source: Optional[str] = None,
    trigger_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List leads with filtering and pagination."""
    try:
        # Use offset param if provided (frontend sends offset directly)
        actual_skip = offset if offset else skip

        stmt = select(Lead)
        count_stmt = select(func.count(Lead.id))

        if min_score is not None:
            stmt = stmt.where(Lead.opportunity_score >= min_score)
            count_stmt = count_stmt.where(Lead.opportunity_score >= min_score)
        if source:
            stmt = stmt.where(Lead.source == source)
            count_stmt = count_stmt.where(Lead.source == source)

        stmt = stmt.order_by(desc(Lead.opportunity_score)).offset(actual_skip).limit(limit)
        result = await db.execute(stmt)
        leads = result.scalars().all()

        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        return {
            "leads": [
                {
                    "id": str(lead.id),
                    "org_name": lead.org_name or "",
                    "source": lead.source or "",
                    "trigger_categories": lead.trigger_categories or [],
                    "forced_spend_categories": lead.forced_spend_categories or [],
                    "opportunity_score": lead.opportunity_score or 0,
                    "severity": str(lead.severity) if lead.severity else "",
                    "sales_angle": lead.sales_angle or "",
                    "why_now": lead.why_now or "",
                    "buyer_segments": lead.buyer_segments or [],
                    "created_at": str(lead.created_at) if lead.created_at else "",
                    "external_id": lead.external_id or "",
                }
                for lead in leads
            ],
            "total": total,
            "skip": actual_skip,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lead_id}")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single lead by ID."""
    try:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return {
            "id": str(lead.id),
            "org_name": lead.org_name or "",
            "source": lead.source or "",
            "trigger_categories": lead.trigger_categories or [],
            "forced_spend_categories": lead.forced_spend_categories or [],
            "opportunity_score": lead.opportunity_score or 0,
            "severity": str(lead.severity) if lead.severity else "",
            "sales_angle": lead.sales_angle or "",
            "why_now": lead.why_now or "",
            "buyer_segments": lead.buyer_segments or [],
            "created_at": str(lead.created_at) if lead.created_at else "",
            "external_id": lead.external_id or "",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

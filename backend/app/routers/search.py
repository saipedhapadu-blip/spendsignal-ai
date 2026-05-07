"""Search router - full-text search across leads."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
from app.db import get_db
from app.models import Lead

router = APIRouter()


@router.get("/leads")
async def search_leads(
    q: str = Query(..., min_length=1, description="Search query"),
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across lead cards."""
    try:
        stmt = select(Lead).where(
            or_(
                Lead.org_name.ilike(f"%{q}%"),
                Lead.sales_angle.ilike(f"%{q}%"),
                Lead.why_now.ilike(f"%{q}%"),
            )
        )
        if source:
            stmt = stmt.where(Lead.source == source)
        if min_score is not None:
            stmt = stmt.where(Lead.opportunity_score >= min_score)
        stmt = stmt.order_by(desc(Lead.opportunity_score)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        results = result.scalars().all()
        return {
            "query": q,
            "total": len(results),
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
                }
                for lead in results
            ],
        }
    except Exception as e:
        return {"query": q, "total": 0, "results": [], "error": str(e)}

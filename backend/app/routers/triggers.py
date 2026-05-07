from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.db import get_db
from app.models import Trigger

router = APIRouter()


@router.get("/")
async def list_triggers(
    skip: int = 0,
    limit: int = 50,
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all extracted regulatory triggers with optional filtering."""
    try:
        query = select(Trigger).order_by(desc(Trigger.extracted_at))
        if category:
            query = query.where(Trigger.category == category)
        if severity:
            query = query.where(Trigger.severity == severity)
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        triggers = result.scalars().all()
        return {"triggers": [t.__dict__ for t in triggers], "count": len(triggers)}
    except Exception as e:
        return {"triggers": [], "count": 0, "message": str(e)}


@router.get("/{trigger_id}")
async def get_trigger(
    trigger_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single trigger by ID."""
    result = await db.execute(select(Trigger).where(Trigger.id == trigger_id))
    trigger = result.scalar_one_or_none()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return trigger.__dict__

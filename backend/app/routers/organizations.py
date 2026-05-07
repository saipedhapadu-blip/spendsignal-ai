from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional
from app.db import get_db
from app.models import Organization

router = APIRouter()


@router.get("/")
async def list_organizations(
    skip: int = 0,
    limit: int = 50,
    name: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations with optional filtering."""
    try:
        query = select(Organization).order_by(desc(Organization.created_at))
        if name:
            query = query.where(Organization.name.ilike(f"%{name}%"))
        if industry:
            query = query.where(Organization.industry == industry)
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        orgs = result.scalars().all()
        return {"organizations": [o.__dict__ for o in orgs], "count": len(orgs)}
    except Exception as e:
        return {"organizations": [], "count": 0, "message": str(e)}


@router.get("/{org_id}")
async def get_organization(
    org_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single organization by ID."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org.__dict__

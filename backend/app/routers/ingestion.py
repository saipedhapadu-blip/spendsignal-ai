"""Ingestion router - triggers data source ingestion and lead generation."""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models import Lead, RawRecord
from app.trigger_engine import extract_triggers, score_opportunity

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_lead_from_record(record: dict, source: str) -> Optional[dict]:
    """Build a lead dict from a normalized record."""
    text = " ".join([
        str(record.get("description", "") or ""),
        str(record.get("trigger_text", "") or ""),
        str(record.get("reason_for_recall", "") or ""),
        str(record.get("title", "") or ""),
    ])
    triggers = extract_triggers(text)
    if not triggers:
        return None
    score = score_opportunity(triggers, source)
    if score < 20:
        return None
    categories = list({c for t in triggers for c in t.get("forced_spend_categories", [])})
    trigger_cats = list({t["category"] for t in triggers})
    severity = max(t.get("severity", 0) for t in triggers)
    org_name = (
        record.get("recalling_firm") or record.get("recipient_name")
        or record.get("facility_name") or record.get("company_name")
        or record.get("department") or "Unknown"
    )
    sales_angle_map = {
        "cybersecurity_incident": "Offer cybersecurity incident response or security assessment.",
        "material_weakness": "Offer internal audit, SOX compliance, or GRC software.",
        "regulatory_investigation": "Offer regulatory counsel or compliance consulting.",
        "environmental_liability": "Offer environmental remediation or EHS consulting.",
        "product_recall": "Offer QMS software or quality/regulatory consulting.",
        "hipaa_privacy": "Offer HIPAA consulting or healthcare privacy software.",
        "osha_safety": "Offer safety consulting or EHS management software.",
        "litigation": "Offer eDiscovery or legal process management services.",
        "compliance_program": "Offer GRC software or compliance consulting.",
    }
    primary_cat = trigger_cats[0] if trigger_cats else ""
    return {
        "org_name": org_name,
        "source": source,
        "trigger_categories": trigger_cats,
        "forced_spend_categories": categories,
        "opportunity_score": score,
        "severity": severity,
        "sales_angle": sales_angle_map.get(primary_cat, "Offer relevant compliance or risk management services."),
        "trigger_details": triggers[:3],
    }


async def _run_sec_ingestion():
    """Background task: ingest SEC EDGAR filings."""
    try:
        from app.connectors.sec_edgar import SECEDGARConnector
        connector = SECEDGARConnector()
        records = await connector.fetch_recent_filings()
        logger.info(f"SEC ingestion: fetched {len(records)} records")
    except Exception as e:
        logger.error(f"SEC ingestion error: {e}")


async def _run_openfda_ingestion():
    """Background task: ingest openFDA recalls."""
    try:
        from app.connectors.openfda import OpenFDAConnector
        connector = OpenFDAConnector()
        records = await connector.fetch_recent_recalls()
        logger.info(f"openFDA ingestion: fetched {len(records)} records")
    except Exception as e:
        logger.error(f"openFDA ingestion error: {e}")


async def _run_epa_ingestion():
    """Background task: ingest EPA ECHO violations."""
    try:
        from app.connectors.epa_echo import EPAECHOConnector
        connector = EPAECHOConnector()
        records = await connector.fetch_recent_violations()
        logger.info(f"EPA ingestion: fetched {len(records)} records")
    except Exception as e:
        logger.error(f"EPA ingestion error: {e}")


async def _run_sam_ingestion():
    """Background task: ingest SAM.gov opportunities."""
    try:
        from app.connectors.sam_gov import SAMGovConnector
        connector = SAMGovConnector()
        records = await connector.fetch_opportunities()
        logger.info(f"SAM.gov ingestion: fetched {len(records)} records")
    except Exception as e:
        logger.error(f"SAM.gov ingestion error: {e}")


async def _run_usaspending_ingestion():
    """Background task: ingest USAspending awards."""
    try:
        from app.connectors.usaspending import USASpendingConnector
        connector = USASpendingConnector()
        records = await connector.fetch_recent_awards()
        logger.info(f"USAspending ingestion: fetched {len(records)} records")
    except Exception as e:
        logger.error(f"USAspending ingestion error: {e}")


@router.post("/trigger/{source}")
async def trigger_ingestion(
    source: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger ingestion for a data source."""
    source_map = {
        "sec_edgar": _run_sec_ingestion,
        "openfda": _run_openfda_ingestion,
        "epa_echo": _run_epa_ingestion,
        "sam_gov": _run_sam_ingestion,
        "usaspending": _run_usaspending_ingestion,
    }
    if source not in source_map:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}. Valid: {list(source_map.keys())}")
    background_tasks.add_task(source_map[source])
    return {"status": "started", "source": source, "message": f"Ingestion for {source} started in background"}


@router.post("/trigger-all")
async def trigger_all_ingestion(background_tasks: BackgroundTasks):
    """Trigger ingestion for all data sources."""
    for fn in [_run_sec_ingestion, _run_openfda_ingestion, _run_epa_ingestion, _run_sam_ingestion, _run_usaspending_ingestion]:
        background_tasks.add_task(fn)
    return {"status": "started", "message": "All ingestion tasks started in background"}


@router.get("/status")
async def ingestion_status(db: AsyncSession = Depends(get_db)):
    """Get ingestion run status."""
    try:
        result = await db.execute(select(RawRecord).limit(1))
        count_result = await db.execute(select(RawRecord))
        raw_records = count_result.scalars().all()
        return {"status": "ok", "raw_records_count": len(raw_records)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

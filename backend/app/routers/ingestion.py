"""Ingestion router - triggers data source ingestion and lead generation."""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db, AsyncSessionLocal
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
        str(record.get("subject", "") or ""),
        str(record.get("naics_description", "") or ""),
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
        or record.get("department") or record.get("awardee_name")
        or record.get("entity_name") or "Unknown"
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
    why_now = f"Recent {source.replace('_', ' ')} activity detected: {', '.join(trigger_cats[:2])}."
    return {
        "org_name": org_name,
        "source": source,
        "trigger_categories": trigger_cats,
        "forced_spend_categories": categories,
        "opportunity_score": score,
        "severity": severity,
        "sales_angle": sales_angle_map.get(primary_cat, "Offer relevant compliance or risk management services."),
        "why_now": why_now,
        "buyer_segments": ["compliance_vendors", "cybersecurity_vendors", "legal_firms"],
        "external_id": record.get("id") or record.get("recall_number") or record.get("award_id") or "",
    }


async def _ingest_and_save(source: str, fetch_fn):
    """Fetch records from a connector and save leads to DB."""
    try:
        records = await fetch_fn()
        logger.info(f"{source}: fetched {len(records)} records")
        saved = 0
        async with AsyncSessionLocal() as db:
            for record in records:
                try:
                    lead_data = _build_lead_from_record(record, source)
                    if not lead_data:
                        continue
                    # Check for duplicate by external_id
                    ext_id = lead_data.get("external_id", "")
                    if ext_id:
                        existing = await db.execute(
                            select(Lead).where(Lead.external_id == ext_id)
                        )
                        if existing.scalar_one_or_none():
                            continue
                    lead = Lead(
                        org_name=lead_data["org_name"],
                        source=lead_data["source"],
                        trigger_categories=lead_data["trigger_categories"],
                        forced_spend_categories=lead_data["forced_spend_categories"],
                        opportunity_score=lead_data["opportunity_score"],
                        severity=lead_data["severity"],
                        sales_angle=lead_data["sales_angle"],
                        why_now=lead_data["why_now"],
                        buyer_segments=lead_data["buyer_segments"],
                        external_id=ext_id or None,
                        created_at=datetime.utcnow(),
                    )
                    db.add(lead)
                    saved += 1
                except Exception as rec_err:
                    logger.warning(f"{source} record error: {rec_err}")
            await db.commit()
        logger.info(f"{source}: saved {saved} leads")
    except Exception as e:
        logger.error(f"{source} ingestion error: {e}")


async def _run_sec_ingestion():
    from app.connectors.sec_edgar import SECEDGARConnector
    c = SECEDGARConnector()
    await _ingest_and_save("sec_edgar", c.fetch_recent_filings)

async def _run_openfda_ingestion():
    from app.connectors.openfda import OpenFDAConnector
    c = OpenFDAConnector()
    await _ingest_and_save("openfda", c.fetch_recent_recalls)

async def _run_epa_ingestion():
    from app.connectors.epa_echo import EPAECHOConnector
    c = EPAECHOConnector()
    await _ingest_and_save("epa_echo", c.fetch_recent_violations)

async def _run_sam_ingestion():
    from app.connectors.sam_gov import SAMGovConnector
    c = SAMGovConnector()
    await _ingest_and_save("sam_gov", c.fetch_opportunities)

async def _run_usaspending_ingestion():
    from app.connectors.usaspending import USASpendingConnector
    c = USASpendingConnector()
    await _ingest_and_save("usaspending", c.fetch_recent_awards)


@router.post("/run/{source}")
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


@router.post("/trigger/{source}")
async def trigger_ingestion_legacy(
    source: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Legacy trigger endpoint."""
    return await trigger_ingestion(source, background_tasks, db)


@router.post("/trigger-all")
async def trigger_all_ingestion(background_tasks: BackgroundTasks):
    """Trigger ingestion for all data sources."""
    for fn in [_run_sec_ingestion, _run_openfda_ingestion, _run_epa_ingestion,
               _run_sam_ingestion, _run_usaspending_ingestion]:
        background_tasks.add_task(fn)
    return {"status": "started", "message": "All ingestion tasks started in background"}


@router.get("/status")
async def ingestion_status(db: AsyncSession = Depends(get_db)):
    """Get ingestion run status."""
    try:
        result = await db.execute(select(Lead))
        leads = result.scalars().all()
        raw_result = await db.execute(select(RawRecord))
        raw_records = raw_result.scalars().all()
        return {"status": "ok", "leads_count": len(leads), "raw_records_count": len(raw_records)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

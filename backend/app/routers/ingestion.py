"""Ingestion router - triggers data source ingestion and lead generation."""
import logging
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db, AsyncSessionLocal
from app.models import Lead
from app.trigger_engine import extract_triggers, score_opportunity

logger = logging.getLogger(__name__)
router = APIRouter()

# Track running ingestion jobs
_running_jobs = {}


def _build_lead_from_record(record: dict, source: str) -> Optional[dict]:
    """Build a lead dict from a normalized record."""
    # Gather text for trigger extraction
    text = " ".join([
        str(record.get("description", "") or ""),
        str(record.get("trigger_text", "") or ""),
        str(record.get("reason_for_recall", "") or ""),
        str(record.get("title", "") or ""),
        str(record.get("subject", "") or ""),
        str(record.get("naics_description", "") or ""),
        str(record.get("violation_types", "") or ""),
        str(record.get("classification", "") or ""),
        str(record.get("product_description", "") or ""),
    ])
    triggers = extract_triggers(text)
    # Also check if connector already identified trigger categories
    if not triggers and record.get("trigger_categories"):
        cats = record["trigger_categories"]
        if isinstance(cats, list):
            triggers = [{"category": c, "severity": 5, "keywords": []} for c in cats]
        elif isinstance(cats, str) and cats:
            triggers = [{"category": cats, "severity": 5, "keywords": []}]
    if not triggers:
        return None
    score = score_opportunity(triggers, source)
    if score < 15:
        return None

    trigger_cats = list({t.get("category") for t in triggers})
    severity_vals = [t.get("severity", 0) for t in triggers]
    severity_map = {0: "low", 1: "low", 2: "low", 3: "medium", 4: "medium",
                    5: "medium", 6: "high", 7: "high", 8: "critical",
                    9: "critical", 10: "critical"}
    max_sev = max(severity_vals) if severity_vals else 0
    severity = severity_map.get(max_sev, "medium")

    # Determine org name from various fields
    org_name = (
        record.get("company_name") or
        record.get("recalling_firm") or
        record.get("facility_name") or
        record.get("entity_name") or
        record.get("org_name") or
        "Unknown Organization"
    )

    # Forced-spend categories mapping
    cat_to_spend = {
        "FDA_RECALL": ["Quality Management System", "Regulatory Compliance", "Food Safety"],
        "FDA_WARNING_SIGNAL": ["GMP Compliance", "Quality Assurance", "Regulatory Consulting"],
        "EPA_VIOLATION": ["Environmental Remediation", "Environmental Compliance", "EHS Software"],
        "SEC_CYBERSECURITY": ["Cybersecurity", "Incident Response", "Compliance"],
        "SEC_REGULATORY": ["Regulatory Compliance", "Legal", "Audit"],
        "SEC_MATERIAL_WEAKNESS": ["Internal Controls", "Audit", "GRC Software"],
        "SEC_LITIGATION": ["Legal Services", "Risk Management"],
        "air_violation": ["Environmental Compliance", "Air Quality Monitoring"],
        "water_violation": ["Water Treatment", "Environmental Compliance"],
        "hazardous_waste": ["Hazardous Waste Management", "Environmental Services"],
        "significant_noncompliance": ["Environmental Compliance", "EHS Software"],
        "formal_enforcement": ["Environmental Legal", "Remediation Services"],
    }
    forced_spend = []
    for cat in trigger_cats:
        forced_spend.extend(cat_to_spend.get(cat, ["Compliance", "Risk Management"]))
    forced_spend = list(set(forced_spend))

    buyer_segs = ["Compliance Consultants", "Legal Firms", "Audit Firms"]
    if any("cyber" in c.lower() or "sec" in c.lower() for c in trigger_cats):
        buyer_segs.append("Cybersecurity Vendors")
    if any("epa" in c.lower() or "environ" in c.lower() or "violation" in c.lower() for c in trigger_cats):
        buyer_segs.extend(["Environmental Remediation Companies", "EHS Software Vendors"])
    if any("fda" in c.lower() or "recall" in c.lower() for c in trigger_cats):
        buyer_segs.extend(["QMS Software Vendors", "Regulatory Consultants"])

    external_id = record.get("external_id") or record.get("content_hash") or f"{source}_{org_name[:30]}"

    return {
        "org_name": org_name,
        "source": source,
        "trigger_categories": trigger_cats,
        "forced_spend_categories": forced_spend,
        "opportunity_score": score,
        "severity": severity,
        "sales_angle": f"This organization may need {', '.join(forced_spend[:2])} solutions due to recent {source} activity.",
        "why_now": f"Recent {source} signals indicate potential compliance and regulatory spending needs.",
        "buyer_segments": list(set(buyer_segs)),
        "external_id": external_id,
    }


async def _save_leads(records: List[dict], source: str):
    """Save leads to database from normalized records."""
    saved = 0
    skipped = 0
    errors = 0
    async with AsyncSessionLocal() as session:
        try:
            for record in records:
                try:
                    lead_data = _build_lead_from_record(record, source)
                    if not lead_data:
                        skipped += 1
                        continue
                    # Check for duplicate by external_id
                    existing = await session.execute(
                        select(Lead).where(Lead.external_id == lead_data["external_id"])
                    )
                    if existing.scalar_one_or_none():
                        skipped += 1
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
                        external_id=lead_data["external_id"],
                        created_at=datetime.utcnow(),
                    )
                    session.add(lead)
                    saved += 1
                except Exception as e:
                    logger.error(f"Error processing record: {e}")
                    errors += 1
            await session.commit()
            logger.info(f"[{source}] Saved {saved}, skipped {skipped}, errors {errors}")
        except Exception as e:
            await session.rollback()
            logger.error(f"[{source}] DB commit failed: {e}")


async def _run_openfda_ingestion():
    """Run openFDA ingestion using the connector."""
    try:
        from app.connectors.openfda import OpenFDAConnector
        logger.info("Starting openFDA ingestion...")
        connector = OpenFDAConnector()
        records = connector.ingest_all(limit_per_type=100)
        logger.info(f"openFDA fetched {len(records)} records")
        await _save_leads(records, "openfda")
    except Exception as e:
        logger.error(f"openFDA ingestion error: {e}")


async def _run_epa_ingestion():
    """Run EPA ECHO ingestion using the connector."""
    try:
        from app.connectors.epa_echo import EPAECHOConnector
        logger.info("Starting EPA ECHO ingestion...")
        connector = EPAECHOConnector()
        # Use asyncio to run the sync ingest_all in executor
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(None, lambda: connector.ingest_all(limit_per_state=50))
        logger.info(f"EPA ECHO fetched {len(records)} records")
        await _save_leads(records, "epa_echo")
    except Exception as e:
        logger.error(f"EPA ECHO ingestion error: {e}")


async def _run_sec_ingestion():
    """Run SEC EDGAR ingestion - fetch recent filings for a set of high-profile CIKs."""
    try:
        from app.connectors.sec_edgar import SECEDGARConnector
        logger.info("Starting SEC EDGAR ingestion...")
        connector = SECEDGARConnector()
        # Sample of well-known CIKs for companies likely to have trigger filings
        sample_ciks = [
            "0000789019",  # Microsoft
            "0001018724",  # Amazon
            "0000320193",  # Apple
            "0001326801",  # Meta
            "0001652044",  # Alphabet
            "0000080661",  # Pfizer
            "0000078003",  # Johnson & Johnson
            "0000034088",  # ExxonMobil
            "0000101830",  # Chevron
            "0000021344",  # Coca-Cola
        ]
        all_records = []
        loop = asyncio.get_event_loop()
        for cik in sample_ciks:
            try:
                records = await loop.run_in_executor(
                    None, lambda c=cik: connector.ingest_filings_for_cik(c)
                )
                all_records.extend(records)
                await asyncio.sleep(0.5)  # rate limit
            except Exception as e:
                logger.error(f"SEC CIK {cik} error: {e}")
        logger.info(f"SEC EDGAR fetched {len(all_records)} records")
        await _save_leads(all_records, "sec_edgar")
    except Exception as e:
        logger.error(f"SEC EDGAR ingestion error: {e}")


async def _run_background_ingestion(source: str):
    """Dispatch ingestion by source name."""
    _running_jobs[source] = {"status": "running", "started_at": datetime.utcnow().isoformat()}
    try:
        if source == "openfda":
            await _run_openfda_ingestion()
        elif source == "epa_echo":
            await _run_epa_ingestion()
        elif source == "sec_edgar":
            await _run_sec_ingestion()
        else:
            logger.warning(f"Unknown source: {source}")
        _running_jobs[source] = {"status": "completed", "completed_at": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Ingestion job {source} failed: {e}")
        _running_jobs[source] = {"status": "failed", "error": str(e)}


@router.post("/run/{source}")
async def trigger_ingestion(
    source: str,
    background_tasks: BackgroundTasks,
):
    """Manually trigger ingestion for a data source."""
    valid_sources = ["openfda", "epa_echo", "sec_edgar", "sam_gov", "usaspending"]
    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Valid: {valid_sources}"
        )
    background_tasks.add_task(_run_background_ingestion, source)
    return {"status": "started", "source": source, "message": f"Ingestion for {source} started in background"}


@router.post("/trigger/{source}")
async def trigger_ingestion_legacy(
    source: str,
    background_tasks: BackgroundTasks,
):
    """Legacy endpoint - same as /run/{source}."""
    return await trigger_ingestion(source, background_tasks)


@router.post("/trigger-all")
async def trigger_all_ingestion(background_tasks: BackgroundTasks):
    """Trigger all ingestion sources."""
    sources = ["openfda", "epa_echo", "sec_edgar"]
    for source in sources:
        background_tasks.add_task(_run_background_ingestion, source)
    return {"status": "started", "sources": sources, "message": "All ingestion jobs started in background"}


@router.get("/status")
async def ingestion_status():
    """Get ingestion job status."""
    return {"jobs": _running_jobs}

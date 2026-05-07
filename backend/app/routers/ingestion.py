"""Ingestion router - triggers data source ingestion and lead generation."""
import logging
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models import Lead
from app.trigger_engine import extract_triggers, score_opportunity

logger = logging.getLogger(__name__)
router = APIRouter()

_running_jobs = {}


def _build_lead_from_record(record: dict, source: str) -> Optional[dict]:
    metadata = record.get("metadata") or {}
    parts = [
        str(record.get("raw_text", "") or ""),
        str(record.get("description", "") or ""),
        str(record.get("reason_for_recall", "") or ""),
        str(record.get("classification", "") or ""),
        str(record.get("title", "") or ""),
        str(metadata.get("classification", "") or ""),
        str(metadata.get("trigger_type", "") or ""),
        str(metadata.get("compliance_status", "") or ""),
    ]
    text = " ".join(p for p in parts if p.strip())
    triggers = extract_triggers(text) if text.strip() else []
    if not triggers:
        raw_trigger = metadata.get("trigger_type") or metadata.get("trigger_category")
        if raw_trigger:
            if isinstance(raw_trigger, list):
                triggers = [{"category": c, "severity": 5, "keywords": [], "method": "connector"} for c in raw_trigger if c]
            elif isinstance(raw_trigger, str) and raw_trigger.strip():
                triggers = [{"category": raw_trigger, "severity": 5, "keywords": [], "method": "connector"}]
    if not triggers:
        classification = metadata.get("classification") or record.get("classification") or ""
        if "Class I" in str(classification):
            triggers = [{"category": "FDA_RECALL", "severity": 9, "keywords": ["Class I"], "method": "connector"}]
        elif "Class II" in str(classification):
            triggers = [{"category": "FDA_RECALL", "severity": 6, "keywords": ["Class II"], "method": "connector"}]
        elif classification:
            triggers = [{"category": "FDA_RECALL", "severity": 4, "keywords": [], "method": "connector"}]
    if not triggers and source == "sec_edgar":
        kw = metadata.get("keywords") or record.get("keywords") or []
        if kw:
            triggers = [{"category": "SEC_REGULATORY", "severity": 5, "keywords": kw[:3], "method": "connector"}]
    if not triggers and (text.strip() or metadata):
        source_map = {"openfda": ("FDA_RECALL", 5), "epa_echo": ("EPA_VIOLATION", 5), "sec_edgar": ("SEC_REGULATORY", 4)}
        cat, sev = source_map.get(source, ("REGULATORY", 3))
        triggers = [{"category": cat, "severity": sev, "keywords": [], "method": "fallback"}]
    if not triggers:
        return None
    score = score_opportunity(triggers, source)
    if score < 5:
        return None
    trigger_cats = list({t.get("category") for t in triggers if t.get("category")})
    severity_vals = [t.get("severity", 0) for t in triggers]
    max_sev = max(severity_vals) if severity_vals else 0
    severity_map = {0: "low", 1: "low", 2: "low", 3: "medium", 4: "medium", 5: "medium", 6: "high", 7: "high", 8: "critical", 9: "critical", 10: "critical"}
    severity = severity_map.get(min(max_sev, 10), "medium")
    org_name = (
        record.get("company_name") or record.get("recalling_firm") or
        metadata.get("recalling_firm") or record.get("facility_name") or
        metadata.get("facility_name") or record.get("entity_name") or
        record.get("org_name") or metadata.get("company_name") or
        metadata.get("ticker") or "Unknown Organization"
    )
    cat_to_spend = {
        "FDA_RECALL": ["Quality Management System", "Regulatory Compliance", "Food Safety"],
        "EPA_VIOLATION": ["Environmental Remediation", "Environmental Compliance", "EHS Software"],
        "SEC_CYBERSECURITY": ["Cybersecurity", "Incident Response", "Compliance"],
        "SEC_REGULATORY": ["Regulatory Compliance", "Legal", "Audit"],
        "SEC_MATERIAL_WEAKNESS": ["Internal Controls", "Audit", "GRC Software"],
        "REGULATORY": ["Regulatory Compliance", "Risk Management"],
    }
    forced_spend = []
    for cat in trigger_cats:
        forced_spend.extend(cat_to_spend.get(cat, ["Compliance", "Risk Management"]))
    forced_spend = list(set(forced_spend)) or ["Compliance", "Risk Management"]
    buyer_segs = ["Compliance Consultants", "Legal Firms", "Audit Firms"]
    if any("cyber" in str(c).lower() for c in trigger_cats):
        buyer_segs.append("Cybersecurity Vendors")
    if any("epa" in str(c).lower() or "violation" in str(c).lower() for c in trigger_cats):
        buyer_segs.extend(["Environmental Remediation Companies", "EHS Software Vendors"])
    if any("fda" in str(c).lower() or "recall" in str(c).lower() for c in trigger_cats):
        buyer_segs.extend(["QMS Software Vendors", "Regulatory Consultants"])
    external_id = record.get("external_id") or record.get("content_hash") or f"{source}_{str(org_name)[:30]}"
    spend_str = ", ".join(forced_spend[:2]) if forced_spend else "compliance"
    return {
        "org_name": str(org_name)[:500],
        "source": source,
        "trigger_categories": trigger_cats,
        "forced_spend_categories": forced_spend,
        "opportunity_score": score,
        "severity": severity,
        "sales_angle": f"This organization may need {spend_str} solutions due to recent {source} regulatory activity.",
        "why_now": f"Recent {source} signals indicate potential compliance needs in {', '.join(trigger_cats[:2])}.",
        "buyer_segments": list(set(buyer_segs)),
        "external_id": external_id,
    }


async def _save_leads(records: List[dict], source: str) -> dict:
    saved = 0
    skipped = 0
    errors = 0
    no_triggers = 0
    async with AsyncSessionLocal() as session:
        try:
            for record in records:
                try:
                    lead_data = _build_lead_from_record(record, source)
                    if not lead_data:
                        no_triggers += 1
                        continue
                    existing = await session.execute(select(Lead).where(Lead.external_id == lead_data["external_id"]))
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
                    logger.error(f"Record error: {e}")
                    errors += 1
            await session.commit()
            logger.info(f"[{source}] saved={saved} skipped={skipped} no_triggers={no_triggers} errors={errors}")
        except Exception as e:
            await session.rollback()
            logger.error(f"[{source}] DB commit failed: {e}")
            raise
    return {"saved": saved, "skipped": skipped, "no_triggers": no_triggers, "errors": errors}


async def _run_openfda_ingestion() -> dict:
    try:
        from app.connectors.openfda import OpenFDAConnector
        connector = OpenFDAConnector()
        records = await asyncio.to_thread(connector.ingest_all, 100)
        stats = await _save_leads(records, "openfda")
        return {"fetched": len(records), **stats}
    except Exception as e:
        logger.error(f"openFDA error: {e}", exc_info=True)
        return {"error": str(e)}


async def _run_epa_ingestion() -> dict:
    try:
        from app.connectors.epa_echo import EPAECHOConnector
        connector = EPAECHOConnector()
        records = await asyncio.to_thread(connector.ingest_all)
        stats = await _save_leads(records, "epa_echo")
        return {"fetched": len(records), **stats}
    except Exception as e:
        logger.error(f"EPA error: {e}", exc_info=True)
        return {"error": str(e)}


async def _run_sec_ingestion() -> dict:
    try:
        from app.connectors.sec_edgar import SECEDGARConnector
        connector = SECEDGARConnector()
        sample_ciks = [
            "0000789019", "0001018724", "0000320193", "0001326801", "0001652044",
            "0000080661", "0000078003", "0000034088", "0000101830", "0000021344",
        ]
        all_records = []
        for cik in sample_ciks:
            try:
                recs = await asyncio.to_thread(connector.ingest_filings_for_cik, cik)
                if recs:
                    all_records.extend(recs)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"SEC CIK {cik} error: {e}")
        stats = await _save_leads(all_records, "sec_edgar")
        return {"fetched": len(all_records), **stats}
    except Exception as e:
        logger.error(f"SEC error: {e}", exc_info=True)
        return {"error": str(e)}


async def _run_background_ingestion(source: str):
    _running_jobs[source] = {"status": "running", "started_at": datetime.utcnow().isoformat()}
    try:
        if source == "openfda":
            result = await _run_openfda_ingestion()
        elif source == "epa_echo":
            result = await _run_epa_ingestion()
        elif source == "sec_edgar":
            result = await _run_sec_ingestion()
        else:
            result = {}
        _running_jobs[source] = {"status": "completed", "completed_at": datetime.utcnow().isoformat(), **result}
    except Exception as e:
        logger.error(f"Job {source} failed: {e}")
        _running_jobs[source] = {"status": "failed", "error": str(e)}


@router.post("/run/{source}")
async def trigger_ingestion(source: str, background_tasks: BackgroundTasks):
    valid = ["openfda", "epa_echo", "sec_edgar"]
    if source not in valid:
        raise HTTPException(400, detail=f"Unknown source. Valid: {valid}")
    background_tasks.add_task(_run_background_ingestion, source)
    return {"status": "started", "source": source}


@router.post("/trigger/{source}")
async def trigger_ingestion_legacy(source: str, background_tasks: BackgroundTasks):
    return await trigger_ingestion(source, background_tasks)


@router.post("/trigger-all")
async def trigger_all_ingestion(background_tasks: BackgroundTasks):
    sources = ["openfda", "epa_echo", "sec_edgar"]
    for s in sources:
        background_tasks.add_task(_run_background_ingestion, s)
    return {"status": "started", "sources": sources}


@router.post("/debug-run/{source}")
async def debug_run_ingestion(source: str):
    """Run ingestion synchronously and return detailed stats."""
    valid = ["openfda", "epa_echo", "sec_edgar"]
    if source not in valid:
        raise HTTPException(400, detail=f"Unknown source. Valid: {valid}")
    if source == "openfda":
        result = await _run_openfda_ingestion()
    elif source == "epa_echo":
        result = await _run_epa_ingestion()
    else:
        result = await _run_sec_ingestion()
    return {"source": source, "result": result}


@router.post("/test-save")
async def test_save_lead():
    """Test direct DB save."""
    try:
        async with AsyncSessionLocal() as session:
            test_lead = Lead(
                org_name="Test Organization Inc",
                source="test",
                trigger_categories=["TEST_TRIGGER"],
                forced_spend_categories=["Compliance"],
                opportunity_score=50,
                severity="medium",
                sales_angle="Test lead.",
                why_now="Testing DB write.",
                buyer_segments=["Compliance Consultants"],
                external_id=f"test_{datetime.utcnow().isoformat()}",
                created_at=datetime.utcnow(),
            )
            session.add(test_lead)
            await session.commit()
            await session.refresh(test_lead)
            return {"status": "success", "lead_id": test_lead.id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/status")
async def ingestion_status():
    return {"jobs": _running_jobs}

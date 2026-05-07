"""Ingestion router - triggers data source ingestion and lead generation."""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Lead, RawRecord
from app.trigger_engine import extract_triggers, score_opportunity
from app.connectors.sec_edgar import SECEdgarConnector
from app.connectors.openfda import OpenFDAConnector
from app.connectors.sam_gov import SAMGovConnector
from app.connectors.usaspending import USASpendingConnector
from app.connectors.epa_echo import EPAECHOConnector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _build_lead_from_record(record: dict, source: str, db: Session) -> Optional[Lead]:
    """Build and save a Lead from a normalized record."""
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

    # Determine org name
    org_name = (
        record.get("recalling_firm") or record.get("recipient_name")
        or record.get("facility_name") or record.get("company_name")
        or record.get("department") or "Unknown"
    )

    # Sales angle and why-now mapping
    sales_angle_map = {
        "cybersecurity_incident": "Offer cybersecurity incident response or security assessment.",
        "material_weakness": "Offer internal audit, SOX compliance, or GRC software.",
        "regulatory_investigation": "Offer regulatory counsel or compliance consulting.",
        "environmental_liability": "Offer environmental remediation or EHS consulting.",
        "product_recall": "Offer QMS software or quality/regulatory consulting.",
        "hipaa_privacy": "Offer HIPAA consulting or healthcare privacy software.",
        "osha_safety": "Offer safety consulting or EHS management software.",
        "litigation": "Offer eDiscovery or legal process management services.",
        "compliance_program": "Offer GRC software or compliance program consulting.",
    }
    primary_cat = trigger_cats[0] if trigger_cats else ""
    sales_angle = sales_angle_map.get(primary_cat, "Offer compliance or risk management solutions.")
    why_now = f"Recent {source.replace('_', ' ')} record indicates {primary_cat.replace('_', ' ')} issue."

    lead = Lead(
        org_name=org_name,
        source=source,
        external_id=record.get("external_id"),
        trigger_categories=trigger_cats,
        trigger_text=text[:2000],
        forced_spend_categories=categories,
        opportunity_score=score,
        severity=severity,
        sales_angle=sales_angle,
        why_now=why_now,
        buyer_segments=categories[:3],
        source_url=record.get("ui_link") or record.get("source_url"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(lead)
    return lead


def _run_ingestion(source: str, db: Session):
    """Background ingestion job for a given source."""
    try:
        if source == "sec_edgar":
            connector = SECEdgarConnector()
            records = connector.ingest_recent_filings()
        elif source == "openfda":
            connector = OpenFDAConnector()
            records = connector.ingest_all()
        elif source == "sam_gov":
            connector = SAMGovConnector()
            records = connector.ingest_all()
        elif source == "usaspending":
            connector = USASpendingConnector()
            records = connector.ingest_all()
        elif source == "epa_echo":
            connector = EPAECHOConnector()
            records = connector.ingest_all()
        else:
            logger.error(f"Unknown source: {source}")
            return

        leads_created = 0
        for record in records:
            try:
                raw = RawRecord(
                    source=source,
                    external_id=record.get("external_id"),
                    raw_data=record,
                    ingested_at=datetime.utcnow(),
                )
                db.add(raw)
                lead = _build_lead_from_record(record, source, db)
                if lead:
                    leads_created += 1
            except Exception as e:
                logger.error(f"Error processing record from {source}: {e}")
                continue

        db.commit()
        logger.info(f"Ingestion complete: {source} - {len(records)} records, {leads_created} leads")
    except Exception as e:
        db.rollback()
        logger.error(f"Ingestion failed for {source}: {e}")


@router.post("/run/{source}")
def trigger_ingestion(
    source: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger ingestion for a specific data source."""
    valid_sources = ["sec_edgar", "openfda", "sam_gov", "usaspending", "epa_echo"]
    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source. Valid: {valid_sources}"
        )
    background_tasks.add_task(_run_ingestion, source, db)
    return {"status": "started", "source": source}


@router.post("/run/all")
def trigger_all_ingestion(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger ingestion for all data sources."""
    sources = ["sec_edgar", "openfda", "sam_gov", "usaspending", "epa_echo"]
    for source in sources:
        background_tasks.add_task(_run_ingestion, source, db)
    return {"status": "started", "sources": sources}

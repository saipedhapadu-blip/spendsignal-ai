import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, Text, ForeignKey, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    organization = Column(String)
    role = Column(String, default="customer")
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataSource(Base):
    __tablename__ = "data_sources"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    source_type = Column(String, nullable=False)
    base_url = Column(String)
    update_frequency = Column(String)
    is_active = Column(Boolean, default=True)
    last_successful_run_at = Column(DateTime)
    last_failed_run_at = Column(DateTime)
    config_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False)
    status = Column(String, default="running")  # running, success, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_message = Column(Text)
    metadata_json = Column(JSON)


class RawRecord(Base):
    __tablename__ = "raw_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False)
    external_id = Column(String, nullable=False)
    source_url = Column(String)
    source_published_at = Column(DateTime)
    source_updated_at = Column(DateTime)
    raw_json = Column(JSON)
    raw_text = Column(Text)
    content_hash = Column(String, index=True)
    ingestion_run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name = Column(String, nullable=False)
    normalized_name = Column(String, index=True)
    entity_type = Column(String)  # public_company, private, government, facility
    ticker = Column(String, index=True)
    cik = Column(String, index=True)
    uei = Column(String, index=True)
    ein = Column(String)
    parent_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    website = Column(String)
    industry = Column(String)
    naics_codes = Column(ARRAY(String))
    headquarters_city = Column(String)
    headquarters_state = Column(String)
    headquarters_country = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Facility(Base):
    __tablename__ = "facilities"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    facility_name = Column(String, nullable=False)
    facility_registry_id = Column(String, index=True)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zip = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    industry = Column(String)
    source_ids = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Trigger(Base):
    __tablename__ = "triggers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_record_id = Column(UUID(as_uuid=True), ForeignKey("raw_records.id"))
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"))
    trigger_type = Column(String, nullable=False, index=True)
    trigger_category = Column(String)
    title = Column(String)
    description = Column(Text)
    event_date = Column(DateTime)
    severity = Column(String)  # low, medium, high, critical
    confidence = Column(Float)
    source_url = Column(String)
    evidence_text = Column(Text)
    extracted_entities = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class Lead(Base):
    __tablename__ = "leads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"))
    lead_title = Column(String)
    opportunity_type = Column(String)
    summary = Column(Text)
    urgency_score = Column(Float)
    severity_score = Column(Float)
    confidence_score = Column(Float)
    total_score = Column(Float, index=True)
    estimated_buying_window = Column(String)
    primary_forced_spend_category_id = Column(UUID(as_uuid=True))
    status = Column(String, default="new")  # new, contacted, qualified, closed
    assigned_to = Column(String)
    generated_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String)
    filters_json = Column(JSON)
    frequency = Column(String, default="daily")  # daily, weekly
    last_sent_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

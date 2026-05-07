import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db import Base


def gen_uuid():
    return str(uuid.uuid4())


class RawRecord(Base):
    __tablename__ = "raw_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=False, index=True)
    external_id = Column(String, nullable=True, index=True)
    raw_data = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


class Lead(Base):
    __tablename__ = "leads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_name = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, index=True)
    trigger_categories = Column(JSONB, default=list)
    forced_spend_categories = Column(JSONB, default=list)
    opportunity_score = Column(Float, default=0.0, index=True)
    severity = Column(Integer, default=0)
    sales_angle = Column(Text)
    why_now = Column(Text)
    buyer_segments = Column(JSONB, default=list)
    external_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

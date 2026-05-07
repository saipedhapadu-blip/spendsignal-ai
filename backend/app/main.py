from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from sqlalchemy import text

from app.db import engine, Base
from app.routers import leads, ingestion, search, auth, triggers, organizations

logger = logging.getLogger(__name__)

# Tables to force-drop before recreating (handles schema migrations)
DROP_TABLES = [
    "leads", "triggers", "organizations", "raw_records",
    "ingestion_runs", "data_sources", "users", "alerts",
    "facilities", "source_entity_links", "forced_spend_categories",
    "trigger_category_mappings", "lead_triggers", "buyer_segments",
    "lead_buyer_matches", "ai_enrichments", "saved_searches",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            # Force drop all known tables to handle schema changes
            for tbl in DROP_TABLES:
                try:
                    await conn.execute(text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE'))
                except Exception:
                    pass
            # Recreate with current schema
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema reset and recreated successfully")
    except Exception as e:
        logger.error(f"DB init error: {e}")
    yield


app = FastAPI(
    title="SpendSignal AI",
    description="AI-powered B2B regulatory forced-spend intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(triggers.router, prefix="/api/triggers", tags=["triggers"])
app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(ingestion.router, prefix="/api/ingestion", tags=["ingestion"])
app.include_router(search.router, prefix="/api/search", tags=["search"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "SpendSignal AI"}

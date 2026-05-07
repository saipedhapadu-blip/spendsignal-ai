from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.db import engine, Base
from app.routers import leads, ingestion, search, auth, triggers, organizations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Drop and recreate all tables to apply schema changes
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables recreated successfully")
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

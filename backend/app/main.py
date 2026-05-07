from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.db import engine, Base
from app.routers import leads, ingestion, search, auth, triggers, organizations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            # Only create tables that don't exist - never drop existing data
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured successfully")
    except Exception as e:
        logger.error(f"Database init error: {e}")
    yield
    await engine.dispose()


app = FastAPI(
    title="SpendSignal AI",
    description="Regulatory Forced-Spend Intelligence Platform",
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

app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(ingestion.router, prefix="/api/ingestion", tags=["ingestion"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(triggers.router, prefix="/api/triggers", tags=["triggers"])
app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])


@app.get("/")
async def root():
    return {"message": "SpendSignal AI API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}

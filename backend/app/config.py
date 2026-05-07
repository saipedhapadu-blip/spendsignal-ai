from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://spendsignal:spendsignal_secret@localhost:5432/spendsignal"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # SEC EDGAR
    SEC_USER_AGENT: str = "SpendSignalAI contact@example.com"
    SEC_RATE_LIMIT: float = 0.1  # seconds between requests
    
    # SAM.gov
    SAM_API_KEY: Optional[str] = None
    SAM_BASE_URL: str = "https://api.sam.gov/opportunities/v2"
    
    # USAspending
    USASPENDING_BASE_URL: str = "https://api.usaspending.gov/api/v2"
    
    # EPA ECHO
    EPA_ECHO_BASE_URL: str = "https://echo.epa.gov/system/files/downloads"
    
    # openFDA
    OPENFDA_BASE_URL: str = "https://api.fda.gov"
    
    # App
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

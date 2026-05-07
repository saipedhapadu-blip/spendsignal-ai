# SpendSignal AI

AI-powered B2B regulatory forced-spend intelligence platform.

## Overview

SpendSignal AI ingests public regulatory, procurement, enforcement, and disclosure datasets to identify organizations likely to spend money on compliance, remediation, cybersecurity, legal, audit, safety, quality, environmental, or risk-management solutions.

## Stack

- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Python FastAPI
- **Database**: PostgreSQL + pgvector
- **Queue**: Celery + Redis
- **Deployment**: Railway

## Data Sources

1. SEC EDGAR filings
2. SAM.gov contract opportunities
3. USAspending contract and award data
4. EPA ECHO enforcement/compliance data
5. FDA openFDA enforcement/recall data

## Getting Started

```bash
docker-compose up
```

## Environment Variables

See `.env.example` for required environment variables.

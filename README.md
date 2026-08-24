# Ad Spend Autopilot

A full-stack AI-assisted performance marketing platform.

## Features
- JWT login
- Live dashboard KPIs and charts
- Campaign creation and management
- Pause/resume campaigns
- Budget optimization with approval guardrails
- Human approval workflow
- Creative brief generation
- Attribution reporting
- Brand-safety checks
- PostgreSQL + Redis + Celery production architecture
- Docker deployment
- Google Ads and Meta integration adapter points

## Quick start
```bash
cp .env.example .env
docker compose up --build
```

Open:
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

Demo account:
- admin@adspend.local
- Admin@123

## Production
Use PostgreSQL, Redis, HTTPS, a secrets manager, official Google/Meta OAuth credentials,
audit logs, rate limiting and human approval for high-impact spend changes.

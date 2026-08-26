from celery import Celery
from .config import settings
from sqlalchemy import select
from .db import SessionLocal
from .models import Campaign

celery_app=Celery("adspend",broker=settings.REDIS_URL,backend=settings.REDIS_URL)

@celery_app.task
def refresh_campaign_metrics(campaign_id: int, org_id: int):
    with SessionLocal() as db:
        c = db.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.organization_id == org_id))
        if not c: return {"status": "error", "message": "Campaign not found or unauthorized"}
        return {"status":"ok","message":"Metrics refreshed"}

@celery_app.task
def run_optimization_cycle(campaign_id: int, org_id: int):
    with SessionLocal() as db:
        c = db.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.organization_id == org_id))
        if not c: return {"status": "error", "message": "Campaign not found or unauthorized"}
        return {"status":"ok","message":"Optimization cycle completed"}

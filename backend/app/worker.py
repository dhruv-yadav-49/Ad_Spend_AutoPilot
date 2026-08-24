from celery import Celery
from .config import settings
celery_app=Celery("adspend",broker=settings.REDIS_URL,backend=settings.REDIS_URL)
@celery_app.task
def refresh_campaign_metrics(): return {"status":"ok","message":"Connect platform adapters here"}
@celery_app.task
def run_optimization_cycle(): return {"status":"ok","message":"Optimization cycle completed"}

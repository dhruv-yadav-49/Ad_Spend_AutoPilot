from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
import logging
from typing import Dict, Any

from .models import AdPlatformConnection
from .credentials import CredentialService
from .providers import GoogleAdsClient, MetaAdsClient
from .schemas_unified import UnifiedCampaign, UnifiedMetrics, UnifiedCampaignsResponse, UnifiedMetricsResponse, PlatformStatus

logger = logging.getLogger(__name__)

class UnifiedReportingService:
    @staticmethod
    def _get_client(db: Session, platform: str, access_token: str):
        if platform == "google":
            return GoogleAdsClient(access_token)
        elif platform == "meta":
            return MetaAdsClient(access_token)
        return None

    @staticmethod
    def get_unified_campaigns(db: Session, organization_id: int) -> UnifiedCampaignsResponse:
        # Strictly use organization_id for scoped access
        connections = db.scalars(
            select(AdPlatformConnection)
            .where(
                AdPlatformConnection.organization_id == organization_id,
                AdPlatformConnection.status == "active"
            )
        ).all()
        
        unified_campaigns = []
        platforms_status = {
            "google": PlatformStatus(status="not_connected"),
            "meta": PlatformStatus(status="not_connected")
        }
        
        for conn in connections:
            if not conn.external_account_id:
                continue
                
            platform = conn.platform
            try:
                # get_access_token_and_customers strictly fetches for the given org
                access_token, valid_customers = CredentialService.get_access_token_and_customers(db, organization_id, platform)
                client = UnifiedReportingService._get_client(db, platform, access_token)
                
                raw_campaigns = client.list_campaigns(conn.external_account_id)
                
                for rc in raw_campaigns:
                    unified_campaigns.append(UnifiedCampaign(
                        id=f"{platform}_{rc['id']}",
                        platform=platform,
                        platform_campaign_id=str(rc["id"]),
                        platform_account_id=conn.external_account_id,
                        name=rc.get("name", "Unknown"),
                        status=rc.get("status", "UNKNOWN")
                    ))
                platforms_status[platform] = PlatformStatus(status="success")
            except Exception as e:
                logger.error(f"Failed to fetch campaigns for platform {platform}: {e}")
                platforms_status[platform] = PlatformStatus(status="failed", error=str(e))
                
        return UnifiedCampaignsResponse(data=unified_campaigns, platforms=platforms_status)

    @staticmethod
    def get_unified_metrics(db: Session, organization_id: int, start_date: str, end_date: str) -> UnifiedMetricsResponse:
        # Validate dates
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format, use YYYY-MM-DD")
            
        if end_dt < start_dt:
            raise ValueError("end_date must be after start_date")
            
        if (end_dt - start_dt).days > 90:
            raise ValueError("Date range cannot exceed 90 days")
            
        if end_dt > datetime.utcnow() or start_dt > datetime.utcnow():
            raise ValueError("Date range cannot be in the future")

        connections = db.scalars(
            select(AdPlatformConnection)
            .where(
                AdPlatformConnection.organization_id == organization_id,
                AdPlatformConnection.status == "active"
            )
        ).all()
        
        unified_metrics = []
        platforms_status = {
            "google": PlatformStatus(status="not_connected"),
            "meta": PlatformStatus(status="not_connected")
        }
        
        for conn in connections:
            if not conn.external_account_id:
                continue
                
            platform = conn.platform
            try:
                access_token, valid_customers = CredentialService.get_access_token_and_customers(db, organization_id, platform)
                client = UnifiedReportingService._get_client(db, platform, access_token)
                
                # We fetch overall account metrics for this date range
                raw_metrics = client.get_metrics(conn.external_account_id, start_date, end_date)
                
                impressions = raw_metrics.get("impressions", 0)
                clicks = raw_metrics.get("clicks", 0)
                cost_micros = raw_metrics.get("cost_micros", 0)
                conversions = raw_metrics.get("conversions", 0.0)
                
                ctr = (clicks / impressions) if impressions > 0 else None
                cpc = (cost_micros / clicks) if clicks > 0 else None
                roas = None  # Explicitly None per requirements
                
                unified_metrics.append(UnifiedMetrics(
                    platform=platform,
                    platform_campaign_id=None,  # Account-level aggregation for now
                    start_date=start_date,
                    end_date=end_date,
                    impressions=impressions,
                    clicks=clicks,
                    cost_micros=cost_micros,
                    conversions=conversions,
                    ctr=ctr,
                    cpc=cpc,
                    roas=roas
                ))
                platforms_status[platform] = PlatformStatus(status="success")
            except Exception as e:
                logger.error(f"Failed to fetch metrics for platform {platform}: {e}")
                platforms_status[platform] = PlatformStatus(status="failed", error=str(e))
                
        return UnifiedMetricsResponse(data=unified_metrics, platforms=platforms_status)

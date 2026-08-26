from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class UnifiedCampaign(BaseModel):
    id: str  # For now, unique ID can just be f"{platform}_{platform_campaign_id}"
    platform: str
    platform_campaign_id: str
    platform_account_id: str
    name: str
    status: str

class UnifiedMetrics(BaseModel):
    platform: str
    platform_campaign_id: Optional[str] = None
    start_date: str
    end_date: str
    impressions: int
    clicks: int
    cost_micros: int
    conversions: float
    ctr: Optional[float] = None
    cpc: Optional[float] = None
    roas: Optional[float] = None

class PlatformStatus(BaseModel):
    status: str
    error: Optional[str] = None

class UnifiedCampaignsResponse(BaseModel):
    data: List[UnifiedCampaign]
    platforms: Dict[str, PlatformStatus]

class UnifiedMetricsResponse(BaseModel):
    data: List[UnifiedMetrics]
    platforms: Dict[str, PlatformStatus]

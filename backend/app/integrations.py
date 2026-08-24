# Official API adapter interfaces. Add OAuth credentials from a secure secrets manager.
class GoogleAdsAdapter:
    async def fetch_campaigns(self): return []
    async def update_budget(self,campaign_id,amount): return {"status":"not_configured"}
class MetaMarketingAdapter:
    async def fetch_campaigns(self): return []
    async def update_budget(self,campaign_id,amount): return {"status":"not_configured"}


import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List
from .config import settings
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

class AdPlatformProvider(ABC):
    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        pass
        
    @abstractmethod
    def exchange_code(self, code: str) -> Tuple[str, str, datetime]:
        pass
        
    @abstractmethod
    def revoke_token(self, token: str):
        pass

class GoogleOAuthProvider(AdPlatformProvider):
    def get_authorization_url(self, state: str) -> str:
        if settings.GOOGLE_ADS_MOCK_MODE:
            return f"http://localhost:8000/platforms/callback?code=mock_google_code_123&state={state}"
        
        redirect_uri = "http://localhost:8000/platforms/callback"
        return f"https://accounts.google.com/o/oauth2/v2/auth?client_id={settings.GOOGLE_ADS_CLIENT_ID}&response_type=code&scope=https://www.googleapis.com/auth/adwords&redirect_uri={redirect_uri}&state={state}&access_type=offline&prompt=consent"
        
    def exchange_code(self, code: str) -> Tuple[str, str, datetime]:
        if settings.GOOGLE_ADS_MOCK_MODE:
            if code == "mock_google_code_123":
                return ("mock_google_access", "mock_google_refresh", datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1))
            raise ValueError("Invalid mock code")
            
        redirect_uri = "http://localhost:8000/platforms/callback"
        resp = httpx.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        })
        
        if resp.status_code != 200:
            logger.error(f"Google OAuth exchange failed: {resp.text}")
            raise ValueError("Failed to exchange code")
            
        data = resp.json()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=data.get("expires_in", 3600))
        return (data["access_token"], data.get("refresh_token"), expires_at)
        
    def revoke_token(self, token: str):
        if settings.GOOGLE_ADS_MOCK_MODE:
            return
        resp = httpx.post("https://oauth2.googleapis.com/revoke", data={"token": token})
        if resp.status_code != 200:
            logger.warning(f"Failed to revoke Google token: {resp.text}")

class MetaAdsProvider(AdPlatformProvider):
    def get_authorization_url(self, state: str) -> str:
        if settings.META_ADS_MOCK_MODE:
            return f"http://localhost:8000/platforms/callback?code=mock_meta_code_123&state={state}"
            
        redirect_uri = "http://localhost:8000/platforms/callback"
        base_url = f"https://www.facebook.com/{settings.META_GRAPH_API_VERSION}/dialog/oauth"
        return f"{base_url}?client_id={settings.META_ADS_CLIENT_ID}&redirect_uri={redirect_uri}&state={state}&scope=ads_management,ads_read"
        
    def exchange_code(self, code: str) -> Tuple[str, str, datetime]:
        if settings.META_ADS_MOCK_MODE:
            if code == "mock_meta_code_123":
                return ("mock_meta_access", "mock_meta_long_lived", datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=60))
            raise ValueError("Invalid mock code")
            
        redirect_uri = "http://localhost:8000/platforms/callback"
        
        # 1. Exchange short-lived token
        token_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/oauth/access_token"
        resp = httpx.get(token_url, params={
            "client_id": settings.META_ADS_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "client_secret": settings.META_ADS_CLIENT_SECRET,
            "code": code
        })
        
        if resp.status_code != 200:
            logger.error(f"Meta OAuth short-lived exchange failed: {resp.text}")
            raise ValueError("Failed to exchange code")
            
        short_token_data = resp.json()
        short_access_token = short_token_data["access_token"]
        
        # 2. Exchange for long-lived token
        ll_resp = httpx.get(token_url, params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.META_ADS_CLIENT_ID,
            "client_secret": settings.META_ADS_CLIENT_SECRET,
            "fb_exchange_token": short_access_token
        })
        
        if ll_resp.status_code != 200:
            logger.error(f"Meta OAuth long-lived exchange failed: {ll_resp.text}")
            raise ValueError("Failed to get long-lived token")
            
        ll_data = ll_resp.json()
        long_access_token = ll_data["access_token"]
        
        # Meta long-lived tokens typically expire in 60 days
        expires_in = ll_data.get("expires_in", 60 * 24 * 3600)
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)
        
        # Meta doesn't use refresh tokens in the same way, the long-lived token itself is what we store.
        # We'll store it as access_token. We can store it as refresh_token too for structure.
        return (long_access_token, long_access_token, expires_at)
        
    def revoke_token(self, token: str):
        if settings.META_ADS_MOCK_MODE:
            return
        revoke_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/me/permissions"
        resp = httpx.delete(revoke_url, params={"access_token": token})
        if resp.status_code != 200:
            logger.warning(f"Failed to revoke Meta token: {resp.text}")

def get_provider(platform: str) -> AdPlatformProvider:
    if platform == "google":
        return GoogleOAuthProvider()
    elif platform == "meta":
        return MetaAdsProvider()
    else:
        raise ValueError(f"Unsupported platform: {platform}")

def get_client(platform: str, access_token: str):
    if platform == "google":
        return GoogleAdsClient(access_token)
    elif platform == "meta":
        return MetaAdsClient(access_token)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

# Client abstraction for Phase 3B
class AdPlatformClient(ABC):
    @abstractmethod
    def list_accounts(self) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def list_campaigns(self, customer_id: str) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def get_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def get_metrics(self, customer_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def update_budget(self, customer_id: str, campaign_id: str, daily_budget_usd: float) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def pause_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def resume_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        pass

class GoogleAdsClient(AdPlatformClient):
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.client = None
        if not settings.GOOGLE_ADS_MOCK_MODE:
            try:
                from google.oauth2.credentials import Credentials
                from google.ads.googleads.client import GoogleAdsClient as GAClient
                from google.ads.googleads.errors import GoogleAdsException
                self.GoogleAdsException = GoogleAdsException
                creds = Credentials(token=self.access_token)
                self.client = GAClient(
                    credentials=creds, 
                    developer_token=settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                    version="v16"
                )
                if settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
                    self.client.login_customer_id = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
            except ImportError:
                raise RuntimeError("google-ads library not installed")

    def _handle_error(self, e):
        from fastapi import HTTPException
        if hasattr(self, 'GoogleAdsException') and isinstance(e, self.GoogleAdsException):
            logger.error(f"Google Ads API Error: {e.failure}")
            # Map standard Google errors to HTTP
            # For simplicity, returning 400 or 401
            raise HTTPException(status_code=400, detail="Google Ads API Error")
        elif "401" in str(e):
            raise HTTPException(status_code=401, detail="Unauthorized - token may be expired")
        elif "429" in str(e):
            raise HTTPException(status_code=429, detail="Rate limited by Google")
        raise HTTPException(status_code=500, detail="Upstream provider error")

    def list_accounts(self) -> List[Dict[str, Any]]:
        if settings.GOOGLE_ADS_MOCK_MODE:
            return [
                {"id": "mock_customer_123", "name": "Mock Org Account", "currency": "USD", "timezone": "UTC"}
            ]
            
        try:
            customer_service = self.client.get_service("CustomerService")
            accessible_customers = customer_service.list_accessible_customers()
            results = []
            for resource_name in accessible_customers.resource_names:
                customer_id = resource_name.split("/")[1]
                # To get name and currency, we would need to query each customer
                # For Phase 3C, we just return the ID to avoid complex multi-queries
                results.append({"id": customer_id, "name": f"Account {customer_id}", "currency": "USD", "timezone": "UTC"})
            return results
        except Exception as e:
            self._handle_error(e)

    def list_campaigns(self, customer_id: str) -> List[Dict[str, Any]]:
        if settings.GOOGLE_ADS_MOCK_MODE:
            return [
                {"id": "camp_1", "name": "Search - Brand", "status": "ENABLED"},
                {"id": "camp_2", "name": "Display - Retargeting", "status": "PAUSED"}
            ]
            
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = "SELECT campaign.id, campaign.name, campaign.status FROM campaign"
            request = self.client.get_type("SearchGoogleAdsRequest")
            request.customer_id = customer_id
            request.query = query
            
            response = ga_service.search(request=request)
            
            campaigns = []
            for row in response:
                status_name = row.campaign.status.name if hasattr(row.campaign.status, 'name') else str(row.campaign.status)
                campaigns.append({
                    "id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": status_name
                })
            return campaigns
        except Exception as e:
            self._handle_error(e)
            
    def get_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        if settings.GOOGLE_ADS_MOCK_MODE:
            if campaign_id == "camp_1":
                return {"id": "camp_1", "name": "Search - Brand", "status": "ENABLED"}
            return None
            
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.id = {campaign_id}"
            request = self.client.get_type("SearchGoogleAdsRequest")
            request.customer_id = customer_id
            request.query = query
            
            response = ga_service.search(request=request)
            for row in response:
                status_name = row.campaign.status.name if hasattr(row.campaign.status, 'name') else str(row.campaign.status)
                return {
                    "id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": status_name
                }
            return None
        except Exception as e:
            self._handle_error(e)

    def get_metrics(self, customer_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        if (end - start).days > 90:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Date range cannot exceed 90 days")
            
        if settings.GOOGLE_ADS_MOCK_MODE:
            return {
                "impressions": 15000,
                "clicks": 450,
                "cost_micros": 125500000,
                "conversions": 12
            }
            
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"""
                SELECT 
                    metrics.impressions, 
                    metrics.clicks, 
                    metrics.cost_micros, 
                    metrics.conversions 
                FROM campaign 
                WHERE segments.date >= '{start_date}' AND segments.date <= '{end_date}'
            """
            request = self.client.get_type("SearchGoogleAdsRequest")
            request.customer_id = customer_id
            request.query = query
            
            response = ga_service.search(request=request)
            
            totals = {
                "impressions": 0,
                "clicks": 0,
                "cost_micros": 0,
                "conversions": 0.0
            }
            
            for row in response:
                totals["impressions"] += row.metrics.impressions
                totals["clicks"] += row.metrics.clicks
                totals["cost_micros"] += row.metrics.cost_micros
                totals["conversions"] += row.metrics.conversions
                
            return totals
        except Exception as e:
            self._handle_error(e)

    def _mutate_campaign_status(self, customer_id: str, campaign_id: str, status_str: str) -> Dict[str, Any]:
        if settings.GOOGLE_ADS_MOCK_MODE:
            # We return mocked new state
            state = self.get_campaign(customer_id, campaign_id) or {"id": campaign_id, "name": "Mock Campaign"}
            state["status"] = status_str
            return state
            
        try:
            campaign_service = self.client.get_service("CampaignService")
            campaign_operation = self.client.get_type("CampaignOperation")
            
            # Use proper ENUM mapping depending on google ads client version
            # E.g., client.enums.CampaignStatusEnum.PAUSED
            status_enum = getattr(self.client.enums.CampaignStatusEnum, status_str)
            
            campaign = campaign_operation.update
            campaign.resource_name = campaign_service.campaign_path(customer_id, campaign_id)
            campaign.status = status_enum
            
            self.client.copy_from(
                campaign_operation.update_mask,
                self.client.get_type("FieldMask")
            )
            campaign_operation.update_mask.paths.append("status")
            
            campaign_service.mutate_campaigns(
                customer_id=customer_id, operations=[campaign_operation]
            )
            return self.get_campaign(customer_id, campaign_id)
        except Exception as e:
            self._handle_error(e)

    def pause_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        return self._mutate_campaign_status(customer_id, campaign_id, "PAUSED")

    def resume_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        return self._mutate_campaign_status(customer_id, campaign_id, "ENABLED")
        
    def update_budget(self, customer_id: str, campaign_id: str, daily_budget_usd: float) -> Dict[str, Any]:
        if settings.GOOGLE_ADS_MOCK_MODE:
            state = self.get_campaign(customer_id, campaign_id) or {"id": campaign_id, "name": "Mock Campaign"}
            state["daily_budget"] = daily_budget_usd
            return state
            
        try:
            # We need to find the budget resource_name for this campaign first
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"SELECT campaign.campaign_budget FROM campaign WHERE campaign.id = {campaign_id}"
            request = self.client.get_type("SearchGoogleAdsRequest")
            request.customer_id = customer_id
            request.query = query
            response = ga_service.search(request=request)
            
            budget_resource = None
            for row in response:
                budget_resource = row.campaign.campaign_budget
                break
                
            if not budget_resource:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Campaign budget resource not found")
                
            budget_service = self.client.get_service("CampaignBudgetService")
            budget_operation = self.client.get_type("CampaignBudgetOperation")
            
            budget = budget_operation.update
            budget.resource_name = budget_resource
            budget.amount_micros = int(daily_budget_usd * 1000000)
            
            self.client.copy_from(
                budget_operation.update_mask,
                self.client.get_type("FieldMask")
            )
            budget_operation.update_mask.paths.append("amount_micros")
            
            budget_service.mutate_campaign_budgets(
                customer_id=customer_id, operations=[budget_operation]
            )
            return self.get_campaign(customer_id, campaign_id)
        except Exception as e:
            self._handle_error(e)

class MetaAdsClient(AdPlatformClient):
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"

    def _handle_error(self, e: httpx.HTTPStatusError):
        from fastapi import HTTPException
        status = e.response.status_code
        logger.error(f"Meta API Error {status}: {e.response.text}")
        if status == 401:
            raise HTTPException(status_code=401, detail="Unauthorized - Meta token invalid or expired")
        elif status == 429:
            raise HTTPException(status_code=429, detail="Rate limited by Meta")
        elif status == 403 or status == 404:
            raise HTTPException(status_code=404, detail="Resource not found or access denied")
        raise HTTPException(status_code=500, detail="Upstream provider error")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        if params is None:
            params = {}
        params["access_token"] = self.access_token
        url = f"{self.base_url}{endpoint}"
        try:
            resp = httpx.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            self._handle_error(e)
        except httpx.TimeoutException:
            from fastapi import HTTPException
            raise HTTPException(status_code=504, detail="Upstream provider timeout")

    def _post(self, endpoint: str, data: dict = None) -> dict:
        if data is None:
            data = {}
        data["access_token"] = self.access_token
        url = f"{self.base_url}{endpoint}"
        try:
            resp = httpx.post(url, data=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            self._handle_error(e)
        except httpx.TimeoutException:
            from fastapi import HTTPException
            raise HTTPException(status_code=504, detail="Upstream provider timeout")

    def list_accounts(self) -> List[Dict[str, Any]]:
        if settings.META_ADS_MOCK_MODE:
            return [{"id": "act_mock_123", "name": "Mock Meta Account", "currency": "USD", "timezone": "UTC"}]
            
        data = self._get("/me/adaccounts", params={"fields": "id,name,currency,timezone_name"})
        results = []
        for acct in data.get("data", []):
            results.append({
                "id": acct.get("id"),
                "name": acct.get("name", f"Account {acct.get('id')}"),
                "currency": acct.get("currency", "USD"),
                "timezone": acct.get("timezone_name", "UTC")
            })
        return results

    def list_campaigns(self, customer_id: str) -> List[Dict[str, Any]]:
        if settings.META_ADS_MOCK_MODE:
            return [{"id": "camp_meta_1", "name": "Meta Brand", "status": "ACTIVE"}]
            
        # Ensure customer_id has 'act_' prefix
        act_id = customer_id if customer_id.startswith("act_") else f"act_{customer_id}"
        data = self._get(f"/{act_id}/campaigns", params={"fields": "id,name,status"})
        campaigns = []
        for c in data.get("data", []):
            campaigns.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "status": c.get("status")
            })
        return campaigns

    def get_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        if settings.META_ADS_MOCK_MODE:
            if campaign_id == "camp_meta_1":
                return {"id": "camp_meta_1", "name": "Meta Brand", "status": "ACTIVE"}
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
            
        data = self._get(f"/{campaign_id}", params={"fields": "id,name,status,daily_budget"})
        
        # Parse daily_budget from cents to USD float if present
        daily_budget_cents = data.get("daily_budget")
        daily_budget_usd = None
        if daily_budget_cents is not None:
            daily_budget_usd = float(daily_budget_cents) / 100.0
            
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "status": data.get("status"),
            "daily_budget": daily_budget_usd
        }

    def get_metrics(self, customer_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        if (end - start).days > 90:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Date range cannot exceed 90 days")
            
        if settings.META_ADS_MOCK_MODE:
            return {
                "impressions": 12000,
                "clicks": 350,
                "cost_micros": 95000000,
                "conversions": 8
            }
            
        act_id = customer_id if customer_id.startswith("act_") else f"act_{customer_id}"
        params = {
            "time_range": f'{{"since":"{start_date}","until":"{end_date}"}}',
            "fields": "impressions,clicks,spend,actions"
        }
        data = self._get(f"/{act_id}/insights", params=params)
        
        totals = {
            "impressions": 0,
            "clicks": 0,
            "cost_micros": 0,
            "conversions": 0.0
        }
        
        for row in data.get("data", []):
            totals["impressions"] += int(row.get("impressions", 0))
            totals["clicks"] += int(row.get("clicks", 0))
            # spend is a string decimal in account currency, we map to micros
            spend = float(row.get("spend", 0.0))
            totals["cost_micros"] += int(spend * 1000000)
            
            # Map specific actions to conversions
            actions = row.get("actions", [])
            for action in actions:
                # offsite_conversion or similar based on specific definition
                if action.get("action_type") in ["offsite_conversion", "lead", "purchase"]:
                    totals["conversions"] += float(action.get("value", 0))
                    
        return totals

    def pause_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        if settings.META_ADS_MOCK_MODE:
            state = self.get_campaign(customer_id, campaign_id) or {"id": campaign_id, "name": "Mock Meta Campaign"}
            state["status"] = "PAUSED"
            return state
            
        data = self._post(f"/{campaign_id}", data={"status": "PAUSED"})
        return self.get_campaign(customer_id, campaign_id)
        
    def resume_campaign(self, customer_id: str, campaign_id: str) -> Dict[str, Any]:
        if settings.META_ADS_MOCK_MODE:
            state = self.get_campaign(customer_id, campaign_id) or {"id": campaign_id, "name": "Mock Meta Campaign"}
            state["status"] = "ACTIVE"
            return state
            
        data = self._post(f"/{campaign_id}", data={"status": "ACTIVE"})
        return self.get_campaign(customer_id, campaign_id)
        
    def update_budget(self, customer_id: str, campaign_id: str, daily_budget_usd: float) -> Dict[str, Any]:
        if settings.META_ADS_MOCK_MODE:
            state = self.get_campaign(customer_id, campaign_id) or {"id": campaign_id, "name": "Mock Meta Campaign"}
            state["daily_budget"] = daily_budget_usd
            return state
            
        # Enforce USD currency safety constraint
        act_id = customer_id if customer_id.startswith("act_") else f"act_{customer_id}"
        account_info = self._get(f"/{act_id}", params={"fields": "currency"})
        currency = account_info.get("currency", "USD").upper()
        
        if currency != "USD":
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400, 
                detail="Phase 4C supports USD Meta ad accounts only; non-USD accounts are rejected rather than silently mis-converted."
            )
            
        # Convert to cents
        daily_budget_cents = int(daily_budget_usd * 100)
        
        data = self._post(f"/{campaign_id}", data={"daily_budget": daily_budget_cents})
        
        # Notice we don't return 'daily_budget' explicitly in get_campaign unless we added it to the fields
        # To make it deterministic for our execution engine's result_state parsing, we should fetch it.
        # However, for consistency with Google Ads mock and the rest, we just return the full campaign dict.
        # We need to ensure get_campaign returns daily_budget so we can assert it.
        # Actually, let's update `get_campaign` to fetch `daily_budget` as well.
        return self.get_campaign(customer_id, campaign_id)

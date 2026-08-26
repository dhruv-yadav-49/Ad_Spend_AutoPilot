from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from datetime import datetime, timedelta
import secrets
import logging

from ..db import get_db
from ..models import User, AdPlatformConnection, OAuthState, Organization
from ..auth import get_current_user
from ..config import settings
from ..encryption import encrypt_token
from ..providers import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms", tags=["Platforms"])

# 1. List connections
@router.get("/connections")
def list_connections(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    connections = db.scalars(
        select(AdPlatformConnection)
        .where(AdPlatformConnection.organization_id == current_user.organization_id)
    ).all()
    
    return [
        {
            "id": c.id,
            "platform": c.platform,
            "status": c.status,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "external_account_name": c.external_account_name
        }
        for c in connections
    ]

# 2. Connect
@router.get("/{platform}/connect")
def connect_platform(platform: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        provider = get_provider(platform)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unsupported platform")
        
    state_val = secrets.token_urlsafe(32)
    
    oauth_state = OAuthState(
        state=state_val,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        platform=platform,
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db.add(oauth_state)
    db.commit()
    
    auth_url = provider.get_authorization_url(state=state_val)
    return RedirectResponse(url=auth_url)

# 3. Callback
@router.get("/callback")
def oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: Session = Depends(get_db)
):
    if not state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/integrations?error=missing_state")
        
    if error:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/integrations?error=oauth_error")
        
    if not code:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/integrations?error=missing_code")

    oauth_state = db.scalar(select(OAuthState).where(OAuthState.state == state))
    
    if not oauth_state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/integrations?error=invalid_state")
        
    if oauth_state.expires_at < datetime.utcnow():
        db.delete(oauth_state)
        db.commit()
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/integrations?error=expired_state")
        
    platform = oauth_state.platform
    org_id = oauth_state.organization_id
    user_id = oauth_state.user_id
    
    # Single use - delete immediately
    db.delete(oauth_state)
    db.commit()
    
    try:
        provider = get_provider(platform)
        access_token, refresh_token, expires_at = provider.exchange_code(code)
    except Exception as e:
        logger.error(f"OAuth exchange failed: {e}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/integrations?error=exchange_failed")
        
    enc_access = encrypt_token(access_token)
    enc_refresh = encrypt_token(refresh_token) if refresh_token else None
    
    # In Phase 3B Mock, we'll pretend we fetched the customer account info during OAuth
    external_account_id = None
    external_account_name = None
    if settings.GOOGLE_ADS_MOCK_MODE and platform == "google":
        external_account_id = "mock_customer_123"
        external_account_name = "Mock Org Account"
    elif settings.META_ADS_MOCK_MODE and platform == "meta":
        external_account_id = "act_mock_123"
        external_account_name = "Mock Meta Account"
        
    # Check if connection already exists for this org/platform
    existing = db.scalar(
        select(AdPlatformConnection)
        .where(AdPlatformConnection.organization_id == org_id, AdPlatformConnection.platform == platform)
    )
    
    if existing:
        existing.encrypted_access_token = enc_access
        if enc_refresh:
            existing.encrypted_refresh_token = enc_refresh
        existing.expires_at = expires_at
        existing.status = "active"
        existing.updated_at = datetime.utcnow()
        if external_account_id:
            existing.external_account_id = external_account_id
            existing.external_account_name = external_account_name
    else:
        new_conn = AdPlatformConnection(
            organization_id=org_id,
            platform=platform,
            encrypted_access_token=enc_access,
            encrypted_refresh_token=enc_refresh,
            expires_at=expires_at,
            created_by_user_id=user_id,
            status="active",
            external_account_id=external_account_id,
            external_account_name=external_account_name
        )
        db.add(new_conn)
        
    db.commit()
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/integrations?status=connected&platform={platform}")

# 4. Disconnect
@router.delete("/{platform}/disconnect")
def disconnect_platform(platform: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    connection = db.scalar(
        select(AdPlatformConnection)
        .where(
            AdPlatformConnection.organization_id == current_user.organization_id,
            AdPlatformConnection.platform == platform
        )
    )
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    try:
        provider = get_provider(platform)
        provider.revoke_token("token_placeholder")
    except Exception as e:
        logger.warning(f"Failed to revoke token for {platform}: {e}")
        
    # Delete encrypted credentials completely
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.expires_at = None
    connection.status = "disconnected"
    connection.updated_at = datetime.utcnow()
    
    db.commit()
    return {"status": "success", "message": f"{platform} disconnected successfully."}

# ----------------- Phase 3B Read-Only APIs ----------------- #
from ..credentials import CredentialService
from ..providers import GoogleAdsClient, MetaAdsClient

def get_google_client(db: Session, current_user: User, customer_id: str = None) -> GoogleAdsClient:
    try:
        access_token, valid_customer_ids = CredentialService.get_access_token_and_customers(db, current_user.organization_id, "google")
    except ValueError as e:
        # No connection or expired token that failed refresh
        raise HTTPException(status_code=404, detail=str(e))
        
    if customer_id and customer_id not in valid_customer_ids:
        # Reject unauthorized customer ID safely (404 to not leak existence)
        raise HTTPException(status_code=404, detail="Customer account not found or access denied")
        
    return GoogleAdsClient(access_token)

@router.get("/google/accounts")
def get_google_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = get_google_client(db, current_user)
    return client.list_accounts()
    
@router.get("/google/campaigns")
def get_google_campaigns(customer_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = get_google_client(db, current_user, customer_id)
    return client.list_campaigns(customer_id)
    
@router.get("/google/metrics")
def get_google_metrics(customer_id: str, start_date: str, end_date: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = get_google_client(db, current_user, customer_id)
    try:
        return client.get_metrics(customer_id, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def get_meta_client(db: Session, current_user: User, customer_id: str = None) -> MetaAdsClient:
    try:
        access_token, valid_customer_ids = CredentialService.get_access_token_and_customers(db, current_user.organization_id, "meta")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    if customer_id and customer_id not in valid_customer_ids:
        raise HTTPException(status_code=404, detail="Customer account not found or access denied")
        
    return MetaAdsClient(access_token)

@router.get("/meta/accounts")
def get_meta_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = get_meta_client(db, current_user)
    return client.list_accounts()
    
@router.get("/meta/campaigns")
def get_meta_campaigns(customer_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = get_meta_client(db, current_user, customer_id)
    return client.list_campaigns(customer_id)
    
@router.get("/meta/metrics")
def get_meta_metrics(customer_id: str, start_date: str, end_date: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = get_meta_client(db, current_user, customer_id)
    try:
        return client.get_metrics(customer_id, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- Phase 3E Unified APIs ----------------- #
from ..services_reporting import UnifiedReportingService
from ..schemas_unified import UnifiedCampaignsResponse, UnifiedMetricsResponse

@router.get("/unified/campaigns", response_model=UnifiedCampaignsResponse)
def get_unified_campaigns(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return UnifiedReportingService.get_unified_campaigns(db, current_user.organization_id)

@router.get("/unified/metrics", response_model=UnifiedMetricsResponse)
def get_unified_metrics(start_date: str, end_date: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return UnifiedReportingService.get_unified_metrics(db, current_user.organization_id, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

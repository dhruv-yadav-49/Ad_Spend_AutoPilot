from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timedelta
import logging

from .models import AdPlatformConnection
from .encryption import decrypt_token, encrypt_token
from .config import settings

logger = logging.getLogger(__name__)

class CredentialService:
    @staticmethod
    def get_access_token_and_customers(db: Session, organization_id: int, platform: str) -> tuple[str, list[str]]:
        """
        Retrieves the valid plaintext access token and a list of valid customer IDs for the given organization and platform.
        Handles decryption securely. If the token is expired, attempts a refresh.
        """
        connection = db.scalar(
            select(AdPlatformConnection)
            .where(
                AdPlatformConnection.organization_id == organization_id,
                AdPlatformConnection.platform == platform,
                AdPlatformConnection.status == "active"
            )
        )
        
        if not connection:
            raise ValueError(f"No active connection found for platform {platform}")
            
        if not connection.encrypted_access_token:
            raise ValueError("Connection missing encrypted access token")
            
        # Check expiration
        if connection.expires_at and connection.expires_at <= datetime.utcnow():
            access_token = CredentialService._refresh_token(db, connection)
        else:
            access_token = decrypt_token(connection.encrypted_access_token)
            
        valid_customer_ids = []
        if connection.external_account_id:
            valid_customer_ids = [connection.external_account_id]
            
        return access_token, valid_customer_ids

    @staticmethod
    def _refresh_token(db: Session, connection: AdPlatformConnection) -> str:
        if not connection.encrypted_refresh_token:
            connection.status = "expired"
            db.commit()
            raise ValueError("Token expired and no refresh token available")
            
        refresh_token = decrypt_token(connection.encrypted_refresh_token)
        
        try:
            if connection.platform == "google":
                if settings.GOOGLE_ADS_MOCK_MODE:
                    new_access_token = "mock_google_access_refreshed"
                    new_expires_at = datetime.utcnow() + timedelta(hours=1)
                else:
                    import httpx
                    resp = httpx.post("https://oauth2.googleapis.com/token", data={
                        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
                        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token"
                    })
                    if resp.status_code != 200:
                        raise ValueError(f"Failed to refresh token: {resp.text}")
                    data = resp.json()
                    new_access_token = data["access_token"]
                    new_expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
            elif connection.platform == "meta":
                if settings.META_ADS_MOCK_MODE:
                    new_access_token = "mock_meta_access_refreshed"
                    new_expires_at = datetime.utcnow() + timedelta(days=60)
                else:
                    import httpx
                    # Extend long-lived token
                    token_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/oauth/access_token"
                    resp = httpx.get(token_url, params={
                        "grant_type": "fb_exchange_token",
                        "client_id": settings.META_ADS_CLIENT_ID,
                        "client_secret": settings.META_ADS_CLIENT_SECRET,
                        "fb_exchange_token": refresh_token
                    })
                    if resp.status_code != 200:
                        raise ValueError(f"Failed to refresh Meta token: {resp.text}")
                    data = resp.json()
                    new_access_token = data["access_token"]
                    new_expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 60 * 24 * 3600))
            else:
                raise NotImplementedError(f"Real token refresh for {connection.platform} not implemented")
                
            connection.encrypted_access_token = encrypt_token(new_access_token)
            connection.expires_at = new_expires_at
            connection.updated_at = datetime.utcnow()
            db.commit()
            return new_access_token
            
        except Exception as e:
            logger.error(f"Failed to refresh token for {connection.platform}: {e}")
            connection.status = "expired"
            db.commit()
            raise ValueError("Failed to refresh token")

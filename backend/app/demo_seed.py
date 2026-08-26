import os
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from .db import engine
from .models import User, Organization, AdPlatformConnection
from .security import hash_password
from .encryption import encrypt_token

def run_demo_seed():
    with Session(engine) as db:
        # Check if already seeded
        org = db.query(Organization).filter_by(name="Demo Organization").first()
        if org:
            print("Demo Organization already exists. Using existing organization...")
            
        if not org:
            org = Organization(
                name="Demo Organization", 
                invite_code=secrets.token_urlsafe(16), 
                created_at=datetime.now(timezone.utc), 
                updated_at=datetime.now(timezone.utc)
            )
            db.add(org)
            db.commit()
            db.refresh(org)

        # Ensure Manager exists
        manager = db.query(User).filter_by(email="manager@demo.com").first()
        if not manager:
            manager = User(
                name="Demo Manager", 
                email="manager@demo.com", 
                password_hash=hash_password("JudgeDemo123"), 
                role="manager", 
                organization_id=org.id
            )
            db.add(manager)

        # Ensure Analyst exists
        analyst = db.query(User).filter_by(email="analyst@demo.com").first()
        if not analyst:
            analyst = User(
                name="Demo Analyst", 
                email="analyst@demo.com", 
                password_hash=hash_password("JudgeDemo123"), 
                role="analyst", 
                organization_id=org.id
            )
            db.add(analyst)
            db.commit()

        # Provide active OAuth connections for Google and Meta so we don't have to authenticate live.
        # Ensure they exist for this organization
        google_conn = db.query(AdPlatformConnection).filter_by(organization_id=org.id, platform="google").first()
        if not google_conn:
            google_conn = AdPlatformConnection(
                organization_id=org.id,
                platform="google",
                external_account_id="mock_customer_123",
                external_account_name="Mock Org Account",
                encrypted_access_token=encrypt_token("mock_google_access"),
                encrypted_refresh_token=encrypt_token("mock_google_refresh"),
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=365),
                status="active",
                created_by_user_id=manager.id
            )
            db.add(google_conn)
        else:
            google_conn.encrypted_access_token = encrypt_token("mock_google_access")
            google_conn.encrypted_refresh_token = encrypt_token("mock_google_refresh")
            google_conn.status = "active"
            
        meta_conn = db.query(AdPlatformConnection).filter_by(organization_id=org.id, platform="meta").first()
        if not meta_conn:
            meta_conn = AdPlatformConnection(
                organization_id=org.id,
                platform="meta",
                external_account_id="act_mock_123",
                external_account_name="Mock Meta Account",
                encrypted_access_token=encrypt_token("mock_meta_access"),
                encrypted_refresh_token=encrypt_token("mock_meta_refresh"),
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=365),
                status="active",
                created_by_user_id=manager.id
            )
            db.add(meta_conn)
        else:
            meta_conn.encrypted_access_token = encrypt_token("mock_meta_access")
            meta_conn.encrypted_refresh_token = encrypt_token("mock_meta_refresh")
            meta_conn.status = "active"
            
        db.commit()
        
        print("\n" + "="*50)
        print("✅ GOLDEN DEMO SEED SUCCESSFUL ✅")
        print("="*50)
        print("Use these credentials to log in during the presentation:\n")
        print("ANALYST (To propose the change)")
        print("Email: analyst@demo.com")
        print("Pass:  JudgeDemo123")
        print("\nMANAGER (To approve the change)")
        print("Email: manager@demo.com")
        print("Pass:  JudgeDemo123")
        print("\nPlatform Connections for Google and Meta are already active.")
        print("="*50 + "\n")

if __name__ == "__main__":
    run_demo_seed()

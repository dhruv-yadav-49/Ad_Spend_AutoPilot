import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import urllib.parse
from sqlalchemy import select

from app.main import app
from app.config import settings
from app.encryption import encrypt_token, decrypt_token
from app.models import AdPlatformConnection
from app.providers import GoogleAdsClient

client = TestClient(app)

import uuid
def get_tokens(role):
    unique_id = str(uuid.uuid4())[:8]
    res = client.post("/auth/signup", json={
        "name": f"P3B {role}",
        "email": f"{role}_{unique_id}@test.com",
        "password": "pw",
        "organization_name": f"Org P3B {role} {unique_id}"
    })
    login = client.post("/auth/login", json={"email": f"{role}_{unique_id}@test.com", "password": "pw"})
    return login.json()["access_token"], login.cookies.get("refresh_token"), login.json()["user"]["organization_id"]

def setup_mock_connection(access_token, platform="google"):
    settings.GOOGLE_ADS_MOCK_MODE = True
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get(f"/platforms/{platform}/connect", headers=headers, follow_redirects=False)
    assert res.status_code == 307
    state = urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)["state"][0]
    res2 = client.get(f"/platforms/callback?code=mock_{platform}_code_123&state={state}", follow_redirects=False)
    assert res2.status_code == 307

def test_expired_token_triggers_refresh_and_persisted(db_session):
    settings.GOOGLE_ADS_MOCK_MODE = True
    access_token, _, org_id = get_tokens("refresh_test")
    setup_mock_connection(access_token)
    
    # Manually expire the token in the DB
    db_session.commit()
    conn = db_session.scalar(select(AdPlatformConnection).where(AdPlatformConnection.organization_id == org_id, AdPlatformConnection.platform == "google"))
    old_access = conn.encrypted_access_token
    conn.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    
    # Make API request, which should trigger refresh
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/google/accounts", headers=headers)
    assert res.status_code == 200
    
    # Verify DB was updated
    db_session.commit()
    conn = db_session.scalar(select(AdPlatformConnection).where(AdPlatformConnection.organization_id == org_id, AdPlatformConnection.platform == "google"))
    assert conn.encrypted_access_token != old_access
    assert decrypt_token(conn.encrypted_access_token) == "mock_google_access_refreshed"
    assert conn.expires_at > datetime.utcnow()

def test_refresh_token_never_returned(db_session):
    settings.GOOGLE_ADS_MOCK_MODE = True
    access_token, _, _ = get_tokens("no_leak")
    setup_mock_connection(access_token)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/connections", headers=headers)
    data = res.json()
    assert len(data) == 1
    assert "encrypted_access_token" not in data[0]
    assert "encrypted_refresh_token" not in data[0]
    assert "access_token" not in data[0]
    assert "refresh_token" not in data[0]

def test_org_cannot_use_others_customer_id(db_session):
    settings.GOOGLE_ADS_MOCK_MODE = True
    access1, _, org1 = get_tokens("tenant_A")
    access2, _, org2 = get_tokens("tenant_B")
    
    setup_mock_connection(access1)
    setup_mock_connection(access2)
    
    # Manually change Org B's external_account_id
    db_session.commit()
    conn = db_session.scalar(select(AdPlatformConnection).where(AdPlatformConnection.organization_id == org2, AdPlatformConnection.platform == "google"))
    conn.external_account_id = "org_b_customer"
    db_session.commit()
        
    # Org A tries to fetch campaigns using Org B's customer_id
    headers1 = {"Authorization": f"Bearer {access1}"}
    res = client.get("/platforms/google/campaigns?customer_id=org_b_customer", headers=headers1)
    assert res.status_code == 404

def test_invalid_customer_id_rejected():
    settings.GOOGLE_ADS_MOCK_MODE = True
    access_token, _, _ = get_tokens("invalid_cust")
    setup_mock_connection(access_token)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/google/campaigns?customer_id=completely_fake_id", headers=headers)
    assert res.status_code == 404

def test_excessive_metrics_date_range():
    settings.GOOGLE_ADS_MOCK_MODE = True
    access_token, _, _ = get_tokens("metrics_test")
    setup_mock_connection(access_token)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/google/metrics?customer_id=mock_customer_123&start_date=2023-01-01&end_date=2024-01-01", headers=headers)
    assert res.status_code == 400
    assert "exceed 90 days" in res.json()["detail"]
    

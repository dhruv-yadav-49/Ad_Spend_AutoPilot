import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import urllib.parse
from sqlalchemy import select

from app.main import app
from app.config import settings
from app.providers import MetaAdsClient
from app.models import AdPlatformConnection

client = TestClient(app)

import uuid
def get_tokens(role):
    unique_id = str(uuid.uuid4())[:8]
    res = client.post("/auth/signup", json={
        "name": f"P3D {role}",
        "email": f"{role}_{unique_id}@test.com",
        "password": "pw",
        "organization_name": f"Org P3D {role} {unique_id}"
    })
    login = client.post("/auth/login", json={"email": f"{role}_{unique_id}@test.com", "password": "pw"})
    return login.json()["access_token"], login.cookies.get("refresh_token"), login.json()["user"]["organization_id"]

def setup_mock_meta_connection(access_token):
    settings.META_ADS_MOCK_MODE = True
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/meta/connect", headers=headers, follow_redirects=False)
    assert res.status_code == 307
    state = urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)["state"][0]
    res2 = client.get(f"/platforms/callback?code=mock_meta_code_123&state={state}", follow_redirects=False)
    assert res2.status_code == 307

def test_meta_tokens_never_returned_plaintext_in_db(db_session):
    access_token, _, org_id = get_tokens("meta_sec")
    setup_mock_meta_connection(access_token)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/connections", headers=headers)
    data = res.json()
    assert len(data) >= 1
    
    meta_conn = next(c for c in data if c["platform"] == "meta")
    assert "encrypted_access_token" not in meta_conn
    assert "access_token" not in meta_conn
    assert "refresh_token" not in meta_conn
    
    # Check DB directly
    conn = db_session.scalar(select(AdPlatformConnection).where(AdPlatformConnection.organization_id == org_id, AdPlatformConnection.platform == "meta"))
    assert conn.encrypted_access_token is not None
    assert isinstance(conn.encrypted_access_token, str)
    assert "mock_meta_access" not in conn.encrypted_access_token

def test_meta_tenant_isolation(db_session):
    access1, _, org1 = get_tokens("tenant_A")
    access2, _, org2 = get_tokens("tenant_B")
    
    setup_mock_meta_connection(access1)
    setup_mock_meta_connection(access2)
    
    # Manually change Org B's external_account_id
    db_session.commit()
    conn = db_session.scalar(select(AdPlatformConnection).where(AdPlatformConnection.organization_id == org2, AdPlatformConnection.platform == "meta"))
    conn.external_account_id = "act_mock_org_b"
    db_session.commit()
        
    # Org A tries to fetch campaigns using Org B's ad_account_id
    headers1 = {"Authorization": f"Bearer {access1}"}
    res = client.get("/platforms/meta/campaigns?customer_id=act_mock_org_b", headers=headers1)
    assert res.status_code == 404
    
    # Try totally fake ID
    res2 = client.get("/platforms/meta/campaigns?customer_id=completely_fake_meta_id", headers=headers1)
    assert res2.status_code == 404
    assert res.json() == res2.json() # Same safe 404 error

@patch("httpx.get")
def test_real_meta_api_reads(mock_get):
    settings.META_ADS_MOCK_MODE = False
    meta_client = MetaAdsClient("real_access_token")
    
    # Mock Accounts
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "act_123", "name": "Test Account", "currency": "EUR", "timezone_name": "Europe/London"}
        ]
    }
    mock_get.return_value = mock_response
    
    accounts = meta_client.list_accounts()
    assert len(accounts) == 1
    assert accounts[0]["id"] == "act_123"
    assert accounts[0]["currency"] == "EUR"
    
    # Mock Metrics
    mock_metrics_resp = MagicMock()
    mock_metrics_resp.status_code = 200
    mock_metrics_resp.json.return_value = {
        "data": [
            {
                "impressions": "1000",
                "clicks": "50",
                "spend": "12.50",
                "actions": [
                    {"action_type": "link_click", "value": "50"},
                    {"action_type": "offsite_conversion", "value": "2"}
                ]
            }
        ]
    }
    mock_get.return_value = mock_metrics_resp
    
    metrics = meta_client.get_metrics("act_123", "2024-01-01", "2024-01-30")
    assert metrics["impressions"] == 1000
    assert metrics["clicks"] == 50
    assert metrics["cost_micros"] == 12500000 # 12.50 * 1,000,000
    assert metrics["conversions"] == 2.0

@patch("httpx.get")
def test_meta_api_error_mapping(mock_get):
    settings.META_ADS_MOCK_MODE = False
    meta_client = MetaAdsClient("real_access_token")
    
    from httpx import HTTPStatusError, Request, Response
    
    req = Request("GET", "https://graph.facebook.com")
    resp_401 = Response(401, request=req)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.raise_for_status.side_effect = HTTPStatusError("401", request=req, response=resp_401)
    mock_get.return_value = mock_resp
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        meta_client.list_accounts()
    assert exc.value.status_code == 401

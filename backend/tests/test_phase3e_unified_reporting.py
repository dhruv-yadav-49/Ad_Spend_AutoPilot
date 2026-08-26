import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import urllib.parse
from sqlalchemy import select

from app.main import app
from app.config import settings
from app.models import AdPlatformConnection

client = TestClient(app)

import uuid
def get_tokens(role):
    unique_id = str(uuid.uuid4())[:8]
    res = client.post("/auth/signup", json={
        "name": f"P3E {role}",
        "email": f"{role}_{unique_id}@test.com",
        "password": "pw",
        "organization_name": f"Org P3E {role} {unique_id}"
    })
    login = client.post("/auth/login", json={"email": f"{role}_{unique_id}@test.com", "password": "pw"})
    return login.json()["access_token"], login.cookies.get("refresh_token"), login.json()["user"]["organization_id"]

def setup_mock_google_connection(access_token):
    settings.GOOGLE_ADS_MOCK_MODE = True
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/google/connect", headers=headers, follow_redirects=False)
    state = urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)["state"][0]
    client.get(f"/platforms/callback?code=mock_google_code_123&state={state}", follow_redirects=False)

def setup_mock_meta_connection(access_token):
    settings.META_ADS_MOCK_MODE = True
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/meta/connect", headers=headers, follow_redirects=False)
    state = urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)["state"][0]
    client.get(f"/platforms/callback?code=mock_meta_code_123&state={state}", follow_redirects=False)

def test_unified_campaigns_returns_both(db_session):
    access_token, _, org_id = get_tokens("unified_user")
    setup_mock_google_connection(access_token)
    setup_mock_meta_connection(access_token)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/platforms/unified/campaigns", headers=headers)
    assert res.status_code == 200
    data = res.json()
    
    assert "platforms" in data
    assert data["platforms"]["google"]["status"] == "success"
    assert data["platforms"]["meta"]["status"] == "success"
    
    campaigns = data["data"]
    # Verify same campaign name != same identity
    platforms = [c["platform"] for c in campaigns]
    assert "google" in platforms
    assert "meta" in platforms
    
    # Assert IDs retain prefix mapping
    for c in campaigns:
        assert c["id"].startswith(c["platform"] + "_")

def test_unified_metrics_math(db_session):
    access_token, _, org_id = get_tokens("math_user")
    setup_mock_google_connection(access_token)
    setup_mock_meta_connection(access_token)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    end = datetime.utcnow().strftime("%Y-%m-%d")
    
    res = client.get(f"/platforms/unified/metrics?start_date={start}&end_date={end}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    metrics = data["data"]
    
    for m in metrics:
        if m["impressions"] == 0:
            assert m["ctr"] is None
        else:
            assert m["ctr"] == m["clicks"] / m["impressions"]
            
        if m["clicks"] == 0:
            assert m["cpc"] is None
        else:
            assert m["cpc"] == m["cost_micros"] / m["clicks"]
            
        assert m["roas"] is None

def test_tenant_forging_ignored(db_session):
    access_alpha, _, org_alpha = get_tokens("alpha")
    access_beta, _, org_beta = get_tokens("beta")
    
    setup_mock_google_connection(access_alpha)
    setup_mock_meta_connection(access_beta) # Beta only has meta
    
    headers_alpha = {"Authorization": f"Bearer {access_alpha}"}
    
    # Alpha tries to fetch Beta's unified data by passing org ID in query (even though it's not in the schema, maybe they try to append it)
    res = client.get(f"/platforms/unified/campaigns?organization_id={org_beta}", headers=headers_alpha)
    assert res.status_code == 200
    data = res.json()
    
    # Data should still only be Alpha's Google campaigns
    platforms = [c["platform"] for c in data["data"]]
    assert "google" in platforms
    assert "meta" not in platforms
    
    assert data["platforms"]["meta"]["status"] == "not_connected"

def test_graceful_platform_failure(db_session):
    access_token, _, org_id = get_tokens("fail_user")
    setup_mock_google_connection(access_token)
    setup_mock_meta_connection(access_token)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    with patch("app.providers.GoogleAdsClient.list_campaigns", side_effect=Exception("API Down")):
        res = client.get("/platforms/unified/campaigns", headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        # Meta should succeed, Google should fail
        assert data["platforms"]["google"]["status"] == "failed"
        assert "API Down" in data["platforms"]["google"]["error"]
        
        assert data["platforms"]["meta"]["status"] == "success"
        
        # Meta campaigns should still be in the data
        platforms = [c["platform"] for c in data["data"]]
        assert "meta" in platforms
        assert "google" not in platforms

def test_date_range_limits(db_session):
    access_token, _, org_id = get_tokens("date_user")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    start_ok = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
    end_ok = datetime.utcnow().strftime("%Y-%m-%d")
    
    res = client.get(f"/platforms/unified/metrics?start_date={start_ok}&end_date={end_ok}", headers=headers)
    assert res.status_code == 200
    
    start_bad = (datetime.utcnow() - timedelta(days=91)).strftime("%Y-%m-%d")
    res = client.get(f"/platforms/unified/metrics?start_date={start_bad}&end_date={end_ok}", headers=headers)
    assert res.status_code == 400
    
    # Start after end
    res = client.get(f"/platforms/unified/metrics?start_date={end_ok}&end_date={start_ok}", headers=headers)
    assert res.status_code == 400
    
    # Future
    start_future = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_future = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")
    res = client.get(f"/platforms/unified/metrics?start_date={start_future}&end_date={end_future}", headers=headers)
    assert res.status_code == 400

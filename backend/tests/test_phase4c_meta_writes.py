import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select, text
import json
import uuid

from app.main import app
from app.config import settings
from app.models import Approval, ExecutionAudit, AdPlatformConnection

@pytest.fixture(autouse=True)
def mock_meta_mode():
    settings.META_ADS_MOCK_MODE = True
    yield
    # reset if needed, though usually tests override it anyway

client = TestClient(app)

def get_tokens(role):
    unique_id = str(uuid.uuid4())[:8]
    client.post("/auth/signup", json={
        "name": f"P4C {role}",
        "email": f"{role}_{unique_id}@test.com",
        "password": "pw",
        "organization_name": f"Org P4C {unique_id}"
    })
    login = client.post("/auth/login", json={"email": f"{role}_{unique_id}@test.com", "password": "pw"})
    return login.json()["access_token"], login.json()["user"]["id"], login.json()["user"]["organization_id"]

def setup_connection(db_session, org_id, user_id):
    conn = AdPlatformConnection(
        organization_id=org_id,
        platform="meta",
        external_account_id="act_mock_1",
        created_by_user_id=user_id,
        status="active"
    )
    db_session.add(conn)
    db_session.commit()

def test_meta_ads_pause_write(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    with patch("app.routers.mutations.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        res = client.post("/platforms/mutations/propose", json={
            "platform": "meta",
            "platform_account_id": "act_mock_1",
            "platform_campaign_id": "camp_meta_1",
            "action": "pause"
        }, headers=headers)
    
    assert res.status_code == 200
    approval_id = res.json()["approval_id"]
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        
    assert exec_res.status_code == 200
    audit_id = exec_res.json()["audit_id"]
    
    audit = db_session.get(ExecutionAudit, audit_id)
    assert audit.status == "success"
    result = json.loads(audit.result_state)
    assert result["status"] == "PAUSED"
    
def test_meta_ads_update_budget_write(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    with patch("app.routers.mutations.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        res = client.post("/platforms/mutations/propose", json={
            "platform": "meta",
            "platform_account_id": "act_mock_1",
            "platform_campaign_id": "camp_meta_1",
            "action": "update_budget",
            "action_payload": {"new_daily_budget": 120.0}
        }, headers=headers)
        
    approval_id = res.json()["approval_id"]
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        
    assert exec_res.status_code == 200
    audit_id = exec_res.json()["audit_id"]
    audit = db_session.get(ExecutionAudit, audit_id)
    result = json.loads(audit.result_state)
    assert result["daily_budget"] == 120.0

def test_stale_approval_aborts_meta(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    # 1. Propose while campaign is ACTIVE
    with patch("app.routers.mutations.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        res = client.post("/platforms/mutations/propose", json={
            "platform": "meta",
            "platform_account_id": "act_mock_1",
            "platform_campaign_id": "camp_meta_1",
            "action": "pause"
        }, headers=headers)
        
    approval_id = res.json()["approval_id"]
    
    # 2. Before execution, the campaign status externally changes to PAUSED
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        with patch("app.providers.MetaAdsClient.get_campaign", return_value={"id": "camp_meta_1", "status": "PAUSED"}):
            exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
            
    # 3. Execution should be blocked (409 Conflict)
    assert exec_res.status_code == 409
    assert "Campaign state changed externally" in exec_res.json()["detail"]
    assert "ACTIVE -> PAUSED" in exec_res.json()["detail"]

def test_meta_currency_validation(db_session, monkeypatch):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    with patch("app.routers.mutations.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        res = client.post("/platforms/mutations/propose", json={
            "platform": "meta",
            "platform_account_id": "act_mock_1",
            "platform_campaign_id": "camp_meta_1",
            "action": "update_budget",
            "action_payload": {"new_daily_budget": 120.0}
        }, headers=headers)
        
    approval_id = res.json()["approval_id"]
    
    # Turn off MOCK_MODE temporarily just for the update_budget part to test currency validation
    # because mock mode bypasses the currency check.
    monkeypatch.setattr("app.providers.settings.META_ADS_MOCK_MODE", False)
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock", ["act_mock_1"])):
        with patch("app.providers.MetaAdsClient._get", return_value={"currency": "EUR"}):
            with patch("app.providers.MetaAdsClient.get_campaign", return_value={"id": "camp_meta_1", "status": "ACTIVE", "daily_budget": 120.0}):
                exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
            
    assert exec_res.status_code == 400
    assert "supports USD Meta ad accounts only" in exec_res.json()["detail"]

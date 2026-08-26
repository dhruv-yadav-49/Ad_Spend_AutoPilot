import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select, text
import json
import uuid

from app.main import app
from app.config import settings
from app.models import Approval, ExecutionAudit, AdPlatformConnection

client = TestClient(app)

def get_tokens(role):
    unique_id = str(uuid.uuid4())[:8]
    client.post("/auth/signup", json={
        "name": f"P4B {role}",
        "email": f"{role}_{unique_id}@test.com",
        "password": "pw",
        "organization_name": f"Org P4B {unique_id}"
    })
    login = client.post("/auth/login", json={"email": f"{role}_{unique_id}@test.com", "password": "pw"})
    return login.json()["access_token"], login.json()["user"]["id"], login.json()["user"]["organization_id"]

def setup_connection(db_session, org_id, user_id):
    conn = AdPlatformConnection(
        organization_id=org_id,
        platform="google",
        external_account_id="mock_account_1",
        created_by_user_id=user_id,
        status="active"
    )
    db_session.add(conn)
    db_session.commit()

def test_google_ads_pause_write(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    # 1. Propose
    # In MOCK_MODE, get_campaign returns status="ENABLED"
    with patch("app.routers.mutations.CredentialService.get_access_token_and_customers", return_value=("mock", ["mock_account_1"])):
        res = client.post("/platforms/mutations/propose", json={
            "platform": "google",
            "platform_account_id": "mock_account_1",
            "platform_campaign_id": "camp_1",
            "action": "pause"
        }, headers=headers)
    
    assert res.status_code == 200
    approval_id = res.json()["approval_id"]
    
    # 2. Execute
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock", ["mock_account_1"])):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        
    assert exec_res.status_code == 200
    audit_id = exec_res.json()["audit_id"]
    
    # 3. Verify audit
    audit = db_session.get(ExecutionAudit, audit_id)
    assert audit.status == "success"
    result = json.loads(audit.result_state)
    assert result["status"] == "PAUSED"
    
def test_google_ads_update_budget_write(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    # MOCK_MODE defaults to $10 daily budget?
    # Actually mock just sets what we tell it
    with patch("app.routers.mutations.CredentialService.get_access_token_and_customers", return_value=("mock", ["mock_account_1"])):
        res = client.post("/platforms/mutations/propose", json={
            "platform": "google",
            "platform_account_id": "mock_account_1",
            "platform_campaign_id": "camp_1",
            "action": "update_budget",
            "action_payload": {"new_daily_budget": 120.0}
        }, headers=headers)
        
    approval_id = res.json()["approval_id"]
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock", ["mock_account_1"])):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        
    assert exec_res.status_code == 200
    audit_id = exec_res.json()["audit_id"]
    audit = db_session.get(ExecutionAudit, audit_id)
    result = json.loads(audit.result_state)
    assert result["daily_budget"] == 120.0

def test_stale_approval_aborts(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    # 1. Propose while campaign is ENABLED
    with patch("app.routers.mutations.CredentialService.get_access_token_and_customers", return_value=("mock", ["mock_account_1"])):
        res = client.post("/platforms/mutations/propose", json={
            "platform": "google",
            "platform_account_id": "mock_account_1",
            "platform_campaign_id": "camp_1",
            "action": "pause"
        }, headers=headers)
        
    approval_id = res.json()["approval_id"]
    
    # 2. Before execution, the campaign status externally changes to PAUSED
    # So `get_campaign` returns PAUSED instead of ENABLED.
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock", ["mock_account_1"])):
        with patch("app.providers.GoogleAdsClient.get_campaign", return_value={"id": "camp_1", "status": "PAUSED"}):
            exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
            
    # 3. Execution should be blocked (409 Conflict)
    assert exec_res.status_code == 409
    assert "Campaign state changed externally" in exec_res.json()["detail"]
    assert "ENABLED -> PAUSED" in exec_res.json()["detail"]

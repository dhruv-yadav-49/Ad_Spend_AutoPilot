import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from datetime import datetime, timezone
import json

from app.main import app
from app.config import settings
from app.models import Approval, ExecutionAudit, AdPlatformConnection

client = TestClient(app)

import uuid
def get_tokens(role):
    unique_id = str(uuid.uuid4())[:8]
    client.post("/auth/signup", json={
        "name": f"P4A {role}",
        "email": f"{role}_{unique_id}@test.com",
        "password": "pw",
        "organization_name": f"Org P4A {unique_id}"
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

def test_unauthenticated_execution():
    res = client.post("/platforms/mutations/1/execute")
    assert res.status_code == 401

def test_analyst_cannot_execute(db_session):
    from app.models import Organization
    
    # Create manager
    access_mgr, uid_mgr, org_id = get_tokens("manager")
    
    org = db_session.get(Organization, org_id)
    invite_code = org.invite_code
    
    # Create analyst using invite code
    unique_id = str(uuid.uuid4())[:8]
    email = f"analyst_{unique_id}@test.com"
    client.post("/auth/signup", json={
        "name": "P4A Analyst",
        "email": email,
        "password": "pw",
        "invite_code": invite_code
    })
    login = client.post("/auth/login", json={"email": email, "password": "pw"})
    access_analyst = login.json()["access_token"]
    
    # Manager proposes a mutation
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers={"Authorization": f"Bearer {access_mgr}"})
    approval_id = res.json()["approval_id"]
    
    # Analyst tries to execute
    res = client.post(f"/platforms/mutations/{approval_id}/execute", headers={"Authorization": f"Bearer {access_analyst}"})
    assert res.status_code == 403
    assert "Only managers can execute mutations" in res.json()["detail"]

def test_invalid_action_payload():
    access, uid, org = get_tokens("manager")
    headers = {"Authorization": f"Bearer {access}"}
    
    # 422 Unprocessable Entity
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "update_budget",
        "action_payload": {"new_daily_budget": -50}
    }, headers=headers)
    assert res.status_code == 422
    assert "greater than 0" in res.text
    
    # Pause cannot have payload
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause",
        "action_payload": {"some_field": "val"}
    }, headers=headers)
    assert res.status_code == 422

def test_manager_auto_approval_and_execution(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    # Pause is auto-approved
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers=headers)
    assert res.status_code == 200
    approval_id = res.json()["approval_id"]
    assert res.json()["status"] == "approved"
    
    # Execute
    # We must patch CredentialService to not try to hit the DB for tokens since we didn't do full OAuth setup
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_account_1"])):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        assert exec_res.status_code == 200
        
        audit_id = exec_res.json()["audit_id"]
        audit = db_session.get(ExecutionAudit, audit_id)
        assert audit.status == "success"
        
        # Verify executed state
        result_state = json.loads(audit.result_state)
        assert result_state["status"].upper() == "PAUSED"

def test_wrong_tenant_execution_indistinguishable(db_session):
    access1, uid1, org1 = get_tokens("manager")
    access2, uid2, org2 = get_tokens("manager")
    
    headers1 = {"Authorization": f"Bearer {access1}"}
    headers2 = {"Authorization": f"Bearer {access2}"}
    
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers=headers1)
    approval_id = res.json()["approval_id"]
    
    # User 2 tries to execute User 1's approval
    exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers2)
    assert exec_res.status_code == 404
    assert exec_res.json()["detail"] == "Approval not found"

def test_self_approval_forbidden(db_session):
    access1, uid1, org1 = get_tokens("manager")
    headers1 = {"Authorization": f"Bearer {access1}"}
    
    # High budget requires manual approval
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "update_budget",
        "action_payload": {"new_daily_budget": 1000}
    }, headers=headers1)
    approval_id = res.json()["approval_id"]
    
    # Manager 1 tries to approve own mutation
    app_res = client.post(f"/platforms/mutations/{approval_id}/approve", headers=headers1)
    assert app_res.status_code == 403
    assert "Manager cannot approve their own mutation" in app_res.json()["detail"]

def test_simultaneous_execution_idempotency(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers=headers)
    approval_id = res.json()["approval_id"]
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_account_1"])):
        res1 = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        assert res1.status_code == 200
        
        # Second attempt should fail with safe rejection
        res2 = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        assert res2.status_code == 400
        assert "Approval is not in 'approved' status" in res2.json()["detail"]

def test_hard_limit_exceeded_aborts(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    # Change max limit for test
    settings.MAX_DAILY_BUDGET_USD = 500
    
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "update_budget",
        "action_payload": {"new_daily_budget": 1000}
    }, headers=headers)
    approval_id = res.json()["approval_id"]
    
    # Manually approve it since it's above threshold (using a second manager)
    access2, uid2, org2 = get_tokens("manager")
    # Make manager 2 part of org 1
    db_session.execute(text(f"UPDATE users SET organization_id = {org} WHERE id = {uid2}"))
    db_session.commit()
    
    app_res = client.post(f"/platforms/mutations/{approval_id}/approve", headers={"Authorization": f"Bearer {access2}"})
    assert app_res.status_code == 200
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_account_1"])):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        assert exec_res.status_code == 400
        assert "exceeds maximum allowed" in exec_res.json()["detail"]

def test_credential_refresh_failure(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers=headers)
    approval_id = res.json()["approval_id"]
    
    # Credential refresh fails
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", side_effect=Exception("Refresh failed")):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        assert exec_res.status_code == 400
        assert "Failed to acquire valid credentials" in exec_res.json()["detail"]

def test_disconnected_platform(db_session):
    access, uid, org = get_tokens("manager")
    # intentionally NOT setting up connection
    headers = {"Authorization": f"Bearer {access}"}
    
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers=headers)
    approval_id = res.json()["approval_id"]
    
    exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
    assert exec_res.status_code == 400
    assert "Platform connection not active or missing" in exec_res.json()["detail"]

def test_provider_succeeds_verification_fails(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers=headers)
    approval_id = res.json()["approval_id"]
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_account_1"])):
        # We patch GoogleAdsClient so the second read (verification) throws exception
        # Call 1: propose (returns state), Call 2: execute read current state (returns state), Call 3: verification (throws exception)
        # Actually in execute: Call 1: get_campaign (current state), Call 2: mutate, Call 3: get_campaign (verify)
        # We can just patch `get_campaign` on the execute endpoint context
        with patch("app.providers.GoogleAdsClient.get_campaign", side_effect=[{"status": "active", "daily_budget": 10}, {"status": "PAUSED", "daily_budget": 10}, Exception("Verification API Error")]):
            exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
            assert exec_res.status_code == 200 # Execution actually succeeded, but audit says uncertain
            audit_id = exec_res.json()["audit_id"]
            
            from app.models import ExecutionAudit
            audit = db_session.get(ExecutionAudit, audit_id)
            assert audit.status == "uncertain"
            assert audit.error_code == "verification_failed"

def test_no_secrets_in_audit(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid)
    headers = {"Authorization": f"Bearer {access}"}
    
    res = client.post("/platforms/mutations/propose", json={
        "platform": "google",
        "platform_account_id": "mock_account_1",
        "platform_campaign_id": "camp_1",
        "action": "pause"
    }, headers=headers)
    approval_id = res.json()["approval_id"]
    
    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_account_1"])):
        exec_res = client.post(f"/platforms/mutations/{approval_id}/execute", headers=headers)
        
        audit_id = exec_res.json()["audit_id"]
        from app.models import ExecutionAudit
        audit = db_session.get(ExecutionAudit, audit_id)
        
        audit_str = str(vars(audit)).lower()
        # Ensure credentials aren't in there
        assert "mock_token" not in audit_str
        assert "access_token" not in audit_str
        assert "refresh_token" not in audit_str

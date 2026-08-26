import pytest
import json
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models import Approval, ExecutionAudit, AdPlatformConnection, Organization
from app.config import settings

settings.GOOGLE_ADS_MOCK_MODE = True
settings.META_ADS_MOCK_MODE = True

client = TestClient(app)

def get_tokens(role):
    unique_id = str(uuid.uuid4())[:8]
    client.post("/auth/signup", json={
        "name": f"P4D {role}",
        "email": f"{role}_{unique_id}@test.com",
        "password": "pw",
        "organization_name": f"Org P4D {unique_id}"
    })
    login = client.post("/auth/login", json={"email": f"{role}_{unique_id}@test.com", "password": "pw"})
    return login.json()["access_token"], login.json()["user"]["id"], login.json()["user"]["organization_id"]

def setup_connection(db_session, org_id, user_id, platform="google", ext_id="mock_customer_123"):
    conn = AdPlatformConnection(
        organization_id=org_id,
        platform=platform,
        external_account_id=ext_id,
        created_by_user_id=user_id,
        status="active"
    )
    db_session.add(conn)
    db_session.commit()

def test_google_ads_429_retryable(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid, "google", "mock_customer_123")
    
    approval = Approval(
        organization_id=org,
        type="mutation",
        platform="google",
        platform_account_id="mock_customer_123",
        platform_campaign_id="camp_1",
        action="update_budget",
        action_payload=json.dumps({"new_daily_budget": 150}),
        expected_previous_state=json.dumps({"status": "ENABLED", "daily_budget": 100}),
        status="approved",
        requester_id=uid,
        summary="Test google 429"
    )
    db_session.add(approval)
    db_session.commit()

    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_customer_123"])):
        with patch('app.providers.GoogleAdsClient.update_budget') as mock_update:
            from fastapi import HTTPException
            mock_update.side_effect = HTTPException(status_code=429, detail="Rate limited by Google")
            
            resp = client.post(
                f"/platforms/mutations/{approval.id}/execute",
                headers={"Authorization": f"Bearer {access}"}
            )
            
            assert resp.status_code == 429
            
            audit = db_session.query(ExecutionAudit).filter_by(approval_id=approval.id).first()
            assert audit is not None
            assert audit.status == "failed_retryable"
            assert "Rate limited" in audit.error_code

def test_meta_ads_403_permanent(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid, "meta", "act_mock_123")
    
    approval = Approval(
        organization_id=org,
        type="mutation",
        platform="meta",
        platform_account_id="act_mock_123",
        platform_campaign_id="camp_meta_1",
        action="pause",
        action_payload=json.dumps({}),
        expected_previous_state=json.dumps({"status": "ACTIVE", "daily_budget": 100}),
        status="approved",
        requester_id=uid,
        summary="Test meta 403"
    )
    db_session.add(approval)
    db_session.commit()

    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["act_mock_123"])):
        with patch('app.providers.MetaAdsClient.pause_campaign') as mock_pause:
            from fastapi import HTTPException
            mock_pause.side_effect = HTTPException(status_code=403, detail="Resource not found or access denied")
            
            resp = client.post(
                f"/platforms/mutations/{approval.id}/execute",
                headers={"Authorization": f"Bearer {access}"}
            )
            
            assert resp.status_code == 403
            
            audit = db_session.query(ExecutionAudit).filter_by(approval_id=approval.id).first()
            assert audit is not None
            assert audit.status == "failed_permanent"
            assert "access denied" in audit.error_code
            
            db_session.refresh(approval)
            assert approval.status == "failed"

def test_retry_on_failed_retryable_preserves_history(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid, "google", "mock_customer_123")
    
    approval = Approval(
        organization_id=org,
        type="mutation",
        platform="google",
        platform_account_id="mock_customer_123",
        platform_campaign_id="camp_1",
        action="update_budget",
        action_payload=json.dumps({"new_daily_budget": 200}),
        expected_previous_state=json.dumps({"status": "ENABLED", "daily_budget": 100}),
        status="approved",
        requester_id=uid,
        summary="Test preserve history"
    )
    db_session.add(approval)
    db_session.commit()

    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_customer_123"])):
        # 1st attempt: 504 Timeout -> failed_retryable
        with patch('app.providers.GoogleAdsClient.update_budget') as mock_update:
            from fastapi import HTTPException
            mock_update.side_effect = HTTPException(status_code=504, detail="Upstream provider timeout")
            resp1 = client.post(
                f"/platforms/mutations/{approval.id}/execute",
                headers={"Authorization": f"Bearer {access}"}
            )
            assert resp1.status_code == 504
            
        audits = db_session.query(ExecutionAudit).filter_by(approval_id=approval.id).order_by(ExecutionAudit.id).all()
        assert len(audits) == 1
        assert audits[0].status == "failed_retryable"

        # 2nd attempt via /retry: Success -> creates new audit
        with patch('app.providers.GoogleAdsClient.update_budget') as mock_update:
            mock_update.return_value = {"id": "camp_1", "status": "ENABLED", "daily_budget": 200}
            resp2 = client.post(
                f"/platforms/mutations/{approval.id}/retry",
                headers={"Authorization": f"Bearer {access}"}
            )
            assert resp2.status_code == 200
            
        audits = db_session.query(ExecutionAudit).filter_by(approval_id=approval.id).order_by(ExecutionAudit.id).all()
        assert len(audits) == 2
        assert audits[0].status == "failed_retryable"
        assert audits[1].status == "success"
        assert audits[0].idempotency_key != audits[1].idempotency_key
        
        db_session.refresh(approval)
        assert approval.status == "executed"

def test_retry_on_failed_permanent_rejected(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid, "google", "mock_customer_123")
    
    approval = Approval(
        organization_id=org,
        type="mutation",
        platform="google",
        platform_account_id="mock_customer_123",
        platform_campaign_id="camp_1",
        action="update_budget",
        action_payload=json.dumps({"new_daily_budget": 200}),
        expected_previous_state=json.dumps({"status": "ENABLED", "daily_budget": 100}),
        status="failed",
        requester_id=uid,
        summary="Test perm rejected"
    )
    db_session.add(approval)
    db_session.commit()
    
    audit = ExecutionAudit(
        organization_id=org,
        user_id=uid,
        approval_id=approval.id,
        idempotency_key="test_idem_perm",
        platform="google",
        platform_account_id="mock_customer_123",
        platform_campaign_id="camp_1",
        action="update_budget",
        status="failed_permanent"
    )
    db_session.add(audit)
    db_session.commit()

    resp = client.post(
        f"/platforms/mutations/{approval.id}/retry",
        headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 400
    assert "permanent failure" in resp.json()["detail"] or "not in 'approved' status" in resp.json()["detail"]

def test_duplicate_execution_protection_via_stale_state(db_session):
    access, uid, org = get_tokens("manager")
    setup_connection(db_session, org, uid, "google", "mock_customer_123")
    
    approval = Approval(
        organization_id=org,
        type="mutation",
        platform="google",
        platform_account_id="mock_customer_123",
        platform_campaign_id="camp_1",
        action="pause",
        action_payload=json.dumps({}),
        expected_previous_state=json.dumps({"status": "ENABLED"}),
        status="approved",
        requester_id=uid,
        summary="Test stale state"
    )
    db_session.add(approval)
    db_session.commit()
    
    audit = ExecutionAudit(
        organization_id=org,
        user_id=uid,
        approval_id=approval.id,
        idempotency_key="test_idem_timeout_1",
        platform="google",
        platform_account_id="mock_customer_123",
        platform_campaign_id="camp_1",
        action="pause",
        status="failed_retryable"
    )
    db_session.add(audit)
    db_session.commit()

    with patch("app.services_execution.CredentialService.get_access_token_and_customers", return_value=("mock_token", ["mock_customer_123"])):
        with patch('app.providers.GoogleAdsClient.get_campaign') as mock_get:
            mock_get.return_value = {"id": "camp_1", "status": "PAUSED"}
            
            resp = client.post(
                f"/platforms/mutations/{approval.id}/retry",
                headers={"Authorization": f"Bearer {access}"}
            )
            
            assert resp.status_code == 409
            assert "Campaign state changed externally" in resp.json()["detail"]

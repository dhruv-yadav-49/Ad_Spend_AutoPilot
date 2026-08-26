from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db
from app.models import Organization, User, Campaign, Approval, AutomationEvent
from app.security import hash_password
from datetime import datetime, timezone
from sqlalchemy.pool import StaticPool
from unittest.mock import patch
from sqlalchemy import select

import conftest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base

client = TestClient(app)

def setup_module(module):
    Base.metadata.drop_all(bind=conftest.engine)
    Base.metadata.create_all(bind=conftest.engine)
    db = conftest.TestingSessionLocal()
    
    org_alpha = Organization(name="Org Alpha", invite_code="alpha_invite", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    org_beta = Organization(name="Org Beta", invite_code="beta_invite", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add_all([org_alpha, org_beta])
    db.commit()
    db.refresh(org_alpha)
    db.refresh(org_beta)
    
    manager_alpha = User(name="Manager Alpha", email="mgr@alpha.com", password_hash=hash_password("pw"), role="manager", organization_id=org_alpha.id)
    analyst_alpha = User(name="Analyst Alpha", email="ana@alpha.com", password_hash=hash_password("pw"), role="analyst", organization_id=org_alpha.id)
    manager_beta = User(name="Manager Beta", email="mgr@beta.com", password_hash=hash_password("pw"), role="manager", organization_id=org_beta.id)
    analyst_beta = User(name="Analyst Beta", email="ana@beta.com", password_hash=hash_password("pw"), role="analyst", organization_id=org_beta.id)
    
    db.add_all([manager_alpha, analyst_alpha, manager_beta, analyst_beta])
    db.commit()
    
    c_alpha = Campaign(organization_id=org_alpha.id, name="Alpha Camp", channel="Google Ads", daily_budget=100, spend=50, status="active")
    c_beta = Campaign(organization_id=org_beta.id, name="Beta Camp", channel="Meta Ads", daily_budget=200, spend=100, status="active")
    db.add_all([c_alpha, c_beta])
    db.commit()
    db.refresh(c_alpha)
    db.refresh(c_beta)
    
    a_alpha_pending = Approval(organization_id=org_alpha.id, type="budget", campaign_id=c_alpha.id, requested_by="AI", summary="App 1", impact=10, status="pending")
    a_alpha_approved = Approval(organization_id=org_alpha.id, type="budget", campaign_id=c_alpha.id, requested_by="AI", summary="App 2", impact=10, status="approved")
    a_beta_pending = Approval(organization_id=org_beta.id, type="budget", campaign_id=c_beta.id, requested_by="AI", summary="App 3", impact=20, status="pending")
    
    db.add_all([a_alpha_pending, a_alpha_approved, a_beta_pending])
    db.commit()
    db.close()

def get_token(email):
    res = client.post("/auth/login", json={"email": email, "password": "pw"})
    return res.json()["access_token"]

# 1. Manager can create live campaign.
def test_manager_create_campaign():
    token = get_token("mgr@alpha.com")
    res = client.post("/campaigns", json={"name": "New Alpha", "channel": "Google Ads", "daily_budget": 50}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

# 2. Analyst cannot create live campaign (403).
def test_analyst_cannot_create_campaign():
    token = get_token("ana@alpha.com")
    res = client.post("/campaigns", json={"name": "Bad Alpha", "channel": "Google Ads", "daily_budget": 50}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

# 3. Analyst cannot pause/resume live campaign (403).
def test_analyst_cannot_pause():
    token = get_token("ana@alpha.com")
    res = client.post("/campaigns/1/pause", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

# 4. Manager can pause/resume live campaign.
def test_manager_can_pause():
    token = get_token("mgr@alpha.com")
    res = client.post("/campaigns/1/pause", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

# 5. Manager can approve pending approval.
def test_manager_can_approve():
    token = get_token("mgr@alpha.com")
    res = client.post("/approvals/1", json={"decision": "approved"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

# 6. Analyst cannot approve (403).
def test_analyst_cannot_approve():
    token = get_token("ana@alpha.com")
    # Need another pending approval.
    db = conftest.TestingSessionLocal()
    a = Approval(organization_id=1, type="budget", campaign_id=1, requested_by="AI", summary="Test", impact=5, status="pending")
    db.add(a)
    db.commit()
    db.refresh(a)
    aid = a.id
    db.close()
    
    res = client.post(f"/approvals/{aid}", json={"decision": "approved"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

# 7. Manager can reject pending approval.
def test_manager_can_reject():
    token = get_token("mgr@alpha.com")
    db = conftest.TestingSessionLocal()
    a = Approval(organization_id=1, type="budget", campaign_id=1, requested_by="AI", summary="Test", impact=5, status="pending")
    db.add(a)
    db.commit()
    db.refresh(a)
    aid = a.id
    db.close()
    
    res = client.post(f"/approvals/{aid}", json={"decision": "rejected"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

# 8. Analyst cannot reject (403).
def test_analyst_cannot_reject():
    token = get_token("ana@alpha.com")
    res = client.post("/approvals/1", json={"decision": "rejected"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

# 9. Analyst budget suggestion always creates pending approval (never auto-executes).
def test_analyst_budget_suggestion_always_pending():
    token = get_token("ana@alpha.com")
    # Below 10% threshold (100 -> 105 is 5%)
    res = client.post("/budget/optimize", json={"campaign_id": 1, "new_daily_budget": 105}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["approval_required"] is True

# 10. Manager eligible action preserves existing Phase 1 threshold behavior.
def test_manager_budget_threshold_behavior():
    token = get_token("mgr@alpha.com")
    # Below 10% threshold
    res = client.post("/budget/optimize", json={"campaign_id": 1, "new_daily_budget": 105}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["approval_required"] is False
    # Above 10% threshold
    res = client.post("/budget/optimize", json={"campaign_id": 1, "new_daily_budget": 150}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["approval_required"] is True

# 11. Analyst can submit creative brief suggestion.
@patch("app.services.run_pipeline")
def test_analyst_submit_creative(mock_run):
    mock_run.return_value = "Mocked output"
    token = get_token("ana@alpha.com")
    res = client.post("/creative/brief", json={"campaign_id": 1, "objective": "More sales"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code != 403
    assert res.status_code != 401

# 12. Analyst can submit brand safety review.
@patch("app.services.run_pipeline")
def test_analyst_submit_brand_safety(mock_run):
    mock_run.return_value = "Mocked output"
    token = get_token("ana@alpha.com")
    res = client.post("/brand-safety/review", json={"text": "Guaranteed results"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code != 403
    assert res.status_code != 401

# 13. Org Alpha manager cannot approve Org Beta approval (404/403).
def test_alpha_manager_cannot_approve_beta():
    token = get_token("mgr@alpha.com")
    res = client.post("/approvals/3", json={"decision": "approved"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404

# 14. Org Alpha analyst cannot approve Org Beta approval (404/403).
def test_alpha_analyst_cannot_approve_beta():
    token = get_token("ana@alpha.com")
    res = client.post("/approvals/3", json={"decision": "approved"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403 # role check happens first, then it returns 403.

# 15. Unauthenticated manager-only action returns 401.
def test_unauthenticated_manager_action():
    res = client.post("/campaigns", json={"name": "Bad", "channel": "Google Ads", "daily_budget": 50})
    assert res.status_code == 401

# 16. Forged organization_id in POST payloads cannot bypass tenant isolation.
def test_forged_org_id_creation():
    token = get_token("mgr@alpha.com")
    # Payload has organization_id=2 (Beta)
    res = client.post("/campaigns", json={"name": "Sneaky", "channel": "Google Ads", "daily_budget": 50, "organization_id": 2}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    c_id = res.json()["id"]
    db = conftest.TestingSessionLocal()
    c = db.scalar(select(Campaign).where(Campaign.id == c_id))
    assert c.organization_id == 1  # Should be forced to Alpha (1)
    db.close()

# 19. Already-approved/rejected approval cannot be executed again.
def test_already_approved_cannot_be_executed_again():
    token = get_token("mgr@alpha.com")
    res = client.post("/approvals/2", json={"decision": "approved"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert res.json()["detail"] == "Approval is not pending"

# 20. Org Alpha manager cannot approve Org Beta approval even if the approval ID is supplied directly.
def test_manager_cannot_approve_other_tenant_even_direct():
    token = get_token("mgr@alpha.com")
    # Approval 3 belongs to Beta
    res = client.post("/approvals/3", json={"decision": "approved"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404

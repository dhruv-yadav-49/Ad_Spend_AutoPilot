from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db
from app.models import Organization, User, Campaign, Approval, AutomationEvent, Creative
from app.security import hash_password
import secrets
from datetime import datetime, timezone

import conftest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base

client = TestClient(app)

def setup_module(module):
    Base.metadata.drop_all(bind=conftest.engine)
    Base.metadata.create_all(bind=conftest.engine)
    db = conftest.TestingSessionLocal()
    
    # Org Alpha
    org_alpha = Organization(name="Org Alpha", invite_code="alpha_invite", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    org_beta = Organization(name="Org Beta", invite_code="beta_invite", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add_all([org_alpha, org_beta])
    db.commit()
    db.refresh(org_alpha)
    db.refresh(org_beta)
    
    # Users
    user_alpha = User(name="Alpha Mgr", email="a@a.com", password_hash=hash_password("pw"), role="manager", organization_id=org_alpha.id)
    user_beta = User(name="Beta Mgr", email="b@b.com", password_hash=hash_password("pw"), role="manager", organization_id=org_beta.id)
    db.add_all([user_alpha, user_beta])
    db.commit()
    
    # Data
    c_alpha = Campaign(organization_id=org_alpha.id, name="Alpha Camp", channel="Google Ads", daily_budget=100, spend=50)
    c_beta = Campaign(organization_id=org_beta.id, name="Beta Camp", channel="Meta Ads", daily_budget=200, spend=100)
    db.add_all([c_alpha, c_beta])
    db.commit()
    db.refresh(c_alpha)
    db.refresh(c_beta)
    
    a_alpha = Approval(organization_id=org_alpha.id, type="budget", campaign_id=c_alpha.id, requested_by="AI", summary="Alpha app", impact=10)
    a_beta = Approval(organization_id=org_beta.id, type="budget", campaign_id=c_beta.id, requested_by="AI", summary="Beta app", impact=20)
    db.add_all([a_alpha, a_beta])
    db.commit()
    
    e_alpha = AutomationEvent(organization_id=org_alpha.id, action="Event Alpha", campaign_name="Alpha Camp", reason="test")
    e_beta = AutomationEvent(organization_id=org_beta.id, action="Event Beta", campaign_name="Beta Camp", reason="test")
    db.add_all([e_alpha, e_beta])
    db.commit()
    db.close()

def get_token(email="a@a.com", password="pw"):
    res = client.post("/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]

def test_alpha_cannot_get_beta_campaign():
    token = get_token("a@a.com")
    res = client.post("/campaigns/2/pause", headers={"Authorization": f"Bearer {token}"})
    # Since ID=2 belongs to Beta, Alpha shouldn't find it. Should be 404 per API convention.
    assert res.status_code == 404

def test_alpha_cannot_get_beta_approval():
    token = get_token("a@a.com")
    res = client.post("/approvals/2", json={"decision": "approved"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404

def test_alpha_cannot_access_beta_events():
    token = get_token("a@a.com")
    res = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    data = res.json()
    for e in data["recent_events"]:
        assert "Alpha" in e["campaign"]
        assert "Beta" not in e["campaign"]

def test_query_param_isolation():
    token = get_token("a@a.com")
    # Even if trying to pass organization_id manually (which isn't accepted anyway), it shouldn't leak
    res = client.get("/dashboard?organization_id=2", headers={"Authorization": f"Bearer {token}"})
    data = res.json()
    assert data["kpis"]["total_spend"] == 50.0  # Only Alpha spend

def test_dashboard_does_not_leak():
    token = get_token("b@b.com")
    res = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    data = res.json()
    assert data["kpis"]["total_spend"] == 100.0  # Only Beta spend
    
def test_signup_invalid_invite_code():
    res = client.post("/auth/signup", json={
        "name": "New User",
        "email": "new@a.com",
        "password": "pw",
        "invite_code": "wrong_code"
    })
    assert res.status_code == 400
    assert "Invalid invite code" in res.json()["detail"]

def test_signup_valid_invite_code():
    res = client.post("/auth/signup", json={
        "name": "New Analyst",
        "email": "analyst@beta.com",
        "password": "pw",
        "invite_code": "beta_invite"
    })
    assert res.status_code == 200
    
    # Verify user joined correct org
    token = get_token("analyst@beta.com")
    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200

def test_user_cannot_join_by_guessing_id():
    # The API doesn't accept organization_id anymore, only organization_name or invite_code
    res = client.post("/auth/signup", json={
        "name": "Hacker",
        "email": "hacker@h.com",
        "password": "pw",
        "organization_id": 1  # Should be ignored or rejected
    })
    # Since neither organization_name nor invite_code is provided, it should fail
    assert res.status_code == 400
    assert "exactly one" in res.json()["detail"]

def test_signup_create_org():
    res = client.post("/auth/signup", json={
        "name": "Org Creator",
        "email": "creator@new.com",
        "password": "pw",
        "organization_name": "New Org"
    })
    assert res.status_code == 200

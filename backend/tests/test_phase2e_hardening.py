from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def get_tokens(role):
    # Depending on role, we use existing seeded users. The DB is seeded via conftest in test_authorization but since this is a separate file it might not be seeded?
    # Actually wait! The conftest.py drops the DB, so we must seed it or use signup.
    res = client.post("/auth/signup", json={
        "name": f"Hardening {role}",
        "email": f"{role}_hard@test.com",
        "password": "pw",
        "organization_name": f"Org {role}"
    })
    # If 400, maybe it already exists.
    login = client.post("/auth/login", json={"email": f"{role}_hard@test.com", "password": "pw"})
    data = login.json()
    return data["access_token"], login.cookies.get("refresh_token")

def test_invalid_refresh_token():
    res = client.post("/auth/refresh")
    assert res.status_code == 401
    
    client.cookies.set("refresh_token", "invalid.jwt.token")
    res = client.post("/auth/refresh")
    assert res.status_code == 401

def test_revoked_refresh_token():
    access, refresh = get_tokens("manager1")
    client.cookies.set("refresh_token", refresh)
    
    # Logout
    res = client.post("/auth/logout", headers={"Authorization": f"Bearer {access}"})
    assert res.status_code == 200
    
    # Try using old refresh token
    res2 = client.post("/auth/refresh", cookies={"refresh_token": refresh})
    assert res2.status_code == 401
    assert "revoked" in res2.json()["detail"].lower()

def test_rate_limiting():
    # temporarily re-enable rate limiter
    app.state.limiter.enabled = True
    try:
        payload = {"email": "manager_hard@test.com", "password": "pw"}
        for _ in range(5):
            client.post("/auth/login", json=payload)
            
        res = client.post("/auth/login", json=payload)
        assert res.status_code == 429
    finally:
        app.state.limiter.enabled = False

def test_spend_safety_limits():
    access, _ = get_tokens("manager2")
    headers = {"Authorization": f"Bearer {access}"}
    
    # Need a campaign first
    res = client.post("/campaigns", json={"name": "Hard Campaign", "channel": "search", "daily_budget": 100}, headers=headers)
    assert res.status_code == 200
    cid = res.json()["id"]
    
    # Negative budget (caught by Pydantic validation)
    res = client.post("/budget/optimize", json={"campaign_id": cid, "new_daily_budget": -500}, headers=headers)
    assert res.status_code == 422
    
    # Zero budget (caught by Pydantic validation)
    res = client.post("/budget/optimize", json={"campaign_id": cid, "new_daily_budget": 0}, headers=headers)
    assert res.status_code == 422
    
    # Hard cap exceeded
    res = client.post("/budget/optimize", json={"campaign_id": cid, "new_daily_budget": 15000}, headers=headers)
    assert res.status_code == 400
    
    # Request valid change that triggers approval
    res = client.post("/budget/optimize", json={"campaign_id": cid, "new_daily_budget": 8000}, headers=headers)
    assert res.status_code == 200
    app_id = res.json()["approval_id"]
    
    # Temporarily lower the global cap to test execution-time validation
    import app.config as config
    import app.main as main_app
    old_cap = config.settings.MAX_DAILY_BUDGET_USD
    config.settings.MAX_DAILY_BUDGET_USD = 7000
    main_app.settings.MAX_DAILY_BUDGET_USD = 7000
    try:
        res = client.post(f"/approvals/{app_id}", json={"decision": "approved"}, headers=headers)
        assert res.status_code == 400
        assert "exceeds hard cap" in res.json()["detail"].lower()
    finally:
        config.settings.MAX_DAILY_BUDGET_USD = old_cap
        main_app.settings.MAX_DAILY_BUDGET_USD = old_cap

from app.worker import refresh_campaign_metrics
def test_background_worker_isolation():
    res = refresh_campaign_metrics(campaign_id=1, org_id=9999)
    assert res["status"] == "error"

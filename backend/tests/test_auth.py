from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_signup_success():
    res = client.post("/auth/signup", json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "securepassword",
        "organization_name": "Test Org"
    })
    assert res.status_code == 200
    assert res.json()["message"] == "User created successfully"

def test_signup_duplicate_email():
    res = client.post("/auth/signup", json={
        "name": "Test User 2",
        "email": "test@example.com",
        "password": "anotherpassword",
        "organization_name": "Test Org 2"
    })
    assert res.status_code == 400

def test_login_success():
    res = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "securepassword"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["user"]["email"] == "test@example.com"
    # Check if refresh token cookie is set
    cookies = res.cookies
    assert "refresh_token" in cookies

def test_login_invalid_password():
    res = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })
    assert res.status_code == 401

def test_refresh_success():
    # First login
    login_res = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "securepassword"
    })
    assert login_res.status_code == 200
    refresh_cookie = login_res.cookies.get("refresh_token")
    
    # Then refresh
    res = client.post("/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_refresh_missing_token():
    client.cookies.clear()
    res = client.post("/auth/refresh")
    assert res.status_code == 401

def test_get_me_success():
    # First login
    login_res = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "securepassword"
    })
    token = login_res.json()["access_token"]
    
    # Then get me
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"

def test_get_me_no_token():
    res = client.get("/auth/me")
    assert res.status_code == 401

def test_logout():
    # First login
    login_res = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "securepassword"
    })
    token = login_res.json()["access_token"]
    
    res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    # Cookie should be deleted/expired
    cookies = res.headers.get("set-cookie", "")
    assert "Max-Age=0" in cookies or "expires" in cookies.lower()

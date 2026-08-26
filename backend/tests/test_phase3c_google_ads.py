import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from app.main import app
from app.config import settings
from app.providers import GoogleAdsClient
from app.credentials import CredentialService

client = TestClient(app)

@pytest.fixture
def mock_settings():
    original_mode = settings.GOOGLE_ADS_MOCK_MODE
    yield settings
    settings.GOOGLE_ADS_MOCK_MODE = original_mode

def test_google_ads_client_error_mapping(mock_settings):
    mock_settings.GOOGLE_ADS_MOCK_MODE = False
    
    # We don't want to actually import google-ads if it's not installed in the test environment,
    # but since it's in requirements.txt, it should be installed.
    # We will mock the client initialization.
    with patch("app.providers.GoogleAdsClient.__init__", return_value=None):
        ga_client = GoogleAdsClient("dummy")
        ga_client.client = MagicMock()
        
        # Test 401 Unauthorized
        class MockAuthError(Exception):
            pass
        
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc:
            ga_client._handle_error(Exception("401 Unauthorized"))
        assert exc.value.status_code == 401
        
        with pytest.raises(HTTPException) as exc:
            ga_client._handle_error(Exception("429 Too Many Requests"))
        assert exc.value.status_code == 429
        
        with pytest.raises(HTTPException) as exc:
            ga_client._handle_error(Exception("Some other random 500 error"))
        assert exc.value.status_code == 500

@patch("httpx.post")
def test_real_token_refresh(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new_real_access_token",
        "expires_in": 3600
    }
    mock_post.return_value = mock_response
    
    settings.GOOGLE_ADS_MOCK_MODE = False
    settings.GOOGLE_ADS_CLIENT_ID = "test_client_id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "test_secret"
    
    # Create a mock connection
    class MockConnection:
        platform = "google"
        encrypted_refresh_token = b"dummy_refresh" # Will fail decryption, so let's mock decrypt_token
        
    connection = MockConnection()
    
    with patch("app.credentials.decrypt_token", return_value="real_refresh_token"), \
         patch("app.credentials.encrypt_token", return_value=b"new_encrypted_access"):
         
        mock_db = MagicMock()
        new_token = CredentialService._refresh_token(mock_db, connection)
        
        assert new_token == "new_real_access_token"
        assert connection.encrypted_access_token == b"new_encrypted_access"
        assert hasattr(connection, "expires_at")
        mock_db.commit.assert_called_once()
        
        mock_post.assert_called_once_with(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "refresh_token": "real_refresh_token",
                "grant_type": "refresh_token"
            }
        )

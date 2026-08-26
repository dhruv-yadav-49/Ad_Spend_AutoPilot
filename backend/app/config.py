from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str = "sqlite:///./adspend.db"
    JWT_SECRET: str = "dev-secret-change-me-very-long"
    JWT_ACCESS_EXPIRY_MINUTES: int = 15
    JWT_REFRESH_EXPIRY_DAYS: int = 7
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173"
    REDIS_URL: str = "redis://localhost:6379/0"
    ROCKETRIDE_URI: str = "ws://localhost:5565"
    ROCKETRIDE_APIKEY: str = ""
    MAX_DAILY_BUDGET_USD: float = 10000.0
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    CREDENTIAL_ENCRYPTION_KEY: str
    GOOGLE_ADS_MOCK_MODE: bool = False
    
    # Google Ads Configuration
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    GOOGLE_ADS_CLIENT_ID: str = ""
    GOOGLE_ADS_CLIENT_SECRET: str = ""
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = ""
    
    # Meta Ads Configuration
    META_ADS_CLIENT_ID: str = ""
    META_ADS_CLIENT_SECRET: str = ""
    META_GRAPH_API_VERSION: str = "v18.0"
    META_ADS_MOCK_MODE: bool = False

settings = Settings()

if not settings.CREDENTIAL_ENCRYPTION_KEY:
    raise ValueError("CREDENTIAL_ENCRYPTION_KEY is missing! Must be a 32-byte base64-encoded string.")

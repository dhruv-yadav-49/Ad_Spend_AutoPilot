from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str = "sqlite:///./adspend.db"
    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    REDIS_URL: str = "redis://localhost:6379/0"
    ROCKETRIDE_URI: str = "ws://localhost:5565"
    ROCKETRIDE_APIKEY: str = ""
settings = Settings()

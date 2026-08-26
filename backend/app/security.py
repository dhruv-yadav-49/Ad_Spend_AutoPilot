from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from .config import settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p): return pwd.hash(p)
def verify_password(p, h): return pwd.verify(p, h)

def create_access_token(sub: str):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_EXPIRY_MINUTES)
    return jwt.encode({"sub": sub, "type": "access", "exp": exp}, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(sub: str, version: int = 1):
    exp = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRY_DAYS)
    return jwt.encode({"sub": sub, "type": "refresh", "version": version, "exp": exp}, settings.JWT_SECRET, algorithm="HS256")

def verify_token(token: str, token_type: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != token_type:
            return None
        return payload
    except JWTError:
        return None

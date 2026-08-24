from datetime import datetime,timedelta,timezone
from jose import jwt
from passlib.context import CryptContext
from .config import settings
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
def hash_password(p): return pwd.hash(p)
def verify_password(p,h): return pwd.verify(p,h)
def create_token(sub):
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub":sub,"exp":exp},settings.SECRET_KEY,algorithm="HS256")

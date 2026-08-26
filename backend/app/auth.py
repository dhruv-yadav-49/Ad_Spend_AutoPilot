from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select
import secrets
from .db import get_db
from .models import User, Organization
from .schemas import LoginRequest, SignupRequest, Token, UserResponse
from .security import hash_password, verify_password, create_access_token, create_refresh_token, verify_token
from .config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])

def get_current_user(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif request.query_params.get("token"):
        token = request.query_params.get("token")
        
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_token(token, "access")
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    email = payload.get("sub")
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
    return user

@router.post("/signup")
@limiter.limit("5/minute")
def signup(request: Request, payload: SignupRequest, db: Session = Depends(get_db)):
    if bool(payload.organization_name) == bool(payload.invite_code):
        raise HTTPException(status_code=400, detail="Must provide exactly one of organization_name or invite_code")
        
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    if payload.organization_name:
        # Create new org, user becomes manager
        org = Organization(name=payload.organization_name, invite_code=secrets.token_urlsafe(16))
        db.add(org)
        db.flush() # get org.id
        role = "manager"
    else:
        # Join via invite code, user becomes analyst
        org = db.scalar(select(Organization).where(Organization.invite_code == payload.invite_code))
        if not org:
            raise HTTPException(status_code=400, detail="Invalid invite code")
        role = "analyst"
        
    new_user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        organization_id=org.id,
        role=role
    )
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    access_token = create_access_token(user.email)
    refresh_token = create_refresh_token(user.email, user.refresh_token_version)
    
    # Set httpOnly cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.JWT_REFRESH_EXPIRY_DAYS * 24 * 60 * 60
    )
    
    org = db.scalar(select(Organization).where(Organization.id == user.organization_id))
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id, 
            "name": user.name, 
            "email": user.email, 
            "role": user.role, 
            "organization_id": user.organization_id, 
            "organization_name": org.name if org else ""
        }
    }

def require_role(required_role: str):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(status_code=403, detail=f"{required_role.capitalize()} role required")
        return current_user
    return role_checker

@router.post("/refresh")
@limiter.limit("5/minute")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    payload = verify_token(refresh_token, "refresh")
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        
    email = payload.get("sub")
    version = payload.get("version")
        
    user = db.scalar(select(User).where(User.email == email))
    if not user or user.refresh_token_version != version:
        raise HTTPException(status_code=401, detail="Refresh token revoked or invalid")
        
    access_token = create_access_token(user.email)
    new_refresh_token = create_refresh_token(user.email, user.refresh_token_version)
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.JWT_REFRESH_EXPIRY_DAYS * 24 * 60 * 60
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.refresh_token_version += 1
    db.commit()
    response.delete_cookie("refresh_token", secure=settings.COOKIE_SECURE, httponly=True, samesite=settings.COOKIE_SAMESITE)
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.scalar(select(Organization).where(Organization.id == current_user.organization_id))
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "organization_id": current_user.organization_id,
        "organization_name": org.name if org else ""
    }

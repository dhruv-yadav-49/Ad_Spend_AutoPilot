from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    invite_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="analyst")
    refresh_token_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Campaign(Base):
    __tablename__="campaigns"
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name:Mapped[str]=mapped_column(String(180))
    channel:Mapped[str]=mapped_column(String(60))
    audience:Mapped[str]=mapped_column(String(120),default="General")
    status:Mapped[str]=mapped_column(String(30),default="active")
    daily_budget:Mapped[float]=mapped_column(Float,default=1000)
    spend:Mapped[float]=mapped_column(Float,default=0)
    conversions:Mapped[int]=mapped_column(Integer,default=0)
    revenue:Mapped[float]=mapped_column(Float,default=0)
    roas:Mapped[float]=mapped_column(Float,default=0)
    cpa:Mapped[float]=mapped_column(Float,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Creative(Base):
    __tablename__="creatives"
    id:Mapped[int]=mapped_column(primary_key=True)
    campaign_id:Mapped[int]=mapped_column(ForeignKey("campaigns.id"))
    title:Mapped[str]=mapped_column(String(180))
    message:Mapped[str]=mapped_column(Text)
    format:Mapped[str]=mapped_column(String(60))
    score:Mapped[float]=mapped_column(Float,default=0)

class Approval(Base):
    __tablename__="approvals"
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    type:Mapped[str]=mapped_column(String(80))
    campaign_id:Mapped[int|None]=mapped_column(ForeignKey("campaigns.id"),nullable=True)
    requested_by:Mapped[str]=mapped_column(String(120),default="AI Autopilot")
    summary:Mapped[str]=mapped_column(Text)
    impact:Mapped[float]=mapped_column(Float,default=0)
    status:Mapped[str]=mapped_column(String(30),default="pending")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    
    # Phase 4A fields
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    platform_account_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    platform_campaign_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class ExecutionAudit(Base):
    __tablename__ = "execution_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approval_id: Mapped[int | None] = mapped_column(ForeignKey("approvals.id"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(50))
    platform_account_id: Mapped[str] = mapped_column(String(200))
    platform_campaign_id: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AutomationEvent(Base):
    __tablename__="automation_events"
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    action:Mapped[str]=mapped_column(String(100))
    campaign_name:Mapped[str]=mapped_column(String(180))
    reason:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default="executed")
    
    # Audit fields
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), server_default="1")
    role: Mapped[str] = mapped_column(String(40), server_default="system")
    old_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(ForeignKey("approvals.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AdPlatformConnection(Base):
    __tablename__="ad_platform_connections"
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    platform: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="active")
    encrypted_access_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    external_account_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # We might have multiple accounts per platform, but the user requested unique constraint later when external_account_id exists
    # Currently SQLite batch mode handles constraints differently, but for now we won't add a unique constraint until we actively use external_account_id.

class OAuthState(Base):
    __tablename__="oauth_states"
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    platform: Mapped[str] = mapped_column(String(50))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

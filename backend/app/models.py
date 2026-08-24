from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120))
    email:Mapped[str]=mapped_column(String(160),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    role:Mapped[str]=mapped_column(String(40),default="admin")

class Campaign(Base):
    __tablename__="campaigns"
    id:Mapped[int]=mapped_column(primary_key=True)
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
    type:Mapped[str]=mapped_column(String(80))
    campaign_id:Mapped[int|None]=mapped_column(ForeignKey("campaigns.id"),nullable=True)
    requested_by:Mapped[str]=mapped_column(String(120),default="AI Autopilot")
    summary:Mapped[str]=mapped_column(Text)
    impact:Mapped[float]=mapped_column(Float,default=0)
    status:Mapped[str]=mapped_column(String(30),default="pending")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AutomationEvent(Base):
    __tablename__="automation_events"
    id:Mapped[int]=mapped_column(primary_key=True)
    action:Mapped[str]=mapped_column(String(100))
    campaign_name:Mapped[str]=mapped_column(String(180))
    reason:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default="executed")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

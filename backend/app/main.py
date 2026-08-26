from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base, engine, get_db
from .models import User, Campaign, Approval, AutomationEvent
from .schemas import CampaignCreate, BudgetAction, ApprovalDecision, CreativeBriefRequest, SafetyRequest
from .seed import seed
from .services import dashboard_payload, optimize_budget, creative_brief, safety_review
from .config import settings
from .auth import router as auth_router, get_current_user, require_role, limiter
from .routers import platforms, mutations
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="Ad Spend Autopilot API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router)
app.include_router(platforms.router)
app.include_router(mutations.router)
app.add_middleware(CORSMiddleware, allow_origins=[settings.CORS_ORIGINS, "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
# Alembic and seed.py handle DB initialization now
@app.get("/health")
def health():return {"status":"ok"}
@app.get("/dashboard")
def dashboard(db:Session=Depends(get_db), current_user: User = Depends(get_current_user)):
    return dashboard_payload(db, current_user.organization_id)
@app.get("/campaigns")
def campaigns(db:Session=Depends(get_db), current_user: User = Depends(get_current_user)):
    return dashboard_payload(db, current_user.organization_id)["campaigns"]
@app.post("/campaigns")
def create(p:CampaignCreate,db:Session=Depends(get_db), current_user: User = Depends(require_role("manager"))):
    c=Campaign(**p.model_dump(), organization_id=current_user.organization_id)
    db.add(c);db.commit();db.refresh(c);return {"id":c.id,"message":"Campaign created"}
@app.post("/campaigns/{id}/pause")
def pause(id:int,db:Session=Depends(get_db), current_user: User = Depends(require_role("manager"))):
    c=db.scalar(select(Campaign).where(Campaign.id == id, Campaign.organization_id == current_user.organization_id))
    if not c:raise HTTPException(404,"Campaign not found")
    c.status="paused";db.add(AutomationEvent(action="Campaign paused",organization_id=current_user.organization_id,campaign_name=c.name,reason="Manual action"));db.commit();return {"message":"Campaign paused"}
@app.post("/campaigns/{id}/resume")
def resume(id:int,db:Session=Depends(get_db), current_user: User = Depends(require_role("manager"))):
    c=db.scalar(select(Campaign).where(Campaign.id == id, Campaign.organization_id == current_user.organization_id))
    if not c:raise HTTPException(404,"Campaign not found")
    c.status="active";db.commit();return {"message":"Campaign resumed"}
@app.post("/budget/optimize")
def budget(p:BudgetAction,db:Session=Depends(get_db), current_user: User = Depends(get_current_user)):
    r,e=optimize_budget(db,p.campaign_id,p.new_daily_budget,current_user.organization_id, current_user.id, current_user.role)
    if e:raise HTTPException(400,e)
    return r
@app.get("/approvals")
def approvals(db:Session=Depends(get_db), current_user: User = Depends(get_current_user)):
    return [{"id":a.id,"type":a.type,"summary":a.summary,"impact":a.impact,"status":a.status,"requested_by":a.requested_by} for a in db.query(Approval).filter(Approval.organization_id == current_user.organization_id).order_by(Approval.created_at.desc()).all()]
@app.post("/approvals/{id}")
def decide(id:int,p:ApprovalDecision,db:Session=Depends(get_db), current_user: User = Depends(require_role("manager"))):
    a=db.scalar(select(Approval).where(Approval.id == id, Approval.organization_id == current_user.organization_id))
    if not a:raise HTTPException(404,"Approval not found")
    if a.status != "pending": raise HTTPException(400, "Approval is not pending")
    
    if p.decision=="approved" and a.campaign_id:
        c=db.scalar(select(Campaign).where(Campaign.id == a.campaign_id, Campaign.organization_id == current_user.organization_id))
        if c:
            new_budget = c.daily_budget + a.impact
            # FINAL SAFETY CHECK
            if new_budget > settings.MAX_DAILY_BUDGET_USD:
                raise HTTPException(400, f"Cannot execute: budget ${new_budget} exceeds hard cap of ${settings.MAX_DAILY_BUDGET_USD}")
                
            old = c.daily_budget
            c.daily_budget=max(1,new_budget)
            db.add(AutomationEvent(action="Approved budget change",organization_id=current_user.organization_id,campaign_name=c.name,reason=a.summary,status="executed",role="manager",old_budget=old,new_budget=c.daily_budget,approval_id=a.id,approved_by=current_user.id))
            
    a.status=p.decision
    db.commit();return {"message":f"Approval {p.decision}"}
@app.post("/creative/brief")
async def brief(p:CreativeBriefRequest,db:Session=Depends(get_db), current_user: User = Depends(get_current_user)):
    r=await creative_brief(db,p.campaign_id,p.objective,current_user.organization_id)
    if not r:raise HTTPException(404,"Campaign not found")
    return r
@app.post("/brand-safety/review")
async def safety(p:SafetyRequest, current_user: User = Depends(get_current_user)):return await safety_review(p.text)
@app.get("/reports/attribution")
def attribution(db:Session=Depends(get_db), current_user: User = Depends(get_current_user)):
    return [{"channel":c.channel,"conversions":c.conversions,"revenue":c.revenue,"spend":c.spend,"roas":c.roas} for c in db.query(Campaign).filter(Campaign.organization_id == current_user.organization_id).all()]

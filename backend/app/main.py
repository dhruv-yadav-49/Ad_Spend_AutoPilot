from fastapi import FastAPI,Depends,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base,engine,get_db
from .models import User,Campaign,Approval,AutomationEvent
from .schemas import LoginRequest,CampaignCreate,BudgetAction,ApprovalDecision,CreativeBriefRequest,SafetyRequest
from .security import verify_password,create_token
from .seed import seed
from .services import dashboard_payload,optimize_budget,creative_brief,safety_review
from .config import settings

app=FastAPI(title="Ad Spend Autopilot API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=[settings.FRONTEND_ORIGIN,"*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db=next(get_db());seed(db);db.close()
@app.get("/health")
def health():return {"status":"ok"}
@app.post("/auth/login")
def login(p:LoginRequest,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==p.email))
    if not u or not verify_password(p.password,u.password_hash):raise HTTPException(401,"Invalid credentials")
    return {"access_token":create_token(u.email),"token_type":"bearer","user":{"name":u.name,"email":u.email,"role":u.role}}
@app.get("/dashboard")
def dashboard(db:Session=Depends(get_db)):return dashboard_payload(db)
@app.get("/campaigns")
def campaigns(db:Session=Depends(get_db)):return dashboard_payload(db)["campaigns"]
@app.post("/campaigns")
def create(p:CampaignCreate,db:Session=Depends(get_db)):
    c=Campaign(**p.model_dump());db.add(c);db.commit();db.refresh(c);return {"id":c.id,"message":"Campaign created"}
@app.post("/campaigns/{id}/pause")
def pause(id:int,db:Session=Depends(get_db)):
    c=db.get(Campaign,id)
    if not c:raise HTTPException(404,"Campaign not found")
    c.status="paused";db.add(AutomationEvent(action="Campaign paused",campaign_name=c.name,reason="Manual action"));db.commit();return {"message":"Campaign paused"}
@app.post("/campaigns/{id}/resume")
def resume(id:int,db:Session=Depends(get_db)):
    c=db.get(Campaign,id)
    if not c:raise HTTPException(404,"Campaign not found")
    c.status="active";db.commit();return {"message":"Campaign resumed"}
@app.post("/budget/optimize")
def budget(p:BudgetAction,db:Session=Depends(get_db)):
    r,e=optimize_budget(db,p.campaign_id,p.new_daily_budget)
    if e:raise HTTPException(404,e)
    return r
@app.get("/approvals")
def approvals(db:Session=Depends(get_db)):
    return [{"id":a.id,"type":a.type,"summary":a.summary,"impact":a.impact,"status":a.status,"requested_by":a.requested_by} for a in db.query(Approval).order_by(Approval.created_at.desc()).all()]
@app.post("/approvals/{id}")
def decide(id:int,p:ApprovalDecision,db:Session=Depends(get_db)):
    a=db.get(Approval,id)
    if not a:raise HTTPException(404,"Approval not found")
    a.status=p.decision
    if p.decision=="approved" and a.campaign_id:
        c=db.get(Campaign,a.campaign_id);c.daily_budget=max(1,c.daily_budget+a.impact)
        db.add(AutomationEvent(action="Approved budget change",campaign_name=c.name,reason=a.summary))
    db.commit();return {"message":f"Approval {p.decision}"}
@app.post("/creative/brief")
async def brief(p:CreativeBriefRequest,db:Session=Depends(get_db)):
    r=await creative_brief(db,p.campaign_id,p.objective)
    if not r:raise HTTPException(404,"Campaign not found")
    return r
@app.post("/brand-safety/review")
async def safety(p:SafetyRequest):return await safety_review(p.text)
@app.get("/reports/attribution")
def attribution(db:Session=Depends(get_db)):
    return [{"channel":c.channel,"conversions":c.conversions,"revenue":c.revenue,"spend":c.spend,"roas":c.roas} for c in db.query(Campaign).all()]

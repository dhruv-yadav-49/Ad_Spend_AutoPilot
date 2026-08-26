import secrets
from datetime import datetime, timezone
from sqlalchemy import select
from .models import User, Campaign, Creative, Approval, AutomationEvent, Organization
from .security import hash_password

def seed(db):
    if db.query(Organization).first(): return

    # Create Organizations
    org_alpha = Organization(name="Org Alpha", invite_code=secrets.token_urlsafe(16), created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    org_beta = Organization(name="Org Beta", invite_code=secrets.token_urlsafe(16), created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add_all([org_alpha, org_beta])
    db.flush()

    # Create Users for Org Alpha
    alpha_manager = User(name="Alpha Manager", email="manager@orga.demo", password_hash=hash_password("Manager@123"), role="manager", organization_id=org_alpha.id)
    alpha_analyst = User(name="Alpha Analyst", email="analyst@orga.demo", password_hash=hash_password("Analyst@123"), role="analyst", organization_id=org_alpha.id)
    
    # Create Users for Org Beta
    beta_manager = User(name="Beta Manager", email="manager@orgb.demo", password_hash=hash_password("Manager@123"), role="manager", organization_id=org_beta.id)
    beta_analyst = User(name="Beta Analyst", email="analyst@orgb.demo", password_hash=hash_password("Analyst@123"), role="analyst", organization_id=org_beta.id)
    
    db.add_all([alpha_manager, alpha_analyst, beta_manager, beta_analyst])
    db.flush()

    # Create Campaigns for Org Alpha
    alpha_rows=[
      ("Alpha Summer Sale","Google Ads","High-intent shoppers",18000,45231,3642,245000,5.42,12.42),
      ("Alpha Retargeting","Meta Ads","Site visitors",14000,38762,4214,189000,4.88,9.20)
    ]
    alpha_cs=[]
    for r in alpha_rows:
        c=Campaign(organization_id=org_alpha.id,name=r[0],channel=r[1],audience=r[2],daily_budget=r[3],spend=r[4],conversions=r[5],revenue=r[6],roas=r[7],cpa=r[8])
        db.add(c);db.flush();alpha_cs.append(c)
        
    for c in alpha_cs:
        db.add(Creative(campaign_id=c.id,title=f"{c.name} Creative",message="Lead with measurable benefit",format="Video",score=c.roas))
        
    db.add(Approval(organization_id=org_alpha.id,type="budget_change",campaign_id=alpha_cs[0].id,summary="Increase Google Ads budget",impact=15000))
    db.add(AutomationEvent(organization_id=org_alpha.id,action="Creative brief generated",campaign_name="Alpha Summer Sale",reason="New test based on winning benefit-led creative"))

    # Create Campaigns for Org Beta
    beta_rows=[
      ("Beta Brand Awareness","TikTok Ads","Gen Z",8000,18231,1280,39000,2.14,14.24),
      ("Beta LinkedIn B2B","LinkedIn Ads","Marketing leaders",7000,14287,682,54000,3.78,20.95)
    ]
    beta_cs=[]
    for r in beta_rows:
        c=Campaign(organization_id=org_beta.id,name=r[0],channel=r[1],audience=r[2],daily_budget=r[3],spend=r[4],conversions=r[5],revenue=r[6],roas=r[7],cpa=r[8])
        db.add(c);db.flush();beta_cs.append(c)
        
    for c in beta_cs:
        db.add(Creative(campaign_id=c.id,title=f"{c.name} Creative",message="Lead with direct CTA",format="Image",score=c.roas))
        
    db.add(Approval(organization_id=org_beta.id,type="budget_change",campaign_id=beta_cs[0].id,summary="Decrease TikTok budget",impact=-2000))
    db.add(AutomationEvent(organization_id=org_beta.id,action="Ad paused",campaign_name="Beta Brand Awareness",reason="ROAS fell below guardrail for 3 consecutive hours"))

    db.commit()
    print("Seed data applied for Org Alpha and Org Beta.")
    print(f"Org Alpha Invite Code: {org_alpha.invite_code}")
    print(f"Org Beta Invite Code: {org_beta.invite_code}")

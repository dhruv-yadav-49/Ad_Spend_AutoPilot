from .models import User,Campaign,Creative,Approval,AutomationEvent
from .security import hash_password
def seed(db):
    if db.query(User).first(): return
    db.add(User(name="Admin User",email="admin@adspend.local",password_hash=hash_password("Admin@123")))
    rows=[
      ("Summer Sale - Prospecting","Google Ads","High-intent shoppers",18000,45231,3642,245000,5.42,12.42),
      ("Retargeting - View Content","Meta Ads","Site visitors",14000,38762,4214,189000,4.88,9.20),
      ("Lookalike 1% - Purchasers","Meta Ads","Lookalike buyers",12000,32112,2831,135000,4.20,11.34),
      ("Brand Awareness - Video","TikTok Ads","Gen Z",8000,18231,1280,39000,2.14,14.24),
      ("LinkedIn - B2B Leads","LinkedIn Ads","Marketing leaders",7000,14287,682,54000,3.78,20.95)]
    cs=[]
    for r in rows:
        c=Campaign(name=r[0],channel=r[1],audience=r[2],daily_budget=r[3],spend=r[4],conversions=r[5],revenue=r[6],roas=r[7],cpa=r[8]);db.add(c);db.flush();cs.append(c)
    for c in cs: db.add(Creative(campaign_id=c.id,title=f"{c.name} Creative A",message="Lead with a measurable customer benefit and a direct call to action.",format="Video",score=c.roas))
    db.add(Approval(type="budget_change",campaign_id=cs[0].id,summary="Increase Google Ads budget by $15,000",impact=15000))
    db.add(AutomationEvent(action="Ad paused",campaign_name="Brand Awareness - Video",reason="ROAS fell below guardrail for 3 consecutive hours"))
    db.add(AutomationEvent(action="Creative brief generated",campaign_name="Summer Sale - Prospecting",reason="New test based on winning benefit-led creative"))
    db.commit()

import json
from collections import defaultdict
from .models import Campaign,Approval,AutomationEvent,Creative
from rocketride import RocketRideClient
from .config import settings

async def run_pipeline(filepath, payload):
    try:
        async with RocketRideClient(uri=settings.ROCKETRIDE_URI, auth=settings.ROCKETRIDE_APIKEY) as client:
            result = await client.use(filepath=filepath)
            token = result['token']
            try:
                out = await client.send(token, payload, mimetype='text/plain')
                return out
            finally:
                await client.terminate(token)
    except Exception as e:
        return f"Pipeline Error: {str(e)}"


def dashboard_payload(db):
    cs=db.query(Campaign).all()
    spend=round(sum(c.spend for c in cs),2); conv=sum(c.conversions for c in cs); rev=sum(c.revenue for c in cs)
    channels=defaultdict(float)
    for c in cs: channels[c.channel]+=c.spend
    return {"kpis":{"total_spend":spend,"roas":round(rev/spend,2) if spend else 0,"conversions":conv,"cpa":round(spend/conv,2) if conv else 0},
      "channel_spend":[{"channel":k,"spend":round(v,2)} for k,v in channels.items()],
      "campaigns":sorted([{"id":c.id,"name":c.name,"channel":c.channel,"status":c.status,"spend":c.spend,"roas":c.roas,"cpa":c.cpa,"conversions":c.conversions,"daily_budget":c.daily_budget} for c in cs],key=lambda x:x["roas"],reverse=True),
      "approvals":db.query(Approval).filter(Approval.status=="pending").count(),
      "recent_events":[{"action":e.action,"campaign":e.campaign_name,"reason":e.reason,"status":e.status} for e in db.query(AutomationEvent).order_by(AutomationEvent.created_at.desc()).limit(8)]}

def optimize_budget(db,campaign_id,new_budget,threshold=.10):
    c=db.get(Campaign,campaign_id)
    if not c:return None,"Campaign not found"
    old=c.daily_budget; change=abs(new_budget-old)/old if old else 1
    if change>threshold:
        a=Approval(type="budget_change",campaign_id=c.id,summary=f"Change {c.name} daily budget from ${old:,.0f} to ${new_budget:,.0f}",impact=new_budget-old)
        db.add(a);db.commit();return {"approval_required":True,"approval_id":a.id},None
    c.daily_budget=new_budget
    db.add(AutomationEvent(action="Budget adjusted",campaign_name=c.name,reason=f"Autopilot changed budget from ${old:.0f} to ${new_budget:.0f}"))
    db.commit();return {"approval_required":False,"new_budget":new_budget},None

async def creative_brief(db,campaign_id,objective):
    c=db.get(Campaign,campaign_id)
    if not c:return None
    top=db.query(Creative).filter(Creative.campaign_id==c.id).order_by(Creative.score.desc()).first()
    msg=top.message if top else "Benefit-led proof with a clear CTA"
    
    payload = f"Campaign: {c.name}\nObjective: {objective}\nAudience: {c.audience}\nTop Message: {msg}"
    rocket_output = await run_pipeline('../pipelines/creative_brief.pipe', payload)
    
    return {"campaign":c.name,"objective":objective,"audience":c.audience,"recommended_message":msg,
      "brief": rocket_output if rocket_output else f"Create a {objective.lower()} ad for {c.audience}. Lead with the strongest proven benefit.",
      "tests":["Benefit-led headline vs urgency-led headline","UGC video vs static","Broad vs high-intent audience"]}

async def safety_review(text):
    rocket_output = await run_pipeline('../pipelines/brand_safety.pipe', text)
    
    try:
        # Try parsing JSON if LLM returns the structured format
        data = json.loads(rocket_output)
        is_safe = data.get("status") == "SAFE"
        flags = data.get("risky_phrases", [])
        recommendation = f"[{data.get('recommended_action', '')}] {data.get('summary', '')}"
    except Exception:
        # Fallback for plain string or error
        risky=[x for x in ["guaranteed","cure","risk-free","hate","discrimination"] if x in text.lower()]
        is_safe = not risky
        flags = risky
        recommendation = rocket_output if rocket_output else ("Approved" if is_safe else "Send for human review")

    return {"safe": is_safe, "flags": flags, "recommendation": recommendation}

from pydantic import BaseModel,Field
from typing import Literal
class LoginRequest(BaseModel): email:str; password:str
class CampaignCreate(BaseModel):
    name:str; channel:str; audience:str="General"; daily_budget:float=Field(gt=0)
class BudgetAction(BaseModel):
    campaign_id:int; new_daily_budget:float=Field(gt=0)
class ApprovalDecision(BaseModel): decision:Literal["approved","rejected"]
class CreativeBriefRequest(BaseModel): campaign_id:int; objective:str="Increase conversions"
class SafetyRequest(BaseModel): text:str

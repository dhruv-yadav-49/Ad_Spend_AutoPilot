from pydantic import BaseModel, Field, EmailStr
from typing import Literal

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    organization_name: str | None = None
    invite_code: str | None = None

class LoginRequest(BaseModel): 
    email: str 
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    organization_id: int
    organization_name: str

class CampaignCreate(BaseModel):
    name:str; channel:str; audience:str="General"; daily_budget:float=Field(gt=0)
class BudgetAction(BaseModel):
    campaign_id:int; new_daily_budget:float=Field(gt=0)
class ApprovalDecision(BaseModel): decision:Literal["approved","rejected"]
class CreativeBriefRequest(BaseModel): campaign_id:int; objective:str="Increase conversions"
class SafetyRequest(BaseModel): text:str

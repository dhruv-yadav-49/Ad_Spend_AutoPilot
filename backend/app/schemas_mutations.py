from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional

class UpdateBudgetPayload(BaseModel):
    new_daily_budget: float = Field(..., description="The new daily budget in account currency")
    
    @field_validator('new_daily_budget')
    def budget_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("new_daily_budget must be greater than 0")
        return v

class PausePayload(BaseModel):
    pass # No payload needed

class ResumePayload(BaseModel):
    pass # No payload needed

class ProposeMutationRequest(BaseModel):
    platform: str = Field(..., description="google or meta")
    platform_account_id: str
    platform_campaign_id: str
    action: str = Field(..., description="update_budget, pause, resume")
    action_payload: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('action')
    def validate_action(cls, v):
        valid_actions = ["update_budget", "pause", "resume"]
        if v not in valid_actions:
            raise ValueError(f"action must be one of {valid_actions}")
        return v

    @field_validator('action_payload')
    def validate_payload(cls, v, info):
        action = info.data.get('action')
        if action == "update_budget":
            UpdateBudgetPayload(**v) # Validates strict schema
        elif action in ["pause", "resume"]:
            if len(v) > 0:
                raise ValueError(f"{action} does not accept a payload")
        return v

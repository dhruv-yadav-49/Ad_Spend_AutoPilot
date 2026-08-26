from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Any, Dict
import json

from ..db import get_db
from ..models import User, Approval
from ..auth import get_current_user, require_role
from ..schemas_mutations import ProposeMutationRequest
from ..services_execution import ExecutionService
from ..credentials import CredentialService
from ..providers import get_client

router = APIRouter(prefix="/platforms/mutations", tags=["mutations"])

@router.post("/propose")
def propose_mutation(
    req: ProposeMutationRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Depending on role, we might auto-approve (if manager and below threshold).
    # For Phase 4A, let's say Analyst always requires approval. 
    # Manager auto-approves if updating budget below threshold (e.g., $100) or pausing/resuming.
    
    # We serialize the action payload back to JSON string for storage
    payload_str = json.dumps(req.action_payload)
    
    # Capture expected previous state
    expected_previous_state_str = None
    try:
        access_token, _ = CredentialService.get_access_token_and_customers(db, current_user.organization_id, req.platform)
        client = get_client(req.platform, access_token)
        current_state = client.get_campaign(req.platform_account_id, req.platform_campaign_id)
        if current_state:
            expected_previous_state_str = json.dumps(current_state)
    except Exception as e:
        # We don't want to block proposal if platform is temporarily unreachable, 
        # but execution will fail if expected state isn't matched.
        pass
        
    status = "pending"
    # Auto-approval logic
    if current_user.role == "manager":
        if req.action in ["pause", "resume"]:
            status = "approved"
        elif req.action == "update_budget":
            # For Phase 4A testing, let's set threshold to $500
            if req.action_payload.get("new_daily_budget", 0) <= 500:
                status = "approved"
    
    approval = Approval(
        organization_id=current_user.organization_id,
        type="mutation",
        platform=req.platform,
        platform_account_id=req.platform_account_id,
        platform_campaign_id=req.platform_campaign_id,
        action=req.action,
        action_payload=payload_str,
        expected_previous_state=expected_previous_state_str,
        requester_id=current_user.id,
        status=status,
        summary=f"Proposed {req.action} on {req.platform} campaign {req.platform_campaign_id}"
    )
    
    db.add(approval)
    db.commit()
    db.refresh(approval)
    
    # If auto-approved, we can execute immediately, but the prompt says 
    # "Manager below threshold -> auto-approval" and execution path should follow.
    # To match testing requirements cleanly, we'll return the approval and let 
    # the client (or another endpoint) call execute. 
    # Wait, the instruction says "Manager below threshold -> auto-approval. Manager above threshold -> requires approval."
    # Then execution is separate.
    return {"message": "Mutation proposed", "approval_id": approval.id, "status": approval.status}

@router.post("/{approval_id}/approve")
def approve_mutation(
    approval_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_role("manager"))
):
    approval = db.get(Approval, approval_id)
    if not approval or approval.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Approval not found")
        
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval is not pending")
        
    if approval.requester_id == current_user.id:
        raise HTTPException(status_code=403, detail="Manager cannot approve their own mutation")
        
    approval.status = "approved"
    approval.approved_by_id = current_user.id
    db.commit()
    return {"message": "Mutation approved"}

@router.post("/{approval_id}/reject")
def reject_mutation(
    approval_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_role("manager"))
):
    approval = db.get(Approval, approval_id)
    if not approval or approval.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Approval not found")
        
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval is not pending")
        
    approval.status = "rejected"
    # Even if they requested it themselves, they can reject their own proposal if they changed their mind
    approval.approved_by_id = current_user.id
    db.commit()
    return {"message": "Mutation rejected"}

@router.post("/{approval_id}/execute")
def execute_mutation(
    approval_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Must be manager to trigger execution? Or can analyst trigger execution if it's approved?
    # "Analyst cannot execute an approved mutation directly."
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Only managers can execute mutations")
        
    # ExecutionService handles the rest of the safety checks
    audit = ExecutionService.execute_approval(db, approval_id, current_user)
    
    return {
        "message": "Execution attempted",
        "audit_id": audit.id,
        "status": audit.status
    }

@router.post("/{approval_id}/retry")
def retry_mutation(
    approval_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Only managers can retry mutations")
        
    approval = db.get(Approval, approval_id)
    if not approval or approval.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Approval not found")

    from ..models import ExecutionAudit
    existing_audits = db.scalars(select(ExecutionAudit).where(ExecutionAudit.approval_id == approval_id)).all()
    if not existing_audits:
        raise HTTPException(status_code=400, detail="Cannot retry an execution that hasn't been attempted yet")
        
    audit = ExecutionService.execute_approval(db, approval_id, current_user)
    
    return {
        "message": "Retry attempted",
        "audit_id": audit.id,
        "status": audit.status
    }

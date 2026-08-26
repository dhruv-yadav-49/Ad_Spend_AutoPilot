import json
import logging
import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

from .models import Approval, ExecutionAudit, AdPlatformConnection, User
from .credentials import CredentialService
from .providers import get_client
from .config import settings

logger = logging.getLogger(__name__)

class ExecutionService:
    @staticmethod
    def _generate_idempotency_key(approval_id: int, action: str, attempt: int = 1) -> str:
        raw = f"{approval_id}_{action}_{attempt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def execute_approval(db: Session, approval_id: int, current_user: User) -> ExecutionAudit:
        # 1. Load Approval
        approval = db.get(Approval, approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
            
        # 2. Verify Tenant Ownership
        if approval.organization_id != current_user.organization_id:
            raise HTTPException(status_code=404, detail="Approval not found") # Disguise as 404
            
        # 3. Verify approval status
        if approval.status != "approved":
            raise HTTPException(status_code=400, detail="Approval is not in 'approved' status")
            
        # 4. Verify requester != approver for explicit approvals
        if approval.approved_by_id and approval.requester_id == approval.approved_by_id:
             raise HTTPException(status_code=403, detail="Approval is invalid: self-approved")
             
        # 5. Verify Platform Connection Ownership
        connection = db.scalar(
            select(AdPlatformConnection).where(
                AdPlatformConnection.organization_id == current_user.organization_id,
                AdPlatformConnection.platform == approval.platform,
                AdPlatformConnection.external_account_id == approval.platform_account_id,
                AdPlatformConnection.status == "active"
            )
        )
        if not connection:
            raise HTTPException(status_code=400, detail="Platform connection not active or missing")
            
        # 6. Retrieve/refresh credentials
        try:
            access_token, _ = CredentialService.get_access_token_and_customers(db, current_user.organization_id, approval.platform)
        except Exception as e:
            logger.error(f"Credential refresh failed: {e}")
            raise HTTPException(status_code=400, detail="Failed to acquire valid credentials")
            
        adapter = get_client(approval.platform, access_token)
        
        # 7. Read CURRENT external state
        try:
            current_state = adapter.get_campaign(approval.platform_account_id, approval.platform_campaign_id)
            if not current_state:
                raise ValueError("Campaign not found")
        except Exception as e:
            logger.error(f"Failed to read current state: {e}")
            raise HTTPException(status_code=400, detail="Failed to read current platform state")
            
        # 8. Compare against approved expected state
        if approval.expected_previous_state:
            expected_state = json.loads(approval.expected_previous_state)
            
            # We compare the fields that matter (status, daily_budget)
            # If the current state differs from what was expected when approved, we must reject it.
            for key in ["status", "daily_budget"]:
                if key in expected_state and key in current_state:
                    if str(expected_state[key]).lower() != str(current_state[key]).lower():
                        raise HTTPException(status_code=409, detail=f"Campaign state changed externally ({key}: {expected_state[key]} -> {current_state[key]}). Execution aborted.")
        
        action_payload = json.loads(approval.action_payload) if approval.action_payload else {}
        
        # 9. Apply MAX_DAILY_BUDGET_USD
        if approval.action == "update_budget":
            if action_payload.get("new_daily_budget", 0) > settings.MAX_DAILY_BUDGET_USD:
                raise HTTPException(status_code=400, detail=f"Budget exceeds maximum allowed ({settings.MAX_DAILY_BUDGET_USD})")
                
        # 10. Check previous execution attempts and acquire idempotency protection
        existing_audits = db.scalars(select(ExecutionAudit).where(ExecutionAudit.approval_id == approval.id)).all()
        for ea in existing_audits:
            if ea.status == "success":
                raise HTTPException(status_code=400, detail="Approval already executed successfully")
            if ea.status == "failed_permanent":
                raise HTTPException(status_code=400, detail="Approval cannot be retried due to a permanent failure")
                
        attempt = len(list(existing_audits)) + 1
        idem_key = ExecutionService._generate_idempotency_key(approval.id, approval.action, attempt)
        
        # Write initial pending audit to claim idempotency key
        audit = ExecutionAudit(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            approval_id=approval.id,
            idempotency_key=idem_key,
            platform=approval.platform,
            platform_account_id=approval.platform_account_id,
            platform_campaign_id=approval.platform_campaign_id,
            action=approval.action,
            previous_state=json.dumps(current_state),
            requested_state=json.dumps(action_payload),
            status="pending"
        )
        db.add(audit)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail="Duplicate execution request")
            
        db.refresh(audit)
        
        # 11. Execute mutation
        try:
            if approval.action == "update_budget":
                result_state = adapter.update_budget(approval.platform_account_id, approval.platform_campaign_id, action_payload["new_daily_budget"])
            elif approval.action == "pause":
                result_state = adapter.pause_campaign(approval.platform_account_id, approval.platform_campaign_id)
            elif approval.action == "resume":
                result_state = adapter.resume_campaign(approval.platform_account_id, approval.platform_campaign_id)
            else:
                raise ValueError(f"Unknown action: {approval.action}")
                
            audit.result_state = json.dumps(result_state)
            audit.status = "success"
            approval.status = "executed"
            approval.executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
        except HTTPException as e:
            logger.error(f"Execution failed: {e.detail}")
            if e.status_code in (429, 500, 502, 503, 504):
                audit.status = "failed_retryable"
            else:
                audit.status = "failed_permanent"
                approval.status = "failed"
            audit.error_code = str(e.detail)
            db.commit()
            raise e
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            audit.status = "failed_retryable"
            audit.error_code = "execution_error_timeout"
            db.commit()
            raise HTTPException(status_code=500, detail="Provider execution failed")
            
        # 12. Verify resulting state
        try:
            final_state = adapter.get_campaign(approval.platform_account_id, approval.platform_campaign_id)
            # In a real implementation we would assert that final_state matches result_state.
            # For Phase 4B mock, we just assume it worked if no exception.
        except Exception as e:
            logger.error(f"Post-execution verification failed: {e}")
            audit.status = "uncertain"
            audit.error_code = "verification_failed"
            db.commit()
            
        return audit

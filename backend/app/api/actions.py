from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_owner
from typing import List, Dict, Optional
from app.services.state_store import state
from app.models.schemas import Action, ActionAuthorizeRequest, ActionCancelRequest
from app.services.command_engine import command_engine

router = APIRouter(prefix="/actions", tags=["Actions"])

@router.get("", response_model=Dict[str, List[Action]])
def get_actions(status: Optional[str] = Query(None)):
    actions = list(state.actions.values())
    if status:
        actions = [a for a in actions if a.status.value == status]
    actions.sort(key=lambda x: x.created_at, reverse=True)
    return {"actions": actions}

@router.get("/{action_id}", response_model=Action)
def get_action(action_id: str):
    if action_id not in state.actions:
        raise HTTPException(status_code=404, detail="Action not found")
    return state.actions[action_id]

@router.post("/{action_id}/authorize")
async def authorize_action(action_id: str, req: ActionAuthorizeRequest,
                           user: dict = Depends(require_owner)):
    """Owner role only. An operator signed in read-only gets 403 from the server, not just a
    hidden button — the approval gate has to hold even if the UI is bypassed."""
    result = await command_engine.authorize_action(
        action_id=action_id,
        authorized_by=req.authorized_by,
        comment=req.comment
    )
    if not result:
        raise HTTPException(status_code=404, detail="Action not found")
    return result

@router.post("/{action_id}/cancel")
async def cancel_action(action_id: str, req: ActionCancelRequest,
                        user: dict = Depends(require_owner)):
    result = await command_engine.cancel_action(
        action_id=action_id,
        cancelled_by=req.cancelled_by,
        reason=req.reason
    )
    if not result:
        raise HTTPException(status_code=404, detail="Action not found")
    return result

@router.get("/{action_id}/status")
def get_action_status(action_id: str):
    if action_id not in state.actions:
        raise HTTPException(status_code=404, detail="Action not found")
    act = state.actions[action_id]
    return {
        "id": act.id,
        "status": act.status,
        "execution_started": act.executed_at,
        "execution_completed": act.completed_at,
        "verification": act.verification
    }

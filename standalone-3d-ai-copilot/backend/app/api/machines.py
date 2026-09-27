from fastapi import APIRouter, HTTPException
from typing import List, Dict
from app.services.state_store import state
from app.models.schemas import Machine

router = APIRouter(prefix="/machines", tags=["Machines"])

@router.get("", response_model=Dict[str, List[Machine]])
def get_machines():
    return {"machines": list(state.machines.values())}

@router.get("/{machine_id}", response_model=Machine)
def get_machine(machine_id: str):
    if machine_id not in state.machines:
        raise HTTPException(status_code=404, detail="Machine not found")
    return state.machines[machine_id]

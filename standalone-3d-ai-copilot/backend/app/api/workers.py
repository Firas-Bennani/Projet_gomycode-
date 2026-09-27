from fastapi import APIRouter, HTTPException
from typing import List, Dict
from app.services.state_store import state
from app.models.schemas import Worker

router = APIRouter(prefix="/workers", tags=["Workers"])

@router.get("", response_model=Dict[str, List[Worker]])
def get_workers():
    return {"workers": list(state.workers.values())}

@router.get("/{worker_id}", response_model=Worker)
def get_worker(worker_id: str):
    if worker_id not in state.workers:
        raise HTTPException(status_code=404, detail="Worker not found")
    return state.workers[worker_id]

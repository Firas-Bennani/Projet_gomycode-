from fastapi import APIRouter
from typing import List, Dict
from app.services.state_store import state
from app.models.schemas import (
    InventoryItem, ClientItem, CollaborationItem, IndustrialEvent, Camera, RiskAssessment
)

router = APIRouter(tags=["Plant Operations"])

@router.get("/inventory", response_model=Dict[str, List[InventoryItem]])
def get_inventory():
    return {"inventory": list(state.inventory.values())}

@router.get("/clients", response_model=Dict[str, List[ClientItem]])
def get_clients():
    return {"clients": list(state.clients.values())}

@router.get("/collaborations", response_model=Dict[str, List[CollaborationItem]])
def get_collaborations():
    return {"collaborations": list(state.collaborations.values())}

@router.get("/events", response_model=Dict[str, List[IndustrialEvent]])
def get_events():
    return {"events": list(state.events.values())}

@router.get("/cameras", response_model=Dict[str, List[Camera]])
def get_cameras():
    return {"cameras": list(state.cameras.values())}

@router.get("/risks", response_model=Dict[str, List[RiskAssessment]])
def get_risks():
    return {"risks": list(state.risks.values())}

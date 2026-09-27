from fastapi import APIRouter
from typing import Dict, Any
from app.services.state_store import state
from app.models.schemas import DigitalTwinSnapshot

router = APIRouter(prefix="/digital-twin", tags=["Digital Twin"])

@router.get("/state", response_model=DigitalTwinSnapshot)
def get_digital_twin_state():
    return DigitalTwinSnapshot(
        zones=list(state.zones.values()),
        machines=list(state.machines.values()),
        workers=list(state.workers.values()),
        sensors=list(state.sensors.values()),
        cameras=list(state.cameras.values()),
        active_risks=[r for r in state.risks.values() if r.status == "ACTIVE"]
    )

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional
from datetime import datetime
from app.services.state_store import state
from app.models.schemas import Incident, IncidentUpdate
from app.services.event_bus import event_bus

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.get("", response_model=Dict[str, List[Incident]])
def get_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    zone: Optional[str] = Query(None)
):
    incidents = list(state.incidents.values())
    if status:
        incidents = [i for i in incidents if i.status == status]
    if severity:
        incidents = [i for i in incidents if i.severity.value == severity]
    if zone:
        incidents = [i for i in incidents if i.zone == zone]
    # Sort latest first
    incidents.sort(key=lambda x: x.timestamp, reverse=True)
    return {"incidents": incidents}

@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: str):
    if incident_id not in state.incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    return state.incidents[incident_id]

@router.patch("/{incident_id}", response_model=Incident)
async def update_incident(incident_id: str, update: IncidentUpdate):
    if incident_id not in state.incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    inc = state.incidents[incident_id]
    inc.status = update.status
    if update.status == "RESOLVED":
        inc.resolved_at = datetime.utcnow()
        if inc.zone in state.zones:
            state.zones[inc.zone].status = "NORMAL"
            state.zones[inc.zone].risk_level = None

    await event_bus.publish(
        event_type="INCIDENT_UPDATED",
        source="api:incidents",
        data=inc.model_dump(mode="json"),
        zone=inc.zone,
        severity="INFO"
    )
    return inc

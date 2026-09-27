from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.state_store import state
from app.models.schemas import Sensor

router = APIRouter(prefix="/sensors", tags=["Sensors"])

@router.get("", response_model=Dict[str, List[Sensor]])
def get_sensors():
    return {"sensors": list(state.sensors.values())}

@router.get("/{sensor_id}", response_model=Sensor)
def get_sensor(sensor_id: str):
    if sensor_id not in state.sensors:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return state.sensors[sensor_id]

@router.get("/{sensor_id}/readings")
def get_sensor_readings(sensor_id: str, range: str = "1h"):
    if sensor_id not in state.sensor_history:
        return {"sensor_id": sensor_id, "readings": []}
    return {
        "sensor_id": sensor_id,
        "readings": state.sensor_history[sensor_id]
    }

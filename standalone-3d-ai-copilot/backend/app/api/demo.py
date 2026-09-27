from fastapi import APIRouter
from app.models.schemas import DemoScenarioRequest, DemoScenarioResponse
from iot.simulator import simulator

router = APIRouter(prefix="/demo", tags=["Demo Controls"])

@router.post("/scenario", response_model=DemoScenarioResponse)
def trigger_scenario(req: DemoScenarioRequest):
    simulator.set_scenario(req.scenario)
    duration_map = {
        "normal": 0,
        "machine_overheating": 25,
        "cybersecurity": 15,
        "fire": 20
    }
    return DemoScenarioResponse(
        status="STARTED",
        scenario=req.scenario,
        message=f"Scenario '{req.scenario}' initiated in simulated industrial plant.",
        estimated_duration_seconds=duration_map.get(req.scenario, 20)
    )

@router.post("/reset")
async def reset_demo():
    await simulator.reset()
    return {"status": "SUCCESS", "message": "Factory state reset to normal."}

@router.get("/status")
def get_demo_status():
    return {
        "current_scenario": simulator.scenario,
        "scenario_step": simulator.scenario_step,
        "simulator_running": simulator.running
    }

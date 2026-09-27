from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.state_store import state
from app.models.schemas import AgentStatus, AgentLogEntry, RAGQueryRequest, RAGQueryResponse
from ai.rag.rag_engine import rag_engine

router = APIRouter(prefix="/ai", tags=["AI Systems"])

@router.get("/agents")
def get_agents():
    return {"agents": [
        agent.model_dump(mode="json") if hasattr(agent, "model_dump") else {
            "id": agent.agent_id,
            "name": agent.name,
            "status": agent.status,
            "current_task": agent.current_task,
            "latest_observation": agent.latest_observation,
            "latest_decision": agent.latest_decision,
            "last_update": agent.last_update.isoformat()
        }
        for agent in state.agents.values()
    ]}

@router.get("/agents/{agent_id}/log")
def get_agent_log(agent_id: str):
    entries = [e for e in state.agent_logs if e["agent_id"] == agent_id]
    return {"agent_id": agent_id, "entries": entries}

@router.get("/logs")
def get_all_agent_logs():
    return {"logs": state.agent_logs}

@router.post("/rag/query", response_model=RAGQueryResponse)
def query_rag(req: RAGQueryRequest):
    result = rag_engine.query(req.query, req.context)
    return result

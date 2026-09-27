from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.status = "ACTIVE"
        self.current_task = "Initializing"
        self.latest_observation = "No data processed yet"
        self.latest_decision = "Monitoring"
        self.last_update = datetime.utcnow()

    @abstractmethod
    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processes an incoming event and returns an observation or alert if an anomaly is detected."""
        pass

    def update_status(self, task: str, observation: str, decision: str, status: str = "ACTIVE"):
        self.current_task = task
        self.latest_observation = observation
        self.latest_decision = decision
        self.status = status
        self.last_update = datetime.utcnow()

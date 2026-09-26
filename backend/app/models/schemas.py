from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ActionStatus(str, Enum):
    PENDING = "PENDING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# ----------------- SENSORS -----------------
class Sensor(BaseModel):
    id: str
    type: str  # temperature, pressure, humidity, smoke, water_level, vibration, energy
    zone: str
    unit: str
    current_value: float
    status: Severity
    last_updated: datetime
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None

class SensorReading(BaseModel):
    timestamp: datetime
    value: float

# ----------------- MACHINES -----------------
class MachineParameterDetail(BaseModel):
    value: float
    unit: str
    threshold: Optional[float] = None
    status: Severity

class Machine(BaseModel):
    id: str
    name: str
    zone: str
    status: Severity
    parameters: Dict[str, MachineParameterDetail]
    uptime_hours: int = 1200
    last_maintenance: str = "2026-09-01T08:00:00Z"
    position: Optional[Dict[str, float]] = None

# ----------------- WORKERS -----------------
class WorkerPPE(BaseModel):
    helmet: bool
    vest: bool
    gloves: bool
    safety_shoes: bool

class WorkerAlert(BaseModel):
    type: str
    detail: str
    timestamp: datetime

class Worker(BaseModel):
    id: str
    name: str
    role: str
    zone: str
    status: str  # ON_SITE, OFF_SITE, AT_RISK
    entry_time: str
    working_hours_today: float
    ppe: WorkerPPE
    alerts: List[WorkerAlert] = []
    position: Optional[Dict[str, float]] = None

# ----------------- CAMERAS -----------------
class Camera(BaseModel):
    id: str
    name: str
    zone: str
    status: str  # ONLINE, OFFLINE
    feed_url: Optional[str] = None
    detected_objects: List[str] = []
    last_event: Optional[str] = None

# ----------------- INCIDENTS -----------------
class EvidenceItem(BaseModel):
    source: str
    detail: str
    timestamp: Optional[datetime] = None

class RecommendedAction(BaseModel):
    action: str
    action_type: str
    target: str
    risk_level: RiskLevel
    requires_confirmation: bool
    reason: str

class Incident(BaseModel):
    id: str
    type: str
    severity: Severity
    confidence: float
    zone: str
    timestamp: datetime
    affected_assets: List[str]
    affected_workers: List[str]
    evidence: List[EvidenceItem]
    ai_reasoning: str
    recommended_actions: List[RecommendedAction]
    status: str  # ACTIVE, RESOLVING, RESOLVED, DISMISSED
    resolved_at: Optional[datetime] = None

class IncidentUpdate(BaseModel):
    status: str

# ----------------- ACTIONS (COMMAND CENTER) -----------------
class Action(BaseModel):
    id: str
    incident_id: Optional[str] = None
    action_type: str
    target: str
    reason: str
    risk_level: RiskLevel
    status: ActionStatus
    created_at: datetime
    created_by: str = "recommendation_agent"
    authorized_by: Optional[str] = None
    authorized_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verification: Optional[Dict[str, Any]] = None

class ActionAuthorizeRequest(BaseModel):
    authorized_by: str = "owner_01"
    comment: Optional[str] = None

class ActionCancelRequest(BaseModel):
    cancelled_by: str = "owner_01"
    reason: Optional[str] = None

# ----------------- RISKS -----------------
class RiskAssessment(BaseModel):
    id: str
    type: str
    zone: str
    severity: Severity
    probability: float
    impact: str
    contributing_factors: List[str]
    assessed_at: datetime
    status: str = "ACTIVE"

# ----------------- AI MULTI-AGENT -----------------
class AgentStatus(BaseModel):
    id: str
    name: str
    status: str  # ACTIVE, IDLE, PROCESSING, WARNING
    current_task: str
    latest_observation: str
    latest_decision: str
    last_update: datetime

class AgentLogEntry(BaseModel):
    timestamp: datetime
    agent_id: str
    input_from: List[str]
    reasoning: str
    decision: str
    actions_proposed: Optional[List[str]] = None

class RAGQueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None

class RAGSource(BaseModel):
    document: str
    section: str
    relevance: float

class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[RAGSource]

# ----------------- DIGITAL TWIN -----------------
class Zone3D(BaseModel):
    id: str
    name: str
    status: str  # NORMAL, ALERT, RESTRICTED
    risk_level: Optional[Severity] = None
    active_incidents: List[str] = []

class DigitalTwinSnapshot(BaseModel):
    zones: List[Zone3D]
    machines: List[Machine]
    workers: List[Worker]
    sensors: List[Sensor]
    cameras: List[Camera]
    active_risks: List[RiskAssessment]

# ----------------- DEMO SCENARIOS -----------------
class DemoScenarioRequest(BaseModel):
    scenario: str  # "normal", "machine_overheating", "cybersecurity", "fire"
    speed: float = 1.0

class DemoScenarioResponse(BaseModel):
    status: str
    scenario: str
    message: str
    estimated_duration_seconds: int

# ----------------- NAVIGATION ITEMS -----------------
class InventoryItem(BaseModel):
    id: str
    name: str
    category: str
    quantity: float
    unit: str
    low_stock_threshold: float
    status: str  # NORMAL, LOW, CRITICAL
    consumption_rate: str

class ClientItem(BaseModel):
    id: str
    name: str
    industry: str
    contact_email: str
    status: str
    orders_count: int
    ai_recommendations: Optional[str] = None

class CollaborationItem(BaseModel):
    id: str
    partner_name: str
    type: str  # SUPPLIER, RESEARCH, LOGISTICS
    status: str
    contact: str
    notes: str

class IndustrialEvent(BaseModel):
    id: str
    title: str
    type: str  # MAINTENANCE, AUDIT, TRAINING, INSPECTION
    scheduled_at: str
    zone_id: Optional[str] = None
    machine_id: Optional[str] = None
    status: str  # SCHEDULED, IN_PROGRESS, COMPLETED

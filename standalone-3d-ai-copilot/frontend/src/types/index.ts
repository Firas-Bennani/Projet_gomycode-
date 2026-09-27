export type Severity = 'INFO' | 'WARNING' | 'HIGH' | 'CRITICAL';
export type ActionStatus = 'PENDING' | 'AWAITING_APPROVAL' | 'AUTHORIZED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface Sensor {
  id: string;
  type: string;
  zone: string;
  unit: string;
  current_value: number;
  status: Severity;
  last_updated: string;
  threshold_warning?: number;
  threshold_critical?: number;
}

export interface SensorReading {
  timestamp: string;
  value: number;
}

export interface MachineParameterDetail {
  value: number;
  unit: string;
  threshold?: number;
  status: Severity;
}

export interface Machine {
  id: string;
  name: string;
  zone: string;
  status: Severity;
  parameters: Record<string, MachineParameterDetail>;
  uptime_hours: number;
  last_maintenance: string;
  position?: { x: number; y: number; z: number };
}

export interface WorkerPPE {
  helmet: boolean;
  vest: boolean;
  gloves: boolean;
  safety_shoes: boolean;
}

export interface WorkerAlert {
  type: string;
  detail: string;
  timestamp: string;
}

export interface Worker {
  id: string;
  name: string;
  role: string;
  zone: string;
  status: string;
  entry_time: string;
  working_hours_today: number;
  ppe: WorkerPPE;
  alerts: WorkerAlert[];
  position?: { x: number; y: number; z: number };
}

export interface Camera {
  id: string;
  name: string;
  zone: string;
  status: string;
  feed_url?: string;
  detected_objects: string[];
  last_event?: string;
}

export interface EvidenceItem {
  source: string;
  detail: string;
  timestamp?: string;
}

export interface RecommendedAction {
  action: string;
  action_type: string;
  target: string;
  risk_level: RiskLevel;
  requires_confirmation: boolean;
  reason: string;
}

export interface Incident {
  id: string;
  type: string;
  severity: Severity;
  confidence: number;
  zone: string;
  timestamp: string;
  affected_assets: string[];
  affected_workers: string[];
  evidence: EvidenceItem[];
  ai_reasoning: string;
  recommended_actions: RecommendedAction[];
  status: string;
  resolved_at?: string;
}

export interface Action {
  id: string;
  incident_id?: string;
  action_type: string;
  target: string;
  reason: string;
  risk_level: RiskLevel;
  status: ActionStatus;
  created_at: string;
  created_by: string;
  authorized_by?: string;
  authorized_at?: string;
  executed_at?: string;
  completed_at?: string;
  verification?: {
    verified: boolean;
    checks: Array<{ check: string; passed: boolean }>;
    timestamp: string;
  };
}

export interface RiskAssessment {
  id: string;
  type: string;
  zone: string;
  severity: Severity;
  probability: number;
  impact: string;
  contributing_factors: string[];
  assessed_at: string;
  status: string;
}

export interface AgentStatus {
  id: string;
  name: string;
  status: string;
  current_task: string;
  latest_observation: string;
  latest_decision: string;
  last_update: string;
}

export interface AgentLogEntry {
  timestamp: string;
  agent_id: string;
  input_from: string[];
  reasoning: string;
  decision: string;
  actions_proposed?: string[];
}

export interface Zone3D {
  id: string;
  name: string;
  status: string;
  risk_level?: Severity;
  active_incidents: string[];
}

export interface DigitalTwinSnapshot {
  zones: Zone3D[];
  machines: Machine[];
  workers: Worker[];
  sensors: Sensor[];
  cameras: Camera[];
  active_risks: RiskAssessment[];
}

export interface InventoryItem {
  id: string;
  name: string;
  category: string;
  quantity: number;
  unit: string;
  low_stock_threshold: number;
  status: string;
  consumption_rate: string;
}

export interface ClientItem {
  id: string;
  name: string;
  industry: string;
  contact_email: string;
  status: string;
  orders_count: number;
  ai_recommendations?: string;
}

export interface CollaborationItem {
  id: string;
  partner_name: string;
  type: string;
  status: string;
  contact: string;
  notes: string;
}

export interface IndustrialEvent {
  id: string;
  title: string;
  type: string;
  scheduled_at: string;
  zone_id?: string;
  machine_id?: string;
  status: string;
}

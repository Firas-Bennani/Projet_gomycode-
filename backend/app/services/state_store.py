from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid
from app.models.schemas import (
    Sensor, Machine, MachineParameterDetail, Worker, WorkerPPE, Camera,
    Incident, Action, RiskAssessment, AgentStatus, AgentLogEntry,
    Zone3D, Severity, ActionStatus, RiskLevel, InventoryItem,
    ClientItem, CollaborationItem, IndustrialEvent
)

class StateStore:
    def __init__(self):
        self.initialize_state()

    def initialize_state(self):
        # 4 Factory Zones
        self.zones: Dict[str, Zone3D] = {
            "ZONE_A": Zone3D(id="ZONE_A", name="Zone A — CNC Machining & Fabrication", status="NORMAL", risk_level=None, active_incidents=[]),
            "ZONE_B": Zone3D(id="ZONE_B", name="Zone B — Heavy Milling & Heat Treatment", status="NORMAL", risk_level=None, active_incidents=[]),
            "ZONE_C": Zone3D(id="ZONE_C", name="Zone C — Robotic Assembly & Quality Control", status="NORMAL", risk_level=None, active_incidents=[]),
            "ZONE_D": Zone3D(id="ZONE_D", name="Zone D — Logistics, Packaging & Storage", status="NORMAL", risk_level=None, active_incidents=[]),
        }

        # Machines
        self.machines: Dict[str, Machine] = {
            "M-01": Machine(
                id="M-01", name="High-Precision CNC 01", zone="ZONE_A", status=Severity.INFO,
                parameters={
                    "temperature": MachineParameterDetail(value=42.1, unit="°C", threshold=75.0, status=Severity.INFO),
                    "pressure": MachineParameterDetail(value=5.2, unit="bar", threshold=7.5, status=Severity.INFO),
                    "rpm": MachineParameterDetail(value=1800, unit="RPM", threshold=2200, status=Severity.INFO),
                    "vibration": MachineParameterDetail(value=1.4, unit="mm/s", threshold=4.5, status=Severity.INFO),
                    "energy": MachineParameterDetail(value=38.4, unit="kW", threshold=60.0, status=Severity.INFO),
                    "production_rate": MachineParameterDetail(value=94.0, unit="%", status=Severity.INFO),
                },
                position={"x": -10.0, "y": 0.0, "z": -6.0}
            ),
            "M-02": Machine(
                id="M-02", name="Hydraulic Press 02", zone="ZONE_A", status=Severity.INFO,
                parameters={
                    "temperature": MachineParameterDetail(value=38.5, unit="°C", threshold=70.0, status=Severity.INFO),
                    "pressure": MachineParameterDetail(value=6.1, unit="bar", threshold=8.0, status=Severity.INFO),
                    "rpm": MachineParameterDetail(value=950, unit="RPM", threshold=1200, status=Severity.INFO),
                    "vibration": MachineParameterDetail(value=2.1, unit="mm/s", threshold=5.0, status=Severity.INFO),
                    "energy": MachineParameterDetail(value=52.0, unit="kW", threshold=80.0, status=Severity.INFO),
                    "production_rate": MachineParameterDetail(value=91.0, unit="%", status=Severity.INFO),
                },
                position={"x": -10.0, "y": 0.0, "z": 6.0}
            ),
            "M-04": Machine(
                id="M-04", name="Heavy Industrial Milling M-04", zone="ZONE_B", status=Severity.INFO,
                parameters={
                    "temperature": MachineParameterDetail(value=45.0, unit="°C", threshold=80.0, status=Severity.INFO),
                    "pressure": MachineParameterDetail(value=5.4, unit="bar", threshold=8.0, status=Severity.INFO),
                    "rpm": MachineParameterDetail(value=1420, unit="RPM", threshold=1600, status=Severity.INFO),
                    "vibration": MachineParameterDetail(value=2.8, unit="mm/s", threshold=5.0, status=Severity.INFO),
                    "energy": MachineParameterDetail(value=64.2, unit="kW", threshold=90.0, status=Severity.INFO),
                    "production_rate": MachineParameterDetail(value=88.0, unit="%", status=Severity.INFO),
                },
                position={"x": 8.0, "y": 0.0, "z": -6.0}
            ),
            "M-05": Machine(
                id="M-05", name="Automated Induction Furnace M-05", zone="ZONE_B", status=Severity.INFO,
                parameters={
                    "temperature": MachineParameterDetail(value=58.0, unit="°C", threshold=110.0, status=Severity.INFO),
                    "pressure": MachineParameterDetail(value=4.8, unit="bar", threshold=7.0, status=Severity.INFO),
                    "rpm": MachineParameterDetail(value=800, unit="RPM", threshold=1000, status=Severity.INFO),
                    "vibration": MachineParameterDetail(value=1.9, unit="mm/s", threshold=4.0, status=Severity.INFO),
                    "energy": MachineParameterDetail(value=112.5, unit="kW", threshold=150.0, status=Severity.INFO),
                    "production_rate": MachineParameterDetail(value=96.0, unit="%", status=Severity.INFO),
                },
                position={"x": 8.0, "y": 0.0, "z": 6.0}
            ),
            "M-06": Machine(
                id="M-06", name="6-Axis Robotic Cell C-01", zone="ZONE_C", status=Severity.INFO,
                parameters={
                    "temperature": MachineParameterDetail(value=31.2, unit="°C", threshold=55.0, status=Severity.INFO),
                    "pressure": MachineParameterDetail(value=4.2, unit="bar", threshold=6.5, status=Severity.INFO),
                    "rpm": MachineParameterDetail(value=2100, unit="RPM", threshold=2400, status=Severity.INFO),
                    "vibration": MachineParameterDetail(value=0.8, unit="mm/s", threshold=3.0, status=Severity.INFO),
                    "energy": MachineParameterDetail(value=28.0, unit="kW", threshold=45.0, status=Severity.INFO),
                    "production_rate": MachineParameterDetail(value=98.5, unit="%", status=Severity.INFO),
                },
                position={"x": 20.0, "y": 0.0, "z": 0.0}
            )
        }

        # Sensors
        now = datetime.utcnow()
        self.sensors: Dict[str, Sensor] = {
            "TEMP-A-01": Sensor(id="TEMP-A-01", type="temperature", zone="ZONE_A", unit="°C", current_value=24.5, status=Severity.INFO, last_updated=now, threshold_warning=35.0, threshold_critical=50.0),
            "TEMP-B-01": Sensor(id="TEMP-B-01", type="temperature", zone="ZONE_B", unit="°C", current_value=26.2, status=Severity.INFO, last_updated=now, threshold_warning=35.0, threshold_critical=50.0),
            "TEMP-C-01": Sensor(id="TEMP-C-01", type="temperature", zone="ZONE_C", unit="°C", current_value=23.1, status=Severity.INFO, last_updated=now, threshold_warning=35.0, threshold_critical=50.0),
            "TEMP-D-01": Sensor(id="TEMP-D-01", type="temperature", zone="ZONE_D", unit="°C", current_value=22.0, status=Severity.INFO, last_updated=now, threshold_warning=32.0, threshold_critical=45.0),
            
            "PRES-B-01": Sensor(id="PRES-B-01", type="pressure", zone="ZONE_B", unit="bar", current_value=5.4, status=Severity.INFO, last_updated=now, threshold_warning=7.0, threshold_critical=8.0),
            "SMOKE-B-01": Sensor(id="SMOKE-B-01", type="smoke", zone="ZONE_B", unit="ppm", current_value=8.0, status=Severity.INFO, last_updated=now, threshold_warning=25.0, threshold_critical=50.0),
            "WATER-B-01": Sensor(id="WATER-B-01", type="water_level", zone="ZONE_B", unit="cm", current_value=0.0, status=Severity.INFO, last_updated=now, threshold_warning=5.0, threshold_critical=15.0),
            "VIB-B-01": Sensor(id="VIB-B-01", type="vibration", zone="ZONE_B", unit="mm/s", current_value=2.8, status=Severity.INFO, last_updated=now, threshold_warning=5.0, threshold_critical=7.5),
            "HUM-B-01": Sensor(id="HUM-B-01", type="humidity", zone="ZONE_B", unit="%", current_value=48.0, status=Severity.INFO, last_updated=now, threshold_warning=70.0, threshold_critical=85.0),
            "ENG-TOTAL": Sensor(id="ENG-TOTAL", type="energy", zone="ZONE_B", unit="kW", current_value=423.0, status=Severity.INFO, last_updated=now, threshold_warning=600.0, threshold_critical=750.0),
        }

        # Sensor Readings History (for charts)
        self.sensor_history: Dict[str, List[Dict[str, Any]]] = {
            s_id: [
                {"timestamp": (now - timedelta(minutes=i*2)).isoformat(), "value": self.sensors[s_id].current_value + (0.1 * (i % 3 - 1))}
                for i in range(20, -1, -1)
            ]
            for s_id in self.sensors
        }

        # Workers
        self.workers: Dict[str, Worker] = {
            "W23": Worker(id="W23", name="Ahmed Benali", role="Senior CNC Technician", zone="ZONE_B", status="ON_SITE", entry_time="07:45", working_hours_today=6.8, ppe=WorkerPPE(helmet=True, vest=True, gloves=True, safety_shoes=True), position={"x": 6.5, "y": 0, "z": -4.0}),
            "W41": Worker(id="W41", name="Sarah Mansouri", role="Maintenance Specialist", zone="ZONE_B", status="ON_SITE", entry_time="08:00", working_hours_today=6.5, ppe=WorkerPPE(helmet=True, vest=True, gloves=True, safety_shoes=True), position={"x": 9.5, "y": 0, "z": -5.5}),
            "W52": Worker(id="W52", name="Karim Tazi", role="Safety Inspector", zone="ZONE_B", status="ON_SITE", entry_time="08:15", working_hours_today=6.2, ppe=WorkerPPE(helmet=True, vest=True, gloves=True, safety_shoes=True), position={"x": 10.0, "y": 0, "z": 4.0}),
            "W12": Worker(id="W12", name="Elena Rostova", role="Robotics Lead", zone="ZONE_C", status="ON_SITE", entry_time="08:30", working_hours_today=6.0, ppe=WorkerPPE(helmet=True, vest=True, gloves=True, safety_shoes=True), position={"x": 18.0, "y": 0, "z": 0.0}),
            "W09": Worker(id="W09", name="Youssef Kabbaj", role="Inventory Coordinator", zone="ZONE_D", status="ON_SITE", entry_time="07:30", working_hours_today=7.0, ppe=WorkerPPE(helmet=True, vest=True, gloves=False, safety_shoes=True), position={"x": -18.0, "y": 0, "z": 0.0}),
        }

        # Cameras
        self.cameras: Dict[str, Camera] = {
            "CAM-A-01": Camera(id="CAM-A-01", name="CCTV North Fabrication", zone="ZONE_A", status="ONLINE", detected_objects=["Machine M-01", "Machine M-02", "Worker W05"], last_event="Normal operation"),
            "CAM-B-01": Camera(id="CAM-B-01", name="CCTV Heavy Thermal Cell", zone="ZONE_B", status="ONLINE", detected_objects=["Machine M-04", "Worker W23", "Worker W41"], last_event="Monitoring thermal zone"),
            "CAM-B-02": Camera(id="CAM-B-02", name="CCTV East Furnace Area", zone="ZONE_B", status="ONLINE", detected_objects=["Machine M-05", "Worker W52"], last_event="Routine sweep"),
            "CAM-C-01": Camera(id="CAM-C-01", name="CCTV Robotic Assembly 360", zone="ZONE_C", status="ONLINE", detected_objects=["Robot Cell C-01", "Worker W12"], last_event="Automated assembly in progress"),
        }

        # Incidents
        self.incidents: Dict[str, Incident] = {}

        # Actions
        self.actions: Dict[str, Action] = {}

        # Risks
        self.risks: Dict[str, RiskAssessment] = {}

        # Agent Statuses
        self.agents: Dict[str, AgentStatus] = {
            "temperature_agent": AgentStatus(
                id="temperature_agent",
                name="Temperature & Environmental Agent",
                status="ACTIVE",
                current_task="Continuous multi-point atmospheric and surface thermal monitoring",
                latest_observation="All 4 zones within standard thermal tolerance (22.0°C - 26.2°C)",
                latest_decision="STATUS NORMAL: No environmental anomaly detected",
                last_update=now
            ),
            "machine_agent": AgentStatus(
                id="machine_agent",
                name="Machine KPI & Diagnostics Agent",
                status="ACTIVE",
                current_task="Real-time multi-variate machine telemetry analysis (Pressure, RPM, Vibration)",
                latest_observation="Machine M-04 pressure stable at 5.4 bar (threshold: 8.0 bar)",
                latest_decision="STATUS NORMAL: Mechanical KPI baseline verified",
                last_update=now
            ),
            "worker_agent": AgentStatus(
                id="worker_agent",
                name="Worker Safety & Productivity Agent",
                status="ACTIVE",
                current_task="Tracking 5 active operators, PPE verification, restricted area surveillance",
                latest_observation="Zone B: 3 workers detected with certified safety equipment",
                latest_decision="STATUS NORMAL: Operator safety criteria compliant",
                last_update=now
            ),
            "cyber_agent": AgentStatus(
                id="cyber_agent",
                name="Cybersecurity Industrial Defense Agent",
                status="ACTIVE",
                current_task="Scrutinizing industrial OT protocol frames (Modbus/TCP, MQTT, S7Comm)",
                latest_observation="OT firewall healthy. Zero unauthorized connection requests in last 60m",
                latest_decision="STATUS NORMAL: Industrial fieldbus network secure",
                last_update=now
            ),
            "recommendation_agent": AgentStatus(
                id="recommendation_agent",
                name="Recommendation & Strategic Intelligence Agent",
                status="ACTIVE",
                current_task="Correlating multi-agent cross-domain telemetry & RAG knowledge retrieval",
                latest_observation="Cross-domain indicators synthesized across all 4 field agents",
                latest_decision="STATUS OPTIMAL: Plant throughput 94.2%, all safety protocols green",
                last_update=now
            ),
        }

        self.agent_logs: List[AgentLogEntry] = []

        # Inventory Items
        self.inventory: Dict[str, InventoryItem] = {
            "INV-01": InventoryItem(id="INV-01", name="Titanium Alloy Rods Ti-6Al-4V", category="Raw Material", quantity=450.0, unit="kg", low_stock_threshold=150.0, status="NORMAL", consumption_rate="28 kg/day"),
            "INV-02": InventoryItem(id="INV-02", name="Synthetic Industrial Coolant Ultra-50", category="Consumable", quantity=180.0, unit="Liters", low_stock_threshold=200.0, status="LOW", consumption_rate="35 L/week"),
            "INV-03": InventoryItem(id="INV-03", name="Diamond-Coated CNC End Mills 12mm", category="Tooling", quantity=24.0, unit="Units", low_stock_threshold=10.0, status="NORMAL", consumption_rate="4 units/day"),
            "INV-04": InventoryItem(id="INV-04", name="Finished Turbine Blades Batch #88", category="Finished Goods", quantity=86.0, unit="Units", low_stock_threshold=20.0, status="NORMAL", consumption_rate="Deliveries on schedule"),
        }

        # Clients
        self.clients: Dict[str, ClientItem] = {
            "CLI-01": ClientItem(id="CLI-01", name="AeroTech Defense Systems", industry="Aerospace & Defense", contact_email="procurement@aerotech-defense.com", status="ACTIVE", orders_count=14, ai_recommendations="Increase Batch #88 production output by 12% to meet Q4 aerospace delivery milestones"),
            "CLI-02": ClientItem(id="CLI-02", name="EuroRail HighSpeed Components", industry="Railway Transportation", contact_email="orders@eurorail-mfg.eu", status="ACTIVE", orders_count=8, ai_recommendations="Schedule hydraulic press calibration before high-torque axle production"),
            "CLI-03": ClientItem(id="CLI-03", name="Nordic Renewables Turbines", industry="Wind Energy", contact_email="b2b@nordicturbines.se", status="PROSPECT", orders_count=2, ai_recommendations="Present Machine M-04 precision tolerance certification to close annual turbine supply agreement"),
        }

        # Collaborations
        self.collaborations: Dict[str, CollaborationItem] = {
            "COL-01": CollaborationItem(id="COL-01", partner_name="Castrol Industrial Fluids", type="SUPPLIER", status="ACTIVE", contact="support.emea@castrol-industrial.com", notes="Automated restocking SLA: 48h emergency delivery for CNC coolant Ultra-50"),
            "COL-02": CollaborationItem(id="COL-02", partner_name="Siemens Industrial Automation Lab", type="RESEARCH", status="ACTIVE", contact="iot-research@siemens.com", notes="Pilot digital twin validation with Sinumerik ONE edge controllers"),
            "COL-03": CollaborationItem(id="COL-03", partner_name="Schneider Electric Power Grid", type="ENERGY_PARTNER", status="ACTIVE", contact="grid.response@schneider-electric.com", notes="Peak shaving protocol active: automatic load reduction above 650 kW total demand"),
        }

        # Industrial Events / Maintenance
        self.events: Dict[str, IndustrialEvent] = {
            "EVT-01": IndustrialEvent(id="EVT-01", title="Quarterly Precision Spindle Alignment", type="MAINTENANCE", scheduled_at="2026-09-28 06:00", zone_id="ZONE_B", machine_id="M-04", status="SCHEDULED"),
            "EVT-02": IndustrialEvent(id="EVT-02", title="ISO 45001 Industrial Safety Audit", type="AUDIT", scheduled_at="2026-10-02 09:30", zone_id="ZONE_B", machine_id=None, status="SCHEDULED"),
            "EVT-03": IndustrialEvent(id="EVT-03", title="Robotic Cell Lubrication & Gripper Inspection", type="MAINTENANCE", scheduled_at="2026-10-05 14:00", zone_id="ZONE_C", machine_id="M-06", status="SCHEDULED"),
        }

        self._load_seed_extensions()

    # ------------------------------------------------------------------------------------
    # Seed data (Engineer 1, item 3): ADDITIVE only.
    #
    # The demo scenarios reference W09/W12/W23/W41/W52, M-01..M-06 and the ZONE_B sensors by id,
    # so those stay defined above and are never touched here. This appends extra workers and a
    # real inventory so the Workers and Inventory pages are not nearly empty. Wrapped in
    # try/except: if a seed file is missing or malformed the platform runs on the hardcoded state
    # exactly as before.
    # ------------------------------------------------------------------------------------
    def _load_seed_extensions(self):
        import json as _json
        import pathlib as _pathlib
        seed_dir = _pathlib.Path(__file__).resolve().parents[1] / "data" / "seed"

        try:
            payload = _json.loads((seed_dir / "workers.json").read_text(encoding="utf-8"))
            for row in payload.get("items", []):
                if row["id"] in self.workers:
                    continue                      # never overwrite a scenario worker
                self.workers[row["id"]] = Worker(
                    id=row["id"], name=row["name"], role=row["role"], zone=row["zone"],
                    status=row.get("status", "ON_SITE"), entry_time=row.get("entry_time", "08:00"),
                    working_hours_today=float(row.get("working_hours_today", 0.0)),
                    ppe=WorkerPPE(**row["ppe"]), alerts=[],
                    position={"x": 0.0, "y": 0.0, "z": 0.0},
                )
            self.worker_details = {row["id"]: row for row in payload.get("items", [])}
        except Exception as exc:
            self.worker_details = {}
            print(f"[state_store] seed workers not loaded ({exc}); using the built-in five.")

        try:
            payload = _json.loads((seed_dir / "inventory.json").read_text(encoding="utf-8"))
            for row in payload.get("items", []):
                self.inventory[row["id"]] = InventoryItem(
                    id=row["id"], name=row["name"], category=row["category"],
                    quantity=float(row["stock"]), unit=row["unit"],
                    low_stock_threshold=float(row["min_threshold"]),
                    status=row["status"],
                    consumption_rate=f"{row['daily_consumption']} {row['unit']}/day",
                )
            self.inventory_details = {row["id"]: row for row in payload.get("items", [])}
        except Exception as exc:
            self.inventory_details = {}
            print(f"[state_store] seed inventory not loaded ({exc}); using the built-in items.")


state = StateStore()

# 🏭 AI Industrial Copilot

> **Next-Generation Autonomous Industrial Sentinel & Multi-Agent Tactical Decision Mesh**  
> Built for the AI Industrial Competition by a team of 4 engineering students.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![Three.js](https://img.shields.io/badge/Three.js-R3F-black?style=flat&logo=three.js&logoColor=white)](https://threejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4+-38B2AC?style=flat&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🎯 The Core Concept

Industrial manufacturing plants generate vast streams of fragmented data across IoT sensors, machine PLCs, CCTV cameras, and worker tracking systems. Operators and owners are overwhelmed by noisy alarms and lack cross-domain context when critical failures occur.

The **AI Industrial Copilot** continuously observes the plant, detects anomalies, correlates cross-domain evidence through a specialized multi-agent mesh, formulates explainable risk assessments, recommends standard operating procedures, and — **with explicit human-in-the-loop authorization** — executes defensive physical commands through connected industrial IoT actuators.

```
SENSE → ANALYZE → DETECT → REASON → RECOMMEND → AUTHORIZE → ACT → VERIFY → VISUALIZE
```

---

## 🧠 The 3 Major AI Systems

### 1. Multi-Agent Industrial Intelligence
A decentralized reasoning system composed of specialized agents that observe, detect trends, and communicate:
* **Temperature & Environmental Agent**: Monitors thermal gradients, atmospheric humidity, combustion aerosol particulates, and water levels across all plant sectors.
* **Machine KPI & Diagnostics Agent**: Scrutinizes high-frequency kinematics (pressure, spindle RPM, bearing vibration, production rate) to catch gradual mechanical degradation before failure.
* **Worker Safety & Productivity Agent**: Verifies mandatory PPE compliance (helmets, high-vis vests, gloves, safety boots) and detects workers in hazardous or restricted zones.
* **Cybersecurity Defense Agent**: Safeguards industrial fieldbus networks (Modbus/TCP, S7Comm, MQTT) against rogue devices and simulated brute-force authentication.
* **Strategic Recommendation Agent**: Correlates multi-agent hypotheses, queries the **RAG Knowledge Layer** (emergency procedures, equipment manuals, ISO regulations), and produces structured incidents with explainability (WHAT, WHY, HOW CONFIDENT, WHAT IMPACT, WHAT TO DO, WHO APPROVES).

### 2. AI + IoT Command & Action Agent
* Turns AI recommendations into executable IoT commands.
* Implements a strict **Human-in-the-Loop** safety architecture:
  * **LOW RISK** (automatic): notifications, telemetry frequency escalation.
  * **MEDIUM RISK** (owner confirmation): containment doors, ventilation damper adjustment.
  * **HIGH RISK** (explicit owner confirmation): emergency machine stop, sector evacuation, water suppression.
* **Post-Action Verification Loop**: Automatically verifies actuator physical feedback (e.g., spindle RPM drops to 0, temperature decreases) before resolving the incident.

### 3. AI + 3D Digital Twin & Visualization
* Real-time spatial representation of the plant rendered with **Three.js / React Three Fiber**.
* Visualizes:
  * Factory zones and boundaries (Zones A, B, C, D)
  * Dynamic machine 3D meshes with operational status indicators
  * Real-time worker avatars and coordinates
  * Environmental sensor halos and CCTV camera vectors
  * **Dynamic Risk Highlighting**: Pulsing thermal alerts, mechanical overpressure zones, fire markers (🔥), and cyber quarantine indicators (🔴).
  * Interactive object inspector modal upon clicking any machine or worker.

---

## 🎬 Live Competition Demonstration Scenarios

The dashboard features a **Jury Demo Scenario Driver Bar** at the top for instantaneous live demonstration:

1. **Normal Factory Baseline**: All kinematics, environmental sensors, and worker compliance within nominal thresholds. 3D twin reflects healthy green status.
2. **Scenario 1: Machine M-04 Overheating & Overpressure**:
   * Machine M-04 temperature ramps from 26°C → 51°C (+4.2°C/min).
   * Hydraulic pressure rises from 5.4 bar to 8.7 bar (Limit: 8.0 bar).
   * Temperature & Machine Agents detect anomaly and alert the Worker Agent (identifying 3 technicians in Zone B).
   * Strategic Recommendation Agent creates a **CRITICAL INCIDENT** with 94% confidence.
   * 3D Digital Twin highlights Zone B and pulses Machine M-04 in red.
   * Owner authorizes **EMERGENCY SHUTDOWN** in the Command Center.
   * IoT actuator halts Machine M-04, cooling engages, and post-action checks verify resolution.
3. **Scenario 2: Safe Industrial Cyber Attack**:
   * Simulated rogue hardware `UNKNOWN-DEVICE-07` attempts 47 unauthorized handshakes to Modbus PLC Gateway.
   * Cybersecurity Agent detects intrusion pattern and recommends network VLAN port isolation.
   * Owner confirms defensive containment.
4. **Scenario 3: Factory Fire Hazard**:
   * Dual-sensor correlation: optical smoke aerosols (>45 ppm) + thermal spike.
   * High-confidence fire classification triggering evacuation alarm, door containment, and clean-agent water suppression.

---

## 🗂️ System Architecture

```
industrial-ai-copilot/
├── backend/                  # FastAPI Backend & AI Engines
│   ├── app/
│   │   ├── api/              # REST Endpoints (Sensors, Machines, Incidents, Actions, AI, Twin, Demo)
│   │   ├── models/           # Pydantic Schemas & SQLAlchemy DB Models
│   │   ├── services/         # Event Bus, Command Engine, State Store
│   │   ├── ws/               # Unified WebSocket Manager (/ws/sensors, /ws/incidents, /ws/actions)
│   │   └── main.py           # FastAPI Application Entrypoint
│   ├── ai/
│   │   ├── agents/           # Temperature, Machine, Worker, Cyber, Recommendation Agents
│   │   ├── orchestrator.py   # Multi-Agent Coordination Mesh
│   │   └── rag/              # RAG Knowledge Layer (SOPs, Equipment Manuals, ISO Standards)
│   ├── iot/
│   │   └── simulator.py      # Real-Time Physical Sensor/Actuator Simulator & Scenarios
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                 # React 18 + TypeScript + Vite + Tailwind + R3F
│   ├── src/
│   │   ├── components/
│   │   │   ├── digital-twin/ # Interactive Three.js 3D Factory Canvas & Inspector
│   │   │   ├── ai/           # Multi-Agent View, IoT Command View, 3D Twin View
│   │   │   ├── views/        # Workers, Inventory, Cameras, Detections, Machines, Clients, Events
│   │   │   ├── Header.tsx    # "Welcome, Mr. X" Header & Live Status
│   │   │   ├── Sidebar.tsx   # 9-Section Navigation Control
│   │   │   └── MetricsBar.tsx# Real-Time Parameters Bar (Temp, Pressure, OEE, Alerts)
│   │   ├── services/         # REST API & WebSocket Real-Time Connectors
│   │   ├── types/            # TypeScript Type Contracts
│   │   └── App.tsx           # 3-Column Command Center Master Layout
│   ├── Dockerfile
│   └── package.json
│
├── docker-compose.yml        # Orchestration (Backend, Frontend, Redis, Mosquitto)
├── .env.example              # Environment Configuration Template
└── README.md
```

---

## 🚀 Quick Start Guide

### Option 1: Run Locally (Fastest)

#### Prerequisites
* Python 3.11+
* Node.js 18+ & npm

#### 1. Start the Backend
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
* Backend API: `http://localhost:8000`
* Interactive API Documentation (Swagger): `http://localhost:8000/docs`

#### 2. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```
* Dashboard Application: `http://localhost:5173`

---

### Option 2: Run with Docker Compose

```bash
docker compose up --build
```
This spins up:
* **Frontend** at `http://localhost:5173`
* **FastAPI Backend** at `http://localhost:8000`
* **Redis** at `localhost:6379`
* **Mosquitto MQTT Broker** at `localhost:1883`

---

## 👥 Engineering Team & Task Distribution

| Engineer | Role | Primary Responsibility |
|---|---|---|
| **Engineer 1** | **AI / Multi-Agent Lead** | Multi-Agent Mesh, 5 Specialized Agents, Orchestrator, Incident Engine, Risk Scoring, RAG Retrieval Layer |
| **Engineer 2** | **IoT / Backend Lead** | FastAPI Architecture, WebSocket Bus, Physical Sensor/Actuator Simulation, Command Engine & Verification |
| **Engineer 3** | **3D / Digital Twin Lead** | Three.js / React Three Fiber Scene, Machine/Worker Meshes, Dynamic Risk Overlays, Object Inspector |
| **Engineer 4** | **Frontend / UX Lead** | 3-Column Command Center Layout, 9 Navigation Sections, Real-time Metrics Bar, Human-in-the-Loop Dialogs |

---

## 📄 License
Developed for educational and AI competition purposes. All simulated data and scenarios are designed for demonstration of autonomous industrial safety systems.

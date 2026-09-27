# Standalone 3D Digital Twin + AI Industrial Copilot

This repository contains the **isolated 3D Digital Twin, Multi-Agent AI Orchestrator, Live CCTV Cameras, and Hackathon Scenarios** extracted from the main project.

It is completely decoupled from non-3D modules (such as HR, Client CRM, Inventory, Collaborations), allowing you to focus 100% on 3D visualization, interactive equipment inspection, AI perception, and real-time emergency scenarios.

---

## 🚀 Quick Start

Simply double-click `start_standalone.bat` or run:

```cmd
.\start_standalone.bat
```

This will automatically:
1. Launch the FastAPI backend on `http://localhost:8000` (IoT Simulator + Multi-Agent Orchestrator + WebSocket bus)
2. Launch the Vite + Three.js frontend on `http://localhost:5173`
3. Open your browser directly to the 3D Digital Twin environment.

---

## 🏗️ Architecture Overview

```
standalone-3d-ai-copilot/
├── backend/
│   ├── ai/
│   │   ├── agents/            # Safety Agent, Diagnostic Agent, Predictive Agent, Execution Agent
│   │   └── orchestrator.py    # Multi-Agent Coordinator
│   ├── app/
│   │   ├── api/               # Sensors, Machines, Scenarios, Incidents, Actions, Cameras API
│   │   ├── services/          # Realtime State Store, Event Bus, Command Engine
│   │   └── main.py            # FastAPI entry point & WebSockets
│   └── iot/
│       └── simulator.py       # Live telemetry generator (HVAC, CNC, Pumps, Transformers, Conveyor)
└── frontend/
    └── src/
        ├── components/
        │   ├── digital-twin/  # Factory3D, Equipment, Buildings, Infrastructure, InspectorModal
        │   ├── ai/            # MultiAgentView, DigitalTwinView, IoTCommandView
        │   ├── views/         # CamerasView (CCTV Grid with live Three.js virtual renderers)
        │   ├── DemoScenarioBar.tsx
        │   └── ScenarioProgressPanel.tsx
        ├── services/          # api.ts, websocket.ts, cameraPerception.ts
        └── App.tsx            # Clean layout dedicated strictly to 3D & AI Copilot
```

---

## 🎮 Features Included

1. **Photorealistic 3D Industrial Scene (`Factory3D.tsx`)**:
   - Modern dark theme with ambient glow, dynamic shadows, and high-tech grid floor.
   - 5 Detailed Equipment models: HVAC Unit, CNC Milling Center, Hydraulic Press, Electrical Transformer, Conveyor System.
   - Heatmap overlays, live status beacons, and 3D object clicking inspector.

2. **Multi-Agent AI Copilot (`MultiAgentView.tsx`)**:
   - Real-time decision logs for Safety Agent, Diagnostic Agent, Predictive Maintenance Agent, and Execution Agent.
   - Interactive command dispatching with human confirmation dialogs.

3. **CCTV & AI Perception Grid (`CamerasView.tsx`)**:
   - 4 Live Security & Process CCTV streams rendered directly from Three.js perspective angles.
   - Real-time AI detection overlays (Thermal anomaly alerts, Personnel detection, Pressure warnings).

4. **Interactive Hackathon Demo Scenarios (`DemoScenarioBar.tsx`)**:
   - Scenario 1: HVAC Overheating Emergency
   - Scenario 2: Conveyor Belt Jam & Thermal Anomaly
   - Scenario 3: Transformer Voltage Spike
   - Interactive Step-by-Step progress panel with automatic 3D camera transitions and resolution execution.

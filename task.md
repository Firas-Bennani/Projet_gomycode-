# Standalone 3D + AI Copilot Extraction

## Step 1: Create Directory Structure
- [x] Create `standalone-3d-ai-copilot/frontend/` scaffold
- [x] Create `standalone-3d-ai-copilot/backend/` scaffold

## Step 2: Extract Frontend
- [x] Copy `package.json` (trimmed — no inventory/client/etc.)
- [x] Copy config files (vite, tsconfig, tailwind, postcss)
- [x] Copy `index.html`
- [x] Copy `src/main.tsx`
- [x] Build dedicated `src/App.tsx` (3D + AI + Cameras + Scenarios only)
- [x] Copy `src/index.css`
- [x] Copy `src/types/index.ts`
- [x] Copy `src/services/api.ts` (trimmed)
- [x] Copy `src/services/websocket.ts`
- [x] Copy `src/services/cameraPerception.ts`
- [x] Copy all `src/components/digital-twin/` files
- [x] Copy all `src/components/ai/` files
- [x] Copy `src/components/views/CamerasView.tsx`
- [x] Copy scenario components (DemoScenarioBar, ScenarioProgressPanel, ConfirmationModal)

## Step 3: Extract Backend
- [x] Copy `iot/simulator.py`
- [x] Copy `ai/orchestrator.py`
- [x] Copy all `ai/agents/` files
- [x] Copy `app/services/` (event_bus, command_engine, state_store)
- [x] Copy `app/api/` (demo, sensors, machines, etc.)
- [x] Copy `app/main.py` (trimmed)
- [x] Copy `requirements.txt`

## Step 4: Create Launcher
- [x] Create `start_standalone.bat`
- [x] Create `README.md`

## Step 5: Install & Verify
- [x] Run `npm install` in standalone frontend
- [x] Run `npm run build` to verify compilation (Passed: 164 modules transformed cleanly)
- [x] Installed Python dependencies in standalone backend venv

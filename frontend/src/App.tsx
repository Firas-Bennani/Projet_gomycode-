import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { MetricsBar } from './components/MetricsBar';
import { DemoScenarioBar } from './components/DemoScenarioBar';
import { ScenarioProgressPanel } from './components/ScenarioProgressPanel';
import { Factory3D } from './components/digital-twin/Factory3D';
import { InspectorModal } from './components/digital-twin/InspectorModal';
import { ConfirmationModal } from './components/ConfirmationModal';

// AI Views
import { MultiAgentView } from './components/ai/MultiAgentView';
import { IoTCommandView } from './components/ai/IoTCommandView';
import { DigitalTwinView } from './components/ai/DigitalTwinView';

// Nav Section Views
import { WorkersView } from './components/views/WorkersView';
import { InventoryView } from './components/views/InventoryView';
import { CamerasView } from './components/views/CamerasView';
import { DetectionsView } from './components/views/DetectionsView';
import { MachinesView } from './components/views/MachinesView';
import { ClientsView } from './components/views/ClientsView';
import { CollaborationsView } from './components/views/CollaborationsView';
import { EventsView } from './components/views/EventsView';

import { api } from './services/api';
import { wsClient } from './services/websocket';
import { CameraPerceptionResult } from './services/cameraPerception';
import {
  Sensor, Machine, Worker, Camera, Incident, Action, RiskAssessment,
  AgentStatus, AgentLogEntry, Zone3D, InventoryItem, ClientItem,
  CollaborationItem, IndustrialEvent
} from './types';
import { BrainCircuit, Cpu, Layers } from 'lucide-react';

export function App() {
  // Navigation State
  const [currentSection, setCurrentSection] = useState<string>('overview');
  const [activeAITab, setActiveAITab] = useState<'multi-agent' | 'iot-command' | '3d-twin'>('multi-agent');

  // Plant Data State
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [risks, setRisks] = useState<RiskAssessment[]>([]);
  const [zones, setZones] = useState<Zone3D[]>([]);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [agentLogs, setAgentLogs] = useState<AgentLogEntry[]>([]);

  // Operational Nav Data
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [collaborations, setCollaborations] = useState<CollaborationItem[]>([]);
  const [events, setEvents] = useState<IndustrialEvent[]>([]);

  // UI Interactive State
  const [selected3DObject, setSelected3DObject] = useState<{ type: any; data: any } | null>(null);
  const [confirmingAction, setConfirmingAction] = useState<Action | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [currentScenario, setCurrentScenario] = useState<string>('normal');
  const [perceptionResults, setPerceptionResults] = useState<Record<string, CameraPerceptionResult>>({});

  // Initial Fetch & Setup
  useEffect(() => {
    loadAllData();
    wsClient.connect();

    // Subscribe to WebSocket events
    const unsubSensors = wsClient.subscribe('SENSOR_READING', (payload) => {
      const data = payload.data;
      if (!data) return;
      setSensors((prev) =>
        prev.map((s) => (s.id === data.sensor_id ? { ...s, current_value: data.value, status: payload.severity || s.status } : s))
      );
    });

    const unsubMachines = wsClient.subscribe('MACHINE_STATUS', (payload) => {
      const data = payload.data;
      if (!data) return;
      setMachines((prev) =>
        prev.map((m) =>
          m.id === data.machine_id
            ? {
                ...m,
                status: payload.severity || m.status,
                parameters: {
                  ...m.parameters,
                  pressure: { ...m.parameters.pressure, value: data.parameters?.pressure?.value ?? m.parameters.pressure?.value },
                  temperature: { ...m.parameters.temperature, value: data.parameters?.temperature?.value ?? m.parameters.temperature?.value },
                  vibration: { ...m.parameters.vibration, value: data.parameters?.vibration?.value ?? m.parameters.vibration?.value },
                }
              }
            : m
        )
      );
    });

    const unsubIncidents = wsClient.subscribe('INCIDENT_CREATED', (payload) => {
      const inc = payload.data;
      if (!inc) return;
      setIncidents((prev) => [inc, ...prev.filter((i) => i.id !== inc.id)]);
      // Auto-switch to IoT Command tab to show pending approval for jury
      setActiveAITab('iot-command');
    });

    const unsubIncidentUpdate = wsClient.subscribe('INCIDENT_UPDATED', (payload) => {
      const inc = payload.data;
      if (!inc) return;
      setIncidents((prev) => prev.map((i) => (i.id === inc.id ? inc : i)));
    });

    const unsubActions = wsClient.subscribe('ACTION_STATUS', (payload) => {
      const act = payload.data;
      if (!act) return;
      setActions((prev) => [act, ...prev.filter((a) => a.id !== act.id)]);
    });

    const unsubAgents = wsClient.subscribe('agents', () => {
      refreshAgents();
    });

    const unsubReset = wsClient.subscribe('FACTORY_RESET', () => {
      loadAllData();
      setCurrentScenario('normal');
    });

    // Periodic poll fallback for agent chatter
    const interval = setInterval(refreshAgents, 3000);

    return () => {
      unsubSensors();
      unsubMachines();
      unsubIncidents();
      unsubIncidentUpdate();
      unsubActions();
      unsubAgents();
      unsubReset();
      clearInterval(interval);
    };
  }, []);

  const loadAllData = async () => {
    try {
      const [
        sRes, mRes, wRes, cRes, iRes, aRes, dtRes, agRes, logRes,
        invRes, cliRes, colRes, evtRes, rskRes
      ] = await Promise.all([
        api.getSensors(),
        api.getMachines(),
        api.getWorkers(),
        api.getCameras(),
        api.getIncidents(),
        api.getActions(),
        api.getDigitalTwinState(),
        api.getAgents(),
        api.getAgentLogs(),
        api.getInventory(),
        api.getClients(),
        api.getCollaborations(),
        api.getEvents(),
        api.getRisks(),
      ]);

      setSensors(sRes.sensors || []);
      setMachines(mRes.machines || []);
      setWorkers(wRes.workers || []);
      setCameras(cRes.cameras || []);
      setIncidents(iRes.incidents || []);
      setActions(aRes.actions || []);
      setZones(dtRes.zones || []);
      setAgents(agRes.agents || []);
      setAgentLogs(logRes.logs || []);
      setInventory(invRes.inventory || []);
      setClients(cliRes.clients || []);
      setCollaborations(colRes.collaborations || []);
      setEvents(evtRes.events || []);
      setRisks(rskRes.risks || []);
    } catch (e) {
      console.error('Failed to load initial data:', e);
    }
  };

  const refreshAgents = async () => {
    try {
      const [agRes, logRes] = await Promise.all([api.getAgents(), api.getAgentLogs()]);
      setAgents(agRes.agents || []);
      setAgentLogs(logRes.logs || []);
    } catch (e) {
      // quiet poll
    }
  };

  const handleTriggerScenario = async (scenario: string) => {
    setCurrentScenario(scenario);
    try {
      await api.triggerScenario(scenario);
    } catch (err) {
      console.error('Failed to trigger scenario:', err);
    }
  };

  const handleReset = async () => {
    try {
      await api.resetDemo();
      loadAllData();
      setCurrentScenario('normal');
      setSelected3DObject(null);
    } catch (err) {
      console.error('Failed to reset demo:', err);
    }
  };

  const handleAuthorizeAction = async () => {
    if (!confirmingAction) return;
    setActionLoading(true);
    try {
      await api.authorizeAction(confirmingAction.id);
      setConfirmingAction(null);
      // Reload actions
      const aRes = await api.getActions();
      setActions(aRes.actions || []);
    } catch (err) {
      console.error('Error authorizing action:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelAction = async (action: Action) => {
    try {
      await api.cancelAction(action.id);
      const aRes = await api.getActions();
      setActions(aRes.actions || []);
    } catch (err) {
      console.error('Error cancelling action:', err);
    }
  };

  const activeAlertCount = incidents.filter((i) => i.status === 'ACTIVE').length;
  const pendingActionsCount = actions.filter((a) => a.status === 'AWAITING_APPROVAL').length;

  return (
    <div className="h-screen w-screen flex flex-col bg-[#050914] text-slate-100 overflow-hidden font-sans">
      {/* Top Header */}
      <Header activeAlertCount={activeAlertCount} />

      {/* Demo Scenario Driver Bar for Jury */}
      <DemoScenarioBar
        currentScenario={currentScenario}
        onTriggerScenario={handleTriggerScenario}
        onReset={handleReset}
      />

      {/* Main 3-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* COLUMN 1 — NAVIGATION (Left) */}
        <Sidebar
          currentSection={currentSection}
          onSelectSection={setCurrentSection}
          activeIncidentsCount={activeAlertCount}
          pendingActionsCount={pendingActionsCount}
        />

        {/* COLUMN 2 — MAIN FACTORY VIEW / SECTION VIEW (Center) */}
        <main className="flex-1 flex flex-col overflow-hidden relative p-3 gap-3">
          {currentSection === 'overview' && (
            <div className="flex-1 flex flex-col gap-3 min-h-0">
              {/* Scenario Progress & Driver Panel */}
              <ScenarioProgressPanel
                currentScenario={currentScenario}
                incidents={incidents}
                actions={actions}
                sensors={sensors}
                machines={machines}
                onAuthorizeAction={(act) => setConfirmingAction(act)}
              />

              {/* 3D Factory Canvas */}
              <div className="flex-1 relative min-h-0">
                <Factory3D
                  machines={machines}
                  workers={workers}
                  sensors={sensors}
                  zones={zones}
                  incidents={incidents}
                  actions={actions}
                  currentScenario={currentScenario}
                  selectedId={selected3DObject?.data?.id}
                  onSelectObject={setSelected3DObject}
                  onPerceptionUpdate={setPerceptionResults}
                />

                {/* Inspect Modal Overlay */}
                <InspectorModal
                  selectedObject={selected3DObject}
                  onClose={() => setSelected3DObject(null)}
                />
              </div>

              {/* Real-time Parameters Panel below 3D */}
              <MetricsBar
                sensors={sensors}
                machines={machines}
                incidents={incidents}
                workers={workers}
              />
            </div>
          )}

          {currentSection === 'workers' && <WorkersView workers={workers} />}
          {currentSection === 'inventory' && <InventoryView items={inventory} />}
          {currentSection === 'cameras' && <CamerasView cameras={cameras} perceptionResults={perceptionResults} />}
          {currentSection === 'command-center' && (
            <div className="h-full glass-panel rounded-xl p-4 overflow-y-auto">
              <IoTCommandView
                actions={actions}
                onAuthorize={(act) => setConfirmingAction(act)}
                onCancel={handleCancelAction}
              />
            </div>
          )}
          {currentSection === 'detections' && <DetectionsView incidents={incidents} />}
          {currentSection === 'clients' && <ClientsView clients={clients} />}
          {currentSection === 'collaborations' && <CollaborationsView items={collaborations} />}
          {currentSection === 'events' && <EventsView events={events} />}
          {currentSection === 'machines' && <MachinesView machines={machines} />}
        </main>

        {/* COLUMN 3 — THREE MAJOR AI SYSTEMS (Right) */}
        <aside className="w-96 glass-panel border-l border-slate-800 flex flex-col p-3 gap-3 select-none">
          {/* AI System Selector Tabs */}
          <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-950/80 rounded-xl border border-slate-800 text-xs font-mono">
            <button
              onClick={() => setActiveAITab('multi-agent')}
              className={`py-2 px-2 rounded-lg flex flex-col items-center gap-1 transition-all ${
                activeAITab === 'multi-agent'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-glow-cyan font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BrainCircuit className="w-4 h-4" />
              <span className="text-[10px]">1. Multi-Agent</span>
            </button>

            <button
              onClick={() => setActiveAITab('iot-command')}
              className={`py-2 px-2 rounded-lg flex flex-col items-center gap-1 transition-all relative ${
                activeAITab === 'iot-command'
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-glow-cyan font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Cpu className="w-4 h-4" />
              <span className="text-[10px]">2. AI + IoT</span>
              {pendingActionsCount > 0 && (
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
              )}
            </button>

            <button
              onClick={() => setActiveAITab('3d-twin')}
              className={`py-2 px-2 rounded-lg flex flex-col items-center gap-1 transition-all ${
                activeAITab === '3d-twin'
                  ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-glow-cyan font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span className="text-[10px]">3. AI + 3D</span>
            </button>
          </div>

          {/* Active AI System Content */}
          <div className="flex-1 overflow-hidden min-h-0">
            {activeAITab === 'multi-agent' && (
              <MultiAgentView agents={agents} logs={agentLogs} />
            )}

            {activeAITab === 'iot-command' && (
              <IoTCommandView
                actions={actions}
                onAuthorize={(act) => setConfirmingAction(act)}
                onCancel={handleCancelAction}
              />
            )}

            {activeAITab === '3d-twin' && (
              <DigitalTwinView
                risks={risks}
                zones={zones}
                incidents={incidents}
              />
            )}
          </div>
        </aside>
      </div>

      {/* Human-in-the-Loop Confirmation Modal */}
      <ConfirmationModal
        action={confirmingAction}
        onConfirm={handleAuthorizeAction}
        onCancel={() => setConfirmingAction(null)}
        loading={actionLoading}
      />
    </div>
  );
}

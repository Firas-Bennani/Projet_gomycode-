import React, { useEffect, useState } from 'react';
import { Play, CheckCircle2, Clock, AlertTriangle, ShieldCheck, Activity, ChevronRight, Zap } from 'lucide-react';
import { Incident, Action, Sensor, Machine } from '../types';

interface ScenarioProgressPanelProps {
  currentScenario: string;
  incidents: Incident[];
  actions: Action[];
  sensors: Sensor[];
  machines: Machine[];
  onAuthorizeAction?: (action: Action) => void;
}

export const ScenarioProgressPanel: React.FC<ScenarioProgressPanelProps> = ({
  currentScenario,
  incidents,
  actions,
  sensors,
  machines,
  onAuthorizeAction
}) => {
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (currentScenario === 'normal') {
      setElapsedTime(0);
      return;
    }
    const timer = setInterval(() => {
      setElapsedTime((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [currentScenario]);

  if (currentScenario === 'normal') {
    return (
      <div className="px-4 py-2 bg-slate-950/80 border border-slate-800 rounded-xl flex items-center justify-between text-xs font-mono text-slate-400">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-slate-300 font-semibold">PLANT BASELINE NORMAL</span>
          <span className="text-slate-500">• Telemetry nominal across all 4 zones</span>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <span>Temp: 25.5°C</span>
          <span>Pressure: 5.2 bar</span>
          <span className="text-emerald-400 font-bold">STATUS: OK</span>
        </div>
      </div>
    );
  }

  // Active Incident / Action status lookup
  const activeIncident = incidents.find((i) => i.status === 'ACTIVE');
  const activeAction = actions.find((a) => a.incident_id === activeIncident?.id || a.status === 'AWAITING_APPROVAL' || a.status === 'IN_PROGRESS');
  const tempSensor = sensors.find((s) => s.id === 'TEMP-B-01');

  // Determine stage flags
  const isStarted = currentScenario !== 'normal';
  const isAnomalyDetected = (tempSensor && tempSensor.current_value > 30.0) || (activeIncident !== undefined);
  const isIncidentCreated = !!activeIncident;
  const isActionProposed = !!activeAction;
  const isActionAuthorized = activeAction?.status === 'AUTHORIZED' || activeAction?.status === 'IN_PROGRESS' || activeAction?.status === 'COMPLETED';
  const isActionExecuting = activeAction?.status === 'IN_PROGRESS';
  const isCoolingDown = tempSensor ? tempSensor.current_value < 45.0 && isActionAuthorized : false;
  const isResolved = !activeIncident && isActionAuthorized;

  // Format elapsed time MM:SS
  const mins = Math.floor(elapsedTime / 60).toString().padStart(2, '0');
  const secs = (elapsedTime % 60).toString().padStart(2, '0');

  const steps = [
    { title: 'Scenario Initiated', done: isStarted, active: isStarted && !isAnomalyDetected },
    { title: 'Anomaly Detected', done: isAnomalyDetected, active: isAnomalyDetected && !isIncidentCreated },
    { title: 'AI Incident Created', done: isIncidentCreated, active: isIncidentCreated && !isActionProposed },
    { title: 'Action Proposed', done: isActionProposed, active: isActionProposed && !isActionAuthorized },
    { title: 'Human Authorized', done: isActionAuthorized, active: isActionAuthorized && !isActionExecuting },
    { title: 'Telemetry Normalizing', done: isCoolingDown || isResolved, active: isCoolingDown && !isResolved },
    { title: 'Verified & Resolved', done: isResolved, active: isResolved }
  ];

  return (
    <div className="p-3 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 border border-cyan-500/40 rounded-xl shadow-2xl space-y-2.5 font-mono select-none">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />
          <h3 className="text-xs font-bold text-white tracking-wider uppercase flex items-center gap-1.5">
            <Zap className="w-4 h-4 text-cyan-400" />
            SCENARIO RUNTIME LIFECYCLE: <span className="text-cyan-300">{currentScenario.toUpperCase().replace('_', ' ')}</span>
          </h3>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1 text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>ELAPSED: <strong className="text-white">{mins}:{secs}</strong></span>
          </div>

          <div className="px-2.5 py-0.5 rounded text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            STAGE: {isResolved ? 'RESOLVED' : isCoolingDown ? 'COOLING DOWN' : isActionAuthorized ? 'ACTION AUTHORIZED' : isActionProposed ? 'AWAITING APPROVAL' : 'DEVELOPING'}
          </div>
        </div>
      </div>

      {/* Interactive Step-by-Step Flow Bar */}
      <div className="grid grid-cols-2 md:grid-cols-7 gap-1.5">
        {steps.map((s, idx) => (
          <div
            key={idx}
            className={`p-1.5 rounded-lg border text-[11px] flex flex-col justify-between transition-all ${
              s.done
                ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
                : s.active
                ? 'bg-cyan-950/60 border-cyan-400 text-cyan-200 shadow-glow-cyan animate-pulse'
                : 'bg-slate-950/40 border-slate-800/80 text-slate-500'
            }`}
          >
            <div className="flex items-center justify-between text-[10px]">
              <span className="opacity-70">0{idx + 1}</span>
              {s.done ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : s.active ? (
                <Activity className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
              ) : (
                <span className="w-3 h-3 rounded-full border border-slate-700 inline-block" />
              )}
            </div>
            <span className="font-bold text-[10.5px] truncate mt-1">{s.title}</span>
          </div>
        ))}
      </div>

      {/* Action quick bar if action awaiting authorization */}
      {activeAction && activeAction.status === 'AWAITING_APPROVAL' && onAuthorizeAction && (
        <div className="p-2.5 bg-amber-950/50 border border-amber-500/60 rounded-lg flex items-center justify-between text-xs animate-bounce">
          <div className="flex items-center gap-2 text-amber-200 font-semibold">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>HUMAN-IN-THE-LOOP AUTHORIZATION REQUIRED: <strong className="text-white">{activeAction.action_type} ({activeAction.target})</strong></span>
          </div>
          <button
            onClick={() => onAuthorizeAction(activeAction)}
            className="px-3 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded shadow-lg transition-all text-xs"
          >
            AUTHORIZE ACTION NOW
          </button>
        </div>
      )}
    </div>
  );
};

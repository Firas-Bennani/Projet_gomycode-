import React from 'react';
import { Play, RotateCcw, Flame, ShieldAlert, Sparkles, AlertTriangle, CloudLightning, UserX } from 'lucide-react';

interface DemoScenarioBarProps {
  currentScenario: string;
  onTriggerScenario: (scenario: string) => void;
  onReset: () => void;
}

export const DemoScenarioBar: React.FC<DemoScenarioBarProps> = ({
  currentScenario,
  onTriggerScenario,
  onReset,
}) => {
  return (
    <div className="h-11 px-4 glass-panel border-b border-slate-800/90 flex items-center justify-between text-xs font-mono select-none">
      <div className="flex items-center gap-2">
        <span className="text-slate-400 font-bold flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>JURY DEMO SCENARIO DRIVER:</span>
        </span>
      </div>

      <div className="flex items-center gap-2 overflow-x-auto">
        <button
          onClick={() => onTriggerScenario('normal')}
          className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
            currentScenario === 'normal'
              ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/50 shadow-sm'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span>Normal Baseline</span>
        </button>

        <button
          onClick={() => onTriggerScenario('machine_overheating')}
          className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
            currentScenario === 'machine_overheating'
              ? 'bg-red-600/40 text-red-300 border border-red-500/60 shadow-glow-red animate-pulse'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
          <span>Scenario 1: M-04 Overheating</span>
        </button>

        <button
          onClick={() => onTriggerScenario('cybersecurity')}
          className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
            currentScenario === 'cybersecurity'
              ? 'bg-purple-600/40 text-purple-300 border border-purple-500/60 shadow-sm animate-pulse'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5 text-purple-400" />
          <span>Scenario 2: Cyber Intrusion</span>
        </button>

        <button
          onClick={() => onTriggerScenario('fire')}
          className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
            currentScenario === 'fire'
              ? 'bg-amber-600/40 text-amber-300 border border-amber-500/60 shadow-sm animate-pulse'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800'
          }`}
        >
          <Flame className="w-3.5 h-3.5 text-amber-400" />
          <span>Scenario 3: Factory Fire</span>
        </button>

        <button
          onClick={() => onTriggerScenario('storm_forecast')}
          title="Predictive: a storm is forecast, the plant is prepared before it arrives"
          className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
            currentScenario === 'storm_forecast'
              ? 'bg-sky-600/40 text-sky-300 border border-sky-500/60 shadow-sm animate-pulse'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800'
          }`}
        >
          <CloudLightning className="w-3.5 h-3.5 text-sky-400" />
          <span>Scenario 4: Storm Forecast (predictive)</span>
        </button>

        <button
          onClick={() => onTriggerScenario('agent_attack')}
          title="An attacker forges messages on the copilot's own agent bus. No machine is touched."
          className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
            currentScenario === 'agent_attack'
              ? 'bg-fuchsia-600/40 text-fuchsia-300 border border-fuchsia-500/60 shadow-sm animate-pulse'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800'
          }`}
        >
          <UserX className="w-3.5 h-3.5 text-fuchsia-400" />
          <span>Scenario 5: Forged Agent Message</span>
        </button>

        <button
          onClick={onReset}
          title="Reset factory state"
          className="p-1 px-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md text-xs transition-colors flex items-center gap-1 border border-slate-700 ml-2"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset</span>
        </button>
      </div>
    </div>
  );
};

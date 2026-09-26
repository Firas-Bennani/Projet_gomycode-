import React from 'react';
import { Action } from '../../types';
import { ShieldCheck, CheckCircle2, XCircle, Clock, Cpu, AlertTriangle, PlayCircle } from 'lucide-react';

interface IoTCommandViewProps {
  actions: Action[];
  onAuthorize: (action: Action) => void;
  onCancel: (action: Action) => void;
}

export const IoTCommandView: React.FC<IoTCommandViewProps> = ({
  actions,
  onAuthorize,
  onCancel,
}) => {
  const pendingActions = actions.filter(
    (a) => a.status === 'AWAITING_APPROVAL' || a.status === 'PENDING'
  );
  const activeOrCompleted = actions.filter(
    (a) => a.status !== 'AWAITING_APPROVAL' && a.status !== 'PENDING'
  );

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto pr-1">
      {/* Header Banner */}
      <div className="glass-panel p-4 rounded-xl border border-sky-500/20">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-sky-400" />
            <h2 className="text-sm font-bold text-white tracking-wide uppercase">
              SYSTEM 2 — AI + IOT COMMAND & EXECUTION
            </h2>
          </div>
          <span className="px-2 py-0.5 text-[11px] font-mono bg-sky-950/60 text-sky-400 border border-sky-800/40 rounded-full">
            HUMAN-IN-THE-LOOP ACTIVE
          </span>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Sensitive actuator commands (shutdown, fire suppression, perimeter locks) require owner confirmation before execution through the IoT industrial bus.
        </p>
      </div>

      {/* Pending Actions (Human Authorization Required) */}
      <div>
        <h3 className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <span>Pending Owner Authorization ({pendingActions.length})</span>
        </h3>

        {pendingActions.length === 0 ? (
          <div className="glass-panel p-5 rounded-xl border border-slate-800 text-center text-xs text-slate-400 font-mono">
            ✓ Zero pending high-risk commands. Plant IoT actuators in nominal standby.
          </div>
        ) : (
          <div className="space-y-3">
            {pendingActions.map((action) => (
              <div
                key={action.id}
                className="glass-panel p-4 rounded-xl border border-amber-500/40 bg-amber-950/15 shadow-glow-amber space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                    {action.risk_level} RISK
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    ID: {action.id}
                  </span>
                </div>

                <div>
                  <h4 className="text-sm font-bold text-white tracking-tight">
                    {action.action_type.replace(/_/g, ' ')} → {action.target}
                  </h4>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                    {action.reason}
                  </p>
                </div>

                <div className="flex items-center gap-2 pt-1 border-t border-amber-900/40">
                  <button
                    onClick={() => onAuthorize(action)}
                    className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition-all shadow-md flex items-center justify-center gap-1.5"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>AUTHORIZE ACTION</span>
                  </button>
                  <button
                    onClick={() => onCancel(action)}
                    className="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition-all border border-slate-700"
                  >
                    CANCEL
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action Execution History & Verification */}
      <div className="flex-1">
        <h3 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>Execution & Verification History</span>
        </h3>

        <div className="space-y-2.5">
          {activeOrCompleted.map((action) => (
            <div
              key={action.id}
              className="glass-panel p-3.5 rounded-xl border border-slate-800 text-xs font-mono space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-200">
                  {action.action_type.replace(/_/g, ' ')}
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    action.status === 'COMPLETED'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : action.status === 'IN_PROGRESS'
                      ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30 animate-pulse'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {action.status}
                </span>
              </div>

              <div className="text-[11px] text-slate-400">Target: {action.target}</div>

              {action.verification && (
                <div className="p-2 bg-slate-950/80 rounded border border-slate-900 text-[10px] space-y-1">
                  <div className="text-emerald-400 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>IoT POST-ACTION VERIFICATION PASSED:</span>
                  </div>
                  {action.verification.checks?.map((c, i) => (
                    <div key={i} className="text-slate-300">
                      • {c.check}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

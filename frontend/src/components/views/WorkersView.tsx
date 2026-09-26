import React from 'react';
import { Worker } from '../../types';
import { Users, HardHat, ShieldCheck, AlertCircle, Clock } from 'lucide-react';

export const WorkersView: React.FC<{ workers: Worker[] }> = ({ workers }) => {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            WORKFORCE SAFETY & PRODUCTIVITY MONITOR
          </h2>
        </div>
        <span className="px-3 py-1 bg-cyan-950/60 border border-cyan-800/40 text-cyan-400 rounded-full text-xs font-mono font-bold">
          {workers.filter((w) => w.status === 'ON_SITE').length} OPERATORS ACTIVE
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {workers.map((worker) => (
          <div key={worker.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-white">{worker.name}</h4>
                <div className="text-xs text-slate-400 font-mono">ID: {worker.id} • {worker.role}</div>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                worker.status === 'AT_RISK' ? 'bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse' : 'bg-emerald-500/20 text-emerald-400'
              }`}>
                {worker.status}
              </span>
            </div>

            <div className="flex items-center justify-between text-xs font-mono bg-slate-950/60 p-2 rounded border border-slate-900">
              <span className="text-slate-400">Station Sector:</span>
              <span className="text-cyan-400 font-bold">{worker.zone}</span>
            </div>

            <div className="text-xs space-y-1.5 border-t border-slate-800/80 pt-2 font-mono">
              <div className="text-[11px] text-slate-400 flex items-center justify-between">
                <span>Shift Duration:</span>
                <span className="text-slate-200">{worker.working_hours_today} hrs (Checked in {worker.entry_time})</span>
              </div>
              <div className="text-[11px] text-slate-400">PPE Safety Verification:</div>
              <div className="grid grid-cols-2 gap-1 text-[10px]">
                <span className={worker.ppe.helmet ? 'text-emerald-400' : 'text-red-400 font-bold'}>
                  {worker.ppe.helmet ? '✓ Helmet' : '✗ Helmet'}
                </span>
                <span className={worker.ppe.vest ? 'text-emerald-400' : 'text-red-400 font-bold'}>
                  {worker.ppe.vest ? '✓ Hi-Vis Vest' : '✗ Hi-Vis Vest'}
                </span>
                <span className={worker.ppe.gloves ? 'text-emerald-400' : 'text-amber-400'}>
                  {worker.ppe.gloves ? '✓ Gloves' : '✗ Gloves'}
                </span>
                <span className={worker.ppe.safety_shoes ? 'text-emerald-400' : 'text-red-400 font-bold'}>
                  {worker.ppe.safety_shoes ? '✓ Safety Boots' : '✗ Boots'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

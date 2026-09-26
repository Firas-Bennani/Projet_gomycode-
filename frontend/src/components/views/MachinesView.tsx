import React from 'react';
import { Machine } from '../../types';
import { Activity, Gauge, Zap, Thermometer, AlertTriangle } from 'lucide-react';

export const MachinesView: React.FC<{ machines: Machine[] }> = ({ machines }) => {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            INDUSTRIAL MACHINE TELEMETRY & KPI MATRIX
          </h2>
        </div>
        <span className="px-3 py-1 bg-slate-900 border border-slate-800 text-slate-300 rounded-full text-xs font-mono">
          {machines.length} KINEMATIC CELLS
        </span>
      </div>

      <div className="space-y-4">
        {machines.map((machine) => (
          <div key={machine.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">{machine.name}</h3>
                <div className="text-xs text-slate-400">ID: {machine.id} • Sector: {machine.zone} • Uptime: {machine.uptime_hours} hrs</div>
              </div>
              <span className={`px-2.5 py-1 rounded text-xs font-bold ${
                machine.status === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse' :
                machine.status === 'WARNING' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
                'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
              }`}>
                {machine.status}
              </span>
            </div>

            {/* Gauges Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 text-xs">
              {Object.entries(machine.parameters).map(([key, p]: [string, any]) => (
                <div key={key} className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-900 flex flex-col justify-between">
                  <span className="text-[10px] text-slate-500 uppercase block">{key}</span>
                  <div className={`text-base font-bold mt-1 ${p.status === 'CRITICAL' ? 'text-red-400' : 'text-slate-100'}`}>
                    {p.value} <span className="text-[10px] text-slate-400">{p.unit}</span>
                  </div>
                  {p.threshold && (
                    <div className="text-[10px] text-slate-500 mt-1">
                      Max: {p.threshold} {p.unit}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

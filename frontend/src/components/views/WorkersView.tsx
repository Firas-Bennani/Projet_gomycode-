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
      <div className="mt-6 border-t border-slate-800 pt-6">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-bold text-white tracking-wide">SYSTÈME DE POINTAGE & PRÉSENCE (LOGS)</h3>
        </div>
        <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/40">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-4 py-2 font-semibold">WORKER</th>
                <th className="px-4 py-2 font-semibold">ID BADGE</th>
                <th className="px-4 py-2 font-semibold">CHECK IN</th>
                <th className="px-4 py-2 font-semibold">CHECK OUT</th>
                <th className="px-4 py-2 font-semibold">STATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {workers.map((w, i) => (
                <tr key={`pointage-${w.id}`} className="hover:bg-slate-800/30">
                  <td className="px-4 py-2.5 font-bold text-white">{w.name}</td>
                  <td className="px-4 py-2.5 text-slate-400">{w.id}</td>
                  <td className="px-4 py-2.5 text-emerald-400">{w.entry_time}</td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {w.status === 'ON_SITE' ? '--- (Active)' : '17:00:00'}
                  </td>
                  <td className="px-4 py-2.5">
                    {w.status === 'ON_SITE' ? (
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">Présent (Validé par IA/Caméra)</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-slate-500/20 text-slate-400">Absent</span>
                    )}
                  </td>
                </tr>
              ))}
              {/* Dummy row to demonstrate "False Presence" detection feature requested by owner */}
              <tr className="hover:bg-slate-800/30">
                <td className="px-4 py-2.5 font-bold text-red-400">John Doe (Anomalie)</td>
                <td className="px-4 py-2.5 text-slate-400">WRK-999</td>
                <td className="px-4 py-2.5 text-emerald-400">08:15:00</td>
                <td className="px-4 py-2.5 text-slate-500">---</td>
                <td className="px-4 py-2.5">
                  <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse">
                    Fausse Présence Détectée (Caméra: Non trouvé)
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import { X, AlertTriangle, ShieldCheck, Thermometer, Gauge, Zap, Activity } from 'lucide-react';
import { Machine, Worker, Sensor } from '../../types';

interface InspectorModalProps {
  selectedObject: { type: 'machine' | 'worker' | 'sensor' | 'zone'; data: any } | null;
  onClose: () => void;
  onQuickAction?: (actionType: string, target: string) => void;
}

export const InspectorModal: React.FC<InspectorModalProps> = ({
  selectedObject,
  onClose,
  onQuickAction
}) => {
  if (!selectedObject) return null;
  const { type, data } = selectedObject;

  return (
    <div className="absolute top-4 right-4 z-40 w-96 glass-panel rounded-xl border border-cyan-500/30 p-5 shadow-2xl animate-in fade-in slide-in-from-top-4 duration-200">
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/60 mb-4">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          <h3 className="font-semibold text-slate-100 text-sm tracking-wide uppercase">
            {type.toUpperCase()} TELEMETRY INSPECTION
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {type === 'machine' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-lg font-bold text-white tracking-tight">{data.name}</div>
              <div className="text-xs text-slate-400 font-mono">ID: {data.id} • {data.zone}</div>
            </div>
            <span
              className={`px-2.5 py-1 rounded-full text-xs font-bold border ${
                data.status === 'CRITICAL'
                  ? 'bg-red-500/20 text-red-400 border-red-500/40'
                  : data.status === 'WARNING'
                  ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                  : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
              }`}
            >
              {data.status}
            </span>
          </div>

          {/* Parameters Grid */}
          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            {Object.entries(data.parameters || {}).map(([key, val]: [string, any]) => (
              <div key={key} className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                <span className="text-slate-400 uppercase text-[10px] block mb-1">{key}</span>
                <span className={`text-sm font-bold ${val.status === 'CRITICAL' ? 'text-red-400' : 'text-slate-200'}`}>
                  {val.value} {val.unit}
                </span>
                {val.threshold && (
                  <span className="text-[10px] text-slate-500 block">Max: {val.threshold}</span>
                )}
              </div>
            ))}
          </div>

          {/* AI Diagnosis */}
          <div className="bg-cyan-950/40 border border-cyan-800/40 rounded-lg p-3 text-xs">
            <span className="font-semibold text-cyan-400 block mb-1">🤖 AI COPILOT REASONING</span>
            <p className="text-slate-300 leading-relaxed text-[11px]">
              {data.status === 'CRITICAL'
                ? `Critical thermodynamic & hydraulic anomaly detected on ${data.id}. Automated protective shutdown recommended to prevent mechanical breach.`
                : `Kinematic signatures for ${data.id} conform to ISO operational thresholds. Spindle bearing vibration and thermal gradient nominal.`}
            </p>
          </div>
        </div>
      )}

      {type === 'worker' && (
        <div className="space-y-4 text-xs">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-lg font-bold text-white">{data.name}</div>
              <div className="text-xs text-slate-400 font-mono">ID: {data.id} • {data.role}</div>
            </div>
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-xs font-mono">
              {data.status}
            </span>
          </div>

          <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800 space-y-2">
            <div className="text-slate-400 font-mono">Current Sector: <span className="text-white">{data.zone}</span></div>
            <div className="text-slate-400 font-mono">Shift Duration: <span className="text-white">{data.working_hours_today} hrs</span></div>
            <div className="text-slate-400 font-mono">Checked In: <span className="text-white">{data.entry_time}</span></div>
          </div>

          <div className="border border-slate-800 rounded-lg p-3">
            <span className="text-slate-400 block mb-2 font-mono">Mandatory PPE Compliance:</span>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <span className={data.ppe.helmet ? 'text-emerald-400' : 'text-red-400'}>
                {data.ppe.helmet ? '✓ Helmet' : '✗ Helmet Missing'}
              </span>
              <span className={data.ppe.vest ? 'text-emerald-400' : 'text-red-400'}>
                {data.ppe.vest ? '✓ Safety Vest' : '✗ Vest Missing'}
              </span>
              <span className={data.ppe.gloves ? 'text-emerald-400' : 'text-amber-400'}>
                {data.ppe.gloves ? '✓ Gloves' : '✗ Gloves'}
              </span>
              <span className={data.ppe.safety_shoes ? 'text-emerald-400' : 'text-red-400'}>
                {data.ppe.safety_shoes ? '✓ Safety Shoes' : '✗ Shoes'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

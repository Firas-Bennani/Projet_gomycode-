import React from 'react';
import { RiskAssessment, Zone3D, Incident } from '../../types';
import { Layers, Flame, Droplets, AlertTriangle, ShieldAlert, User, Eye } from 'lucide-react';

interface DigitalTwinViewProps {
  risks: RiskAssessment[];
  zones: Zone3D[];
  incidents: Incident[];
}

export const DigitalTwinView: React.FC<DigitalTwinViewProps> = ({
  risks,
  zones,
  incidents,
}) => {
  const getRiskIcon = (type: string) => {
    switch (type.toUpperCase()) {
      case 'FIRE':
      case 'INDUSTRIAL_FIRE':
        return <Flame className="w-4 h-4 text-red-400" />;
      case 'FLOOD':
        return <Droplets className="w-4 h-4 text-cyan-400" />;
      case 'CYBER_INTRUSION':
        return <ShieldAlert className="w-4 h-4 text-purple-400" />;
      default:
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
    }
  };

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto pr-1">
      {/* Header Banner */}
      <div className="glass-panel p-4 rounded-xl border border-cyan-500/20">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h2 className="text-sm font-bold text-white tracking-wide uppercase">
              SYSTEM 3 — AI + 3D DIGITAL TWIN & VISUALIZATION
            </h2>
          </div>
          <span className="px-2 py-0.5 text-[11px] font-mono bg-cyan-950/60 text-cyan-400 border border-cyan-800/40 rounded-full">
            REAL-TIME MAPPING ACTIVE
          </span>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          The 3D factory engine synthesizes CCTV camera feeds, IoT sensor points, machine health indicators, and worker coordinates into a spatial digital twin.
        </p>
      </div>

      {/* Spatial Risk Matrix Cards */}
      <div>
        <h3 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
          <Eye className="w-3.5 h-3.5 text-cyan-400" />
          <span>Active Spatial Risk Detections ({risks.length})</span>
        </h3>

        {risks.length === 0 ? (
          <div className="glass-panel p-5 rounded-xl border border-slate-800 text-center text-xs text-slate-400 font-mono">
            ✓ Spatial terrain nominal. Zero localized risk vectors detected.
          </div>
        ) : (
          <div className="space-y-3">
            {risks.map((risk) => (
              <div
                key={risk.id}
                className="glass-panel p-4 rounded-xl border border-red-500/40 bg-red-950/20 space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getRiskIcon(risk.type)}
                    <span className="font-bold text-white text-xs">{risk.type}</span>
                  </div>
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-red-500/20 text-red-400 border border-red-500/40 rounded">
                    {risk.severity} • {Math.round(risk.probability * 100)}% CONFIDENCE
                  </span>
                </div>

                <div className="text-xs font-mono text-slate-300">
                  Sector: <span className="text-cyan-400 font-bold">{risk.zone}</span>
                </div>

                <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-900 text-xs font-mono space-y-1">
                  <span className="text-slate-500 block text-[10px]">CORROBORATING SENSOR EVIDENCE:</span>
                  {risk.contributing_factors.map((f, i) => (
                    <div key={i} className="text-slate-300 text-[11px]">
                      • {f}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sector Topology Overview */}
      <div className="flex-1">
        <h3 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-2.5">
          Sector Perimeter Health
        </h3>
        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          {zones.map((zone) => (
            <div
              key={zone.id}
              className={`p-3 rounded-xl border ${
                zone.status === 'ALERT'
                  ? 'bg-red-950/30 border-red-500/40 text-red-300'
                  : 'bg-slate-900/60 border-slate-800 text-slate-300'
              }`}
            >
              <div className="font-bold text-white text-xs mb-1">{zone.id}</div>
              <div className="text-[10px] text-slate-400 line-clamp-1">{zone.name}</div>
              <div className="mt-2 text-[10px] flex items-center justify-between">
                <span>Status:</span>
                <span className={zone.status === 'ALERT' ? 'text-red-400 font-bold animate-pulse' : 'text-emerald-400'}>
                  {zone.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

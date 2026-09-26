import React from 'react';
import { Camera } from '../../types';
import { Video, ShieldCheck, Eye } from 'lucide-react';

export const CamerasView: React.FC<{ cameras: Camera[] }> = ({ cameras }) => {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Video className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            INDUSTRIAL COMPUTER VISION & OPTICAL SENSOR FEEDS
          </h2>
        </div>
        <span className="px-3 py-1 bg-emerald-950/60 border border-emerald-800/40 text-emerald-400 rounded-full text-xs font-mono">
          4 OPTICAL STREAMS ONLINE
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cameras.map((camera) => (
          <div key={camera.id} className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2.5 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-white">{camera.name}</h4>
                <div className="text-xs text-slate-400">ID: {camera.id} • {camera.zone}</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                REC • 1080P
              </span>
            </div>

            {/* Simulated Video Canvas */}
            <div className="h-44 bg-slate-950 rounded-lg border border-slate-800/90 relative overflow-hidden flex items-center justify-center scanline-effect">
              {/* Fake Optical Grid / HUD Overlay */}
              <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px] opacity-40" />
              <div className="absolute top-2 left-2 text-[10px] text-cyan-400 flex items-center gap-1 font-mono bg-slate-900/80 px-2 py-0.5 rounded">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                <span>AI OBJECT CLASSIFICATION ACTIVE</span>
              </div>

              {/* Bounding box simulation */}
              <div className="border border-cyan-400/80 bg-cyan-500/10 rounded p-2 text-center text-xs text-cyan-200 font-mono shadow-glow-cyan">
                <Eye className="w-5 h-5 mx-auto mb-1 text-cyan-400" />
                <span>{camera.detected_objects.join(' • ')}</span>
              </div>

              <div className="absolute bottom-2 right-2 text-[10px] text-slate-400 font-mono bg-slate-900/80 px-2 py-0.5 rounded">
                FPS: 30.0 • LATENCY: 14ms
              </div>
            </div>

            <div className="text-xs text-slate-400">
              Latest Event: <span className="text-slate-200">{camera.last_event}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

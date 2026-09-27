import React from 'react';
import { Activity, Gauge, Cpu, Layers } from 'lucide-react';

interface PerformancePanelProps {
  fps: number;
  drawCalls: number;
  triangles: number;
  visibleObjects: number;
  cameraInferenceFps: number;
  wsRate: number;
  onClose?: () => void;
}

export const PerformancePanel: React.FC<PerformancePanelProps> = ({
  fps,
  drawCalls,
  triangles,
  visibleObjects,
  cameraInferenceFps,
  wsRate,
  onClose
}) => {
  return (
    <div className="absolute bottom-3 left-3 z-20 p-3 bg-slate-950/90 backdrop-blur-md rounded-xl border border-cyan-500/40 text-xs font-mono text-slate-200 w-64 shadow-2xl space-y-2 select-none">
      <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
        <div className="flex items-center gap-1.5 text-cyan-400 font-bold">
          <Activity className="w-4 h-4" />
          <span>DIGITAL TWIN PERFORMANCE</span>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xs">
            ✕
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
          <div className="text-slate-400 text-[10px]">MAIN VIEWPORT FPS</div>
          <div className={`font-bold text-sm ${fps >= 55 ? 'text-emerald-400' : fps >= 35 ? 'text-amber-400' : 'text-red-400'}`}>
            {fps.toFixed(1)} FPS
          </div>
        </div>

        <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
          <div className="text-slate-400 text-[10px]">CAMERA INFERENCE</div>
          <div className="font-bold text-sm text-cyan-300">{cameraInferenceFps.toFixed(1)} FPS</div>
        </div>

        <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
          <div className="text-slate-400 text-[10px]">DRAW CALLS</div>
          <div className="font-bold text-slate-200">{drawCalls} calls</div>
        </div>

        <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
          <div className="text-slate-400 text-[10px]">TRIANGLES</div>
          <div className="font-bold text-slate-200">{(triangles / 1000).toFixed(1)}k</div>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-800/80">
        <span>WS STREAM: <strong className="text-emerald-400">{wsRate} msg/s</strong></span>
        <span>OBJECTS: <strong className="text-cyan-400">{visibleObjects}</strong></span>
      </div>
    </div>
  );
};

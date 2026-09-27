import React from 'react';
import { Camera } from '../../types';
import { Video, Eye, AlertTriangle, ShieldCheck, Zap, Maximize2 } from 'lucide-react';
import { CameraPerceptionResult } from '../../services/cameraPerception';

interface CamerasViewProps {
  cameras: Camera[];
  perceptionResults?: Record<string, CameraPerceptionResult>;
  onSelectCameraView?: (camId: string) => void;
}

export const CamerasView: React.FC<CamerasViewProps> = ({ cameras, perceptionResults, onSelectCameraView }) => {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800 font-mono select-none">
      {/* Top Section Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Video className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            3D DIGITAL TWIN • VIRTUAL OPTICAL CAMERA FEEDS & COMPUTER VISION
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 rounded-lg text-xs font-bold flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            <span>VISION ENGINE: REAL-TIME 3D PERCEPTION</span>
          </span>
          <span className="px-3 py-1 bg-emerald-950/60 border border-emerald-800/40 text-emerald-400 rounded-lg text-xs">
            4 FEEDS ONLINE
          </span>
        </div>
      </div>

      {/* Grid of 4 Virtual Cameras */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cameras.map((camera) => {
          const perc = perceptionResults?.[camera.id];
          const hasHazard = perc?.hasSmokeFire || camera.detected_objects.some((o) => o.includes('FIRE') || o.includes('SMOKE') || o.includes('CRITICAL'));
          const boundingBoxes = perc?.boundingBoxes || [];

          return (
            <div
              key={camera.id}
              className={`p-3.5 rounded-xl bg-slate-900/90 border space-y-2.5 transition-all ${
                hasHazard ? 'border-red-500/80 shadow-glow-red' : 'border-slate-800 hover:border-slate-700'
              }`}
            >
              {/* Feed Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>{camera.name}</span>
                    <span className="text-xs font-normal text-slate-400">({camera.zone})</span>
                  </h4>
                  <div className="text-[11px] text-slate-400">CAMERA ID: {camera.id} • FOV: 55°</div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                    hasHazard
                      ? 'bg-red-500/20 text-red-400 border-red-500/40 animate-pulse'
                      : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                  }`}>
                    {hasHazard ? 'ALERT • HAZARD' : 'LIVE • 3D RENDER'}
                  </span>

                  {onSelectCameraView && (
                    <button
                      onClick={() => onSelectCameraView(camera.id)}
                      className="p-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700"
                      title="Switch 3D View to Camera POV"
                    >
                      <Maximize2 className="w-3.5 h-3.5 text-cyan-400" />
                    </button>
                  )}
                </div>
              </div>

              {/* 3D Camera Optics Render Frame */}
              <div className="h-48 bg-[#040811] rounded-lg border border-slate-800 relative overflow-hidden flex items-center justify-center scanline-effect group">
                {/* Background 3D Grid Blueprint Aesthetic */}
                <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:14px_14px] opacity-50" />

                {/* Live Top HUD Badge */}
                <div className="absolute top-2 left-2 z-10 text-[10px] text-cyan-300 flex items-center gap-1.5 bg-slate-950/80 backdrop-blur px-2 py-0.5 rounded border border-cyan-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                  <span>3D FRUSTUM VISION ACTIVE</span>
                </div>

                {/* Frame Timestamp */}
                <div className="absolute top-2 right-2 z-10 text-[10px] text-slate-400 bg-slate-950/80 backdrop-blur px-2 py-0.5 rounded border border-slate-800">
                  {perc?.timestamp || new Date().toLocaleTimeString()}
                </div>

                {/* 3D Object Detection Bounding Boxes Overlay */}
                {boundingBoxes.length > 0 ? (
                  boundingBoxes.map((box, bIdx) => (
                    <div
                      key={`box-${bIdx}`}
                      style={{
                        left: `${box.x}%`,
                        top: `${box.y}%`,
                        width: `${box.width}%`,
                        height: `${box.height}%`
                      }}
                      className={`absolute border-2 rounded p-1 transition-all ${
                        box.label.includes('FIRE') || box.label.includes('SMOKE')
                          ? 'border-red-500 bg-red-500/20 text-red-300 shadow-glow-red animate-pulse'
                          : box.label.includes('PERSON')
                          ? 'border-amber-400 bg-amber-500/10 text-amber-200'
                          : 'border-cyan-400 bg-cyan-500/10 text-cyan-200'
                      }`}
                    >
                      <div className="text-[9.5px] font-bold bg-slate-950/90 px-1 py-0.2 rounded inline-block -mt-3.5 -ml-1 border border-slate-700">
                        {box.label} ({(box.confidence * 100).toFixed(0)}%)
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-slate-500 text-xs">
                    <Eye className="w-6 h-6 mx-auto mb-1 text-slate-600 animate-pulse" />
                    <span>Sweeping Zone {camera.zone}...</span>
                  </div>
                )}

                {/* Bottom Frame Statistics */}
                <div className="absolute bottom-2 right-2 text-[10px] text-slate-400 bg-slate-950/80 px-2 py-0.5 rounded border border-slate-800 flex items-center gap-3">
                  <span>RES: 320x180</span>
                  <span>INFERENCE: 8.5 FPS</span>
                  <span>LATENCY: 12ms</span>
                </div>
              </div>

              {/* Detected Objects Summary */}
              <div className="text-xs text-slate-300 flex items-center justify-between pt-1">
                <span className="text-slate-400">Active Detections:</span>
                <span className="font-bold text-cyan-300">
                  {perc?.detectedObjects.length
                    ? perc.detectedObjects.join(' • ')
                    : camera.detected_objects.join(' • ')}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

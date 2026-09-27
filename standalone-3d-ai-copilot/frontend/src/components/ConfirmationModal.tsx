import React from 'react';
import { Action } from '../types';
import { AlertTriangle, CheckCircle2, XCircle, ShieldAlert, Cpu } from 'lucide-react';

interface ConfirmationModalProps {
  action: Action | null;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  action,
  onConfirm,
  onCancel,
  loading = false,
}) => {
  if (!action) return null;

  const isHighRisk = action.risk_level === 'HIGH';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-150">
      <div className={`w-full max-w-lg glass-panel p-6 rounded-2xl border shadow-2xl space-y-5 ${
        isHighRisk ? 'border-red-500/50 bg-slate-900/95' : 'border-amber-500/50 bg-slate-900/95'
      }`}>
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-xl ${isHighRisk ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'}`}>
            <AlertTriangle className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                isHighRisk ? 'bg-red-500/20 text-red-400 border border-red-500/40' : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
              }`}>
                {action.risk_level} RISK LEVEL
              </span>
              <span className="text-xs text-slate-400 font-mono">ID: {action.id}</span>
            </div>
            <h3 className="text-base font-bold text-white mt-1">
              HUMAN AUTHORIZATION REQUIRED
            </h3>
          </div>
        </div>

        {/* Action Details */}
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2.5 text-xs font-mono">
          <div>
            <span className="text-slate-500 block text-[10px] uppercase">RECOMMENDED ACTION:</span>
            <span className="text-sm font-bold text-cyan-400">
              {action.action_type.replace(/_/g, ' ')} → {action.target}
            </span>
          </div>

          <div>
            <span className="text-slate-500 block text-[10px] uppercase">OPERATIONAL REASON:</span>
            <span className="text-slate-200 leading-relaxed block">{action.reason}</span>
          </div>

          <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-slate-400">
            <span>TRIGGERED BY:</span>
            <span className="text-white font-bold">{action.created_by}</span>
          </div>
        </div>

        {/* Warning Callout */}
        <div className="p-3 bg-red-950/30 border border-red-900/50 rounded-lg text-xs text-red-200 leading-relaxed">
          ⚠️ <strong>Plant Director Notice:</strong> Executing this command will transmit an electrical trigger to industrial actuator field controllers. Verify safety perimeter before confirming.
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`flex-1 py-3 px-4 rounded-xl text-xs font-bold text-white transition-all shadow-lg flex items-center justify-center gap-2 ${
              isHighRisk
                ? 'bg-red-600 hover:bg-red-500 shadow-glow-red'
                : 'bg-emerald-600 hover:bg-emerald-500'
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>{loading ? 'TRANSMITTING COMMAND...' : 'AUTHORIZE IOT EXECUTION'}</span>
          </button>
          <button
            onClick={onCancel}
            disabled={loading}
            className="py-3 px-5 rounded-xl text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition-all border border-slate-700"
          >
            CANCEL
          </button>
        </div>
      </div>
    </div>
  );
};

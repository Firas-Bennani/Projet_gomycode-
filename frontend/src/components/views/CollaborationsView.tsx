import React from 'react';
import { CollaborationItem } from '../../types';
import { Handshake, Globe2, Building } from 'lucide-react';

export const CollaborationsView: React.FC<{ items: CollaborationItem[] }> = ({ items }) => {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Handshake className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            STRATEGIC INDUSTRIAL COLLABORATIONS & SUPPLIERS
          </h2>
        </div>
        <span className="px-3 py-1 bg-slate-900 border border-slate-800 text-slate-300 rounded-full text-xs font-mono">
          {items.length} PARTNERSHIPS
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {items.map((col) => (
          <div key={col.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5 font-mono">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white">{col.partner_name}</h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">
                {col.type}
              </span>
            </div>
            <div className="text-xs text-slate-400">Point of Contact: {col.contact}</div>
            <div className="p-2.5 bg-slate-950/80 rounded border border-slate-900 text-xs text-slate-300 leading-relaxed">
              {col.notes}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

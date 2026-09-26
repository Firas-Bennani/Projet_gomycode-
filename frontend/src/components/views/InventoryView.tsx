import React from 'react';
import { InventoryItem } from '../../types';
import { Package, AlertTriangle, TrendingDown } from 'lucide-react';

export const InventoryView: React.FC<{ items: InventoryItem[] }> = ({ items }) => {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Package className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            COMMODITIES & INVENTORY TELEMETRY
          </h2>
        </div>
        <span className="px-3 py-1 bg-slate-900 border border-slate-800 text-slate-300 rounded-full text-xs font-mono">
          {items.length} TRACKED ASSETS
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((item) => (
          <div key={item.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-white">{item.name}</h4>
                <div className="text-xs text-slate-400">ID: {item.id} • Category: {item.category}</div>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                item.status === 'LOW' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' : 'bg-emerald-500/20 text-emerald-400'
              }`}>
                {item.status} STOCK
              </span>
            </div>

            <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-900 flex items-center justify-between">
              <div>
                <span className="text-[10px] text-slate-500 block">CURRENT QUANTITY</span>
                <span className="text-lg font-bold text-cyan-400">{item.quantity} {item.unit}</span>
              </div>
              <div className="text-right">
                <span className="text-[10px] text-slate-500 block">MINIMUM THRESHOLD</span>
                <span className="text-sm text-slate-300">{item.low_stock_threshold} {item.unit}</span>
              </div>
            </div>

            <div className="text-xs text-slate-400 flex items-center gap-1.5">
              <TrendingDown className="w-3.5 h-3.5 text-slate-500" />
              <span>Burn Rate: <strong className="text-slate-200">{item.consumption_rate}</strong></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

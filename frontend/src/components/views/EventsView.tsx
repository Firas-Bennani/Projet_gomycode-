import React from 'react';
import { IndustrialEvent } from '../../types';
import { Calendar, Wrench, ShieldCheck, Clock } from 'lucide-react';

export const EventsView: React.FC<{ events: IndustrialEvent[] }> = ({ events }) => {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Calendar className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            INDUSTRIAL MAINTENANCE & INTERVENTION SCHEDULE
          </h2>
        </div>
        <span className="px-3 py-1 bg-slate-900 border border-slate-800 text-slate-300 rounded-full text-xs font-mono">
          {events.length} UPCOMING OPERATIONS
        </span>
      </div>

      <div className="space-y-3 font-mono">
        {events.map((evt) => (
          <div key={evt.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800/40">
                  {evt.type}
                </span>
                <h4 className="text-sm font-bold text-white">{evt.title}</h4>
              </div>
              <div className="text-xs text-slate-400">
                Scheduled: {evt.scheduled_at} • Target: {evt.machine_id || evt.zone_id || 'Plant-Wide'}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-slate-800 text-slate-300">
                {evt.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

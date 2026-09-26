import React from 'react';
import {
  Cuboid as Cube, Users, Package, Video, Terminal, AlertOctagon,
  Briefcase, Handshake, Calendar, Activity, ChevronRight
} from 'lucide-react';

interface SidebarProps {
  currentSection: string;
  onSelectSection: (section: string) => void;
  activeIncidentsCount: number;
  pendingActionsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentSection,
  onSelectSection,
  activeIncidentsCount,
  pendingActionsCount,
}) => {
  const navItems = [
    { id: 'overview', label: '3D Digital Twin', icon: Cube, highlight: true },
    { id: 'workers', label: '1. Workers', icon: Users },
    { id: 'inventory', label: '2. Commodities / Inventory', icon: Package },
    { id: 'cameras', label: '3. Cameras', icon: Video },
    { id: 'command-center', label: '4. Command Center', icon: Terminal, badge: pendingActionsCount, badgeColor: 'bg-amber-500' },
    { id: 'detections', label: '5. Detections', icon: AlertOctagon, badge: activeIncidentsCount, badgeColor: 'bg-red-500' },
    { id: 'clients', label: '6. Clients', icon: Briefcase },
    { id: 'collaborations', label: '7. Collaborations', icon: Handshake },
    { id: 'events', label: '8. Plans / Events', icon: Calendar },
    { id: 'machines', label: '9. Machine Parameters', icon: Activity },
  ];

  return (
    <aside className="w-64 glass-panel border-r border-slate-800 flex flex-col justify-between py-4 select-none">
      <div className="space-y-1 px-3">
        <div className="px-3 pb-2 text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">
          NAVIGATION CONTROL
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentSection === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onSelectSection(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono transition-all ${
                isActive
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-glow-cyan font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <div className="flex items-center gap-2.5 truncate">
                <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                <span className="truncate">{item.label}</span>
              </div>

              {item.badge !== undefined && item.badge > 0 && (
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold text-slate-950 ${item.badgeColor} animate-pulse`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Industrial Sentinel Status Footer */}
      <div className="px-4 pt-3 border-t border-slate-800/80 text-[10px] font-mono text-slate-500 space-y-1">
        <div className="flex items-center justify-between">
          <span>EDGE FIELD ENGINE:</span>
          <span className="text-emerald-400 font-bold">ONLINE</span>
        </div>
        <div className="flex items-center justify-between">
          <span>MQTT INGESTION:</span>
          <span className="text-cyan-400">1883 / 9001</span>
        </div>
      </div>
    </aside>
  );
};

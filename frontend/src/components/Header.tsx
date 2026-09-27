import React, { useState, useEffect } from 'react';
import { Cpu, ShieldCheck, Bell, Activity, User, Moon, Sun, LogOut } from 'lucide-react';
import { getUser, logout } from '../services/auth';

interface HeaderProps {
  activeAlertCount: number;
}

export const Header: React.FC<HeaderProps> = ({ activeAlertCount }) => {
  const [time, setTime] = useState(new Date().toLocaleTimeString());
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(timer);
  }, []);

  const toggleTheme = () => {
    document.documentElement.classList.toggle('dark');
    setIsDark(document.documentElement.classList.contains('dark'));
  };

  return (
    <header className="h-16 px-6 glass-panel border-b border-slate-200 dark:border-slate-800 flex items-center justify-between z-30 select-none bg-white/80 dark:bg-[#080d1a]/80 backdrop-blur-md">
      {/* Brand & Identity */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-glow-cyan">
          <Cpu className="w-5 h-5 text-slate-950 font-bold" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-extrabold text-white tracking-wider font-mono">
              Industrial_Copilot
            </h1>
            <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded">
              v1.0 MVP
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            Autonomous Plant Sentinel & Tactical Decision Mesh
          </span>
        </div>
      </div>

      {/* Signed-in user (real session, not a placeholder) + sign out */}
      <div className="hidden md:flex items-center gap-3">
        <div className="flex items-center gap-2 px-4 py-1.5 bg-slate-900/80 rounded-full border border-slate-800 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          <span className="text-slate-400">Welcome,</span>
          <strong className="text-white">
            {getUser()?.display_name || getUser()?.username || 'operator'}
          </strong>
          <span className="text-slate-500">
            ({getUser()?.job_title || getUser()?.role})
          </span>
          <span className={`ml-1 px-1.5 py-0.5 rounded text-[9px] font-bold border ${
            getUser()?.role === 'owner'
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
              : 'bg-slate-700/40 text-slate-300 border-slate-600/40'}`}>
            {getUser()?.role === 'owner' ? 'CAN AUTHORIZE' : 'READ-ONLY'}
          </span>
        </div>
        <button
          onClick={() => logout('You signed out.')}
          title="Sign out"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-slate-800 bg-slate-900/80 text-[11px] font-mono text-slate-300 hover:text-white hover:border-cyan-600/50 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          SIGN OUT
        </button>
      </div>

      {/* Right Telemetry Status & Clock */}
      <div className="flex items-center gap-4 text-xs font-mono">
        <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-slate-900/60 rounded border border-slate-800 text-slate-300">
          <Activity className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span>SENSE → REASON → ACT</span>
        </div>

        <div className="flex items-center gap-2">
          {activeAlertCount > 0 ? (
            <div className="flex items-center gap-1.5 px-3 py-1 bg-red-600/20 border border-red-500/50 text-red-400 rounded-full font-bold shadow-glow-red animate-pulse">
              <Bell className="w-3.5 h-3.5" />
              <span>{activeAlertCount} CRITICAL ALERT{activeAlertCount > 1 ? 'S' : ''}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-full">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>PLANT SECURE</span>
            </div>
          )}
        </div>

        <div className="text-slate-400 border-l border-slate-800 pl-3">
          {time}
        </div>
        <button
          onClick={toggleTheme}
          className="ml-2 p-1.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
          title="Toggle Light/Dark Mode"
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};

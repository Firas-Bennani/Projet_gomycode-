import React, { useState } from 'react';
import { ClientItem } from '../../types';
import { Briefcase, TrendingUp, Sparkles, Plus, X } from 'lucide-react';

export const ClientsView: React.FC<{ clients: ClientItem[] }> = ({ clients: initialClients }) => {
  const [clients, setClients] = useState(initialClients);
  const [isAdding, setIsAdding] = useState(false);
  const [newClient, setNewClient] = useState({ name: '', industry: '', contact_email: '' });

  const handleAddClient = (e: React.FormEvent) => {
    e.preventDefault();
    const id = `CLI-${Math.floor(Math.random() * 1000)}`;
    setClients([...clients, { 
      id, 
      name: newClient.name, 
      industry: newClient.industry, 
      contact_email: newClient.contact_email,
      status: 'PROSPECT',
      orders_count: 0
    }]);
    setNewClient({ name: '', industry: '', contact_email: '' });
    setIsAdding(false);
  };

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Briefcase className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            CLIENT PORTFOLIO & COMMERCIAL OPPORTUNITIES
          </h2>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={() => setIsAdding(!isAdding)}
            className="flex items-center gap-1 px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded-md text-xs font-bold transition-colors"
          >
            {isAdding ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            {isAdding ? 'CANCEL' : 'ADD CLIENT'}
          </button>
          <span className="px-3 py-1 bg-slate-900 border border-slate-800 text-slate-300 rounded-full text-xs font-mono">
            {clients.length} INDUSTRIAL ACCOUNTS
          </span>
        </div>
      </div>

      {isAdding && (
        <form onSubmit={handleAddClient} className="p-4 bg-slate-800/40 border border-slate-700 rounded-lg flex gap-3 items-end">
          <div className="flex-1 space-y-1">
            <label className="text-[10px] text-slate-400 font-mono">COMPANY NAME</label>
            <input required type="text" value={newClient.name} onChange={e => setNewClient({...newClient, name: e.target.value})} className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-sm text-white focus:border-cyan-500 outline-none" placeholder="e.g. Acme Corp" />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-[10px] text-slate-400 font-mono">INDUSTRY</label>
            <input required type="text" value={newClient.industry} onChange={e => setNewClient({...newClient, industry: e.target.value})} className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-sm text-white focus:border-cyan-500 outline-none" placeholder="e.g. Aerospace" />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-[10px] text-slate-400 font-mono">CONTACT EMAIL</label>
            <input required type="email" value={newClient.contact_email} onChange={e => setNewClient({...newClient, contact_email: e.target.value})} className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-sm text-white focus:border-cyan-500 outline-none" placeholder="contact@acme.com" />
          </div>
          <button type="submit" className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm rounded">Save</button>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {clients.map((c) => (
          <div key={c.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">{c.name}</h3>
                <div className="text-xs text-slate-400">Industry: {c.industry}</div>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                c.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-cyan-500/20 text-cyan-400'
              }`}>
                {c.status}
              </span>
            </div>

            <div className="text-xs text-slate-300">
              Orders Completed: <strong className="text-white">{c.orders_count}</strong> • Contact: {c.contact_email}
            </div>

            {c.ai_recommendations && (
              <div className="p-3 bg-cyan-950/40 rounded-lg border border-cyan-800/40 text-xs">
                <span className="text-cyan-400 font-bold flex items-center gap-1 mb-1">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>AI COMMERCIAL COPILOT RECOMMENDATION:</span>
                </span>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {c.ai_recommendations}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

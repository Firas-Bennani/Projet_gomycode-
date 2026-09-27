import React, { useState } from 'react';
import { CollaborationItem } from '../../types';
import { Handshake, Globe2, Building, Plus, X } from 'lucide-react';

export const CollaborationsView: React.FC<{ items: CollaborationItem[] }> = ({ items: initialItems }) => {
  const [items, setItems] = useState(initialItems);
  const [isAdding, setIsAdding] = useState(false);
  const [newPartner, setNewPartner] = useState({ partner_name: '', type: 'SUPPLIER', contact: '', notes: '' });

  const handleAddPartner = (e: React.FormEvent) => {
    e.preventDefault();
    const id = `COL-${Math.floor(Math.random() * 1000)}`;
    setItems([...items, { 
      id, 
      partner_name: newPartner.partner_name, 
      type: newPartner.type as any, 
      contact: newPartner.contact,
      notes: newPartner.notes,
      active_since: new Date().toISOString().split('T')[0]
    }]);
    setNewPartner({ partner_name: '', type: 'SUPPLIER', contact: '', notes: '' });
    setIsAdding(false);
  };

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto p-4 glass-panel rounded-xl border border-slate-800">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Handshake className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide uppercase">
            STRATEGIC INDUSTRIAL COLLABORATIONS & SUPPLIERS
          </h2>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={() => setIsAdding(!isAdding)}
            className="flex items-center gap-1 px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded-md text-xs font-bold transition-colors"
          >
            {isAdding ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            {isAdding ? 'CANCEL' : 'ADD PARTNER'}
          </button>
          <span className="px-3 py-1 bg-slate-900 border border-slate-800 text-slate-300 rounded-full text-xs font-mono">
            {items.length} PARTNERSHIPS
          </span>
        </div>
      </div>

      {isAdding && (
        <form onSubmit={handleAddPartner} className="p-4 bg-slate-800/40 border border-slate-700 rounded-lg flex flex-col gap-3">
          <div className="flex gap-3 items-end">
            <div className="flex-1 space-y-1">
              <label className="text-[10px] text-slate-400 font-mono">PARTNER NAME</label>
              <input required type="text" value={newPartner.partner_name} onChange={e => setNewPartner({...newPartner, partner_name: e.target.value})} className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-sm text-white focus:border-cyan-500 outline-none" placeholder="e.g. Global Tech" />
            </div>
            <div className="flex-1 space-y-1">
              <label className="text-[10px] text-slate-400 font-mono">TYPE</label>
              <select value={newPartner.type} onChange={e => setNewPartner({...newPartner, type: e.target.value})} className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-sm text-white focus:border-cyan-500 outline-none">
                <option value="SUPPLIER">SUPPLIER</option>
                <option value="RESEARCH">RESEARCH</option>
                <option value="INTEGRATOR">INTEGRATOR</option>
              </select>
            </div>
            <div className="flex-1 space-y-1">
              <label className="text-[10px] text-slate-400 font-mono">CONTACT EMAIL</label>
              <input required type="email" value={newPartner.contact} onChange={e => setNewPartner({...newPartner, contact: e.target.value})} className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-sm text-white focus:border-cyan-500 outline-none" placeholder="contact@globaltech.com" />
            </div>
          </div>
          <div className="flex gap-3 items-end">
             <div className="flex-1 space-y-1">
              <label className="text-[10px] text-slate-400 font-mono">NOTES</label>
              <input type="text" value={newPartner.notes} onChange={e => setNewPartner({...newPartner, notes: e.target.value})} className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-sm text-white focus:border-cyan-500 outline-none" placeholder="Collaboration details..." />
            </div>
            <button type="submit" className="px-6 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm rounded">Save</button>
          </div>
        </form>
      )}

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

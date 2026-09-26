import React, { useState } from 'react';
import { AgentStatus, AgentLogEntry } from '../../types';
import {
  Thermometer, UserCheck, Activity, ShieldAlert, BrainCircuit,
  ArrowRight, Search, BookOpen, Clock, CheckCircle2
} from 'lucide-react';
import { api } from '../../services/api';

interface MultiAgentViewProps {
  agents: AgentStatus[];
  logs: AgentLogEntry[];
}

export const MultiAgentView: React.FC<MultiAgentViewProps> = ({ agents, logs }) => {
  const [ragQuery, setRagQuery] = useState('');
  const [ragResult, setRagResult] = useState<any>(null);
  const [loadingRag, setLoadingRag] = useState(false);

  const getAgentIcon = (id: string) => {
    switch (id) {
      case 'temperature_agent': return <Thermometer className="w-4 h-4 text-cyan-400" />;
      case 'machine_agent': return <Activity className="w-4 h-4 text-sky-400" />;
      case 'worker_agent': return <UserCheck className="w-4 h-4 text-amber-400" />;
      case 'cyber_agent': return <ShieldAlert className="w-4 h-4 text-purple-400" />;
      case 'recommendation_agent': return <BrainCircuit className="w-4 h-4 text-emerald-400" />;
      default: return <BrainCircuit className="w-4 h-4 text-cyan-400" />;
    }
  };

  const handleSearchRag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragQuery.trim()) return;
    setLoadingRag(true);
    try {
      const res = await api.queryRAG(ragQuery);
      setRagResult(res);
    } catch (err) {
      console.error('RAG query error:', err);
    } finally {
      setLoadingRag(false);
    }
  };

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto pr-1">
      {/* Header Banner */}
      <div className="glass-panel p-4 rounded-xl border border-cyan-500/20">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-cyan-400" />
            <h2 className="text-sm font-bold text-white tracking-wide uppercase">
              SYSTEM 1 — MULTI-AGENT INDUSTRIAL INTELLIGENCE
            </h2>
          </div>
          <span className="px-2 py-0.5 text-[11px] font-mono bg-cyan-950/60 text-cyan-400 border border-cyan-800/40 rounded-full">
            5/5 AGENTS ACTIVE
          </span>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Decentralized reasoning mesh: specialized agents continuously analyze environmental, mechanical, worker, and cyber signals to formulate joint incident hypotheses.
        </p>
      </div>

      {/* Inter-Agent Collaboration Flow Visualizer */}
      <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
        <div className="text-[11px] font-mono text-slate-400 mb-2 uppercase tracking-wider flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          <span>Active Multi-Agent Synthesis Pipeline</span>
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono bg-slate-950/60 p-2.5 rounded-lg border border-slate-900 overflow-x-auto gap-2">
          <div className="flex flex-col items-center text-center p-1.5 bg-slate-900 rounded border border-cyan-900/50">
            <Thermometer className="w-3.5 h-3.5 text-cyan-400 mb-1" />
            <span className="text-slate-200">Thermal</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
          <div className="flex flex-col items-center text-center p-1.5 bg-slate-900 rounded border border-sky-900/50">
            <Activity className="w-3.5 h-3.5 text-sky-400 mb-1" />
            <span className="text-slate-200">Machine</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
          <div className="flex flex-col items-center text-center p-1.5 bg-slate-900 rounded border border-amber-900/50">
            <UserCheck className="w-3.5 h-3.5 text-amber-400 mb-1" />
            <span className="text-slate-200">Safety</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
          <div className="flex flex-col items-center text-center p-1.5 bg-emerald-950/60 rounded border border-emerald-500/40 text-emerald-400 font-bold">
            <BrainCircuit className="w-3.5 h-3.5 mb-1" />
            <span>Strategic</span>
          </div>
        </div>
      </div>

      {/* Agents Cards */}
      <div className="space-y-3">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className={`glass-panel p-3.5 rounded-xl border transition-all ${
              agent.status === 'WARNING'
                ? 'border-amber-500/40 bg-amber-950/10'
                : 'border-slate-800/80 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-slate-900/90 rounded-lg border border-slate-800">
                  {getAgentIcon(agent.id)}
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-slate-100">{agent.name}</h4>
                  <span className="text-[10px] text-slate-500 font-mono">ID: {agent.id}</span>
                </div>
              </div>
              <span
                className={`px-2 py-0.5 text-[10px] font-mono rounded-full font-bold ${
                  agent.status === 'WARNING'
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                }`}
              >
                {agent.status}
              </span>
            </div>

            <div className="space-y-1.5 text-[11px] font-mono">
              <div className="bg-slate-950/60 p-2 rounded border border-slate-900/80">
                <span className="text-slate-500 block text-[10px]">LATEST OBSERVATION:</span>
                <span className="text-slate-300">{agent.latest_observation}</span>
              </div>
              <div className="bg-slate-950/40 p-2 rounded border border-slate-900/60">
                <span className="text-cyan-500 block text-[10px]">DECISION / ACTION:</span>
                <span className="text-slate-200">{agent.latest_decision}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Controlled RAG Query Widget */}
      <div className="glass-panel p-3.5 rounded-xl border border-cyan-500/30">
        <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-400 uppercase tracking-wide mb-2">
          <BookOpen className="w-3.5 h-3.5" />
          <span>RAG KNOWLEDGE LAYER (SOP & MANUALS)</span>
        </div>
        <form onSubmit={handleSearchRag} className="flex gap-2 mb-2">
          <input
            type="text"
            value={ragQuery}
            onChange={(e) => setRagQuery(e.target.value)}
            placeholder="Search procedures (e.g. EP-07 overheating, fire)..."
            className="flex-1 bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
          />
          <button
            type="submit"
            disabled={loadingRag}
            className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
          >
            <Search className="w-3.5 h-3.5" />
            <span>Query</span>
          </button>
        </form>

        {ragResult && (
          <div className="mt-3 p-3 bg-slate-950/90 rounded-lg border border-slate-800 text-xs space-y-2">
            <div className="text-slate-300 text-[11px] leading-relaxed whitespace-pre-line">
              {ragResult.answer}
            </div>
            {ragResult.sources && (
              <div className="pt-2 border-t border-slate-800 flex flex-wrap gap-1.5 text-[10px] font-mono text-cyan-400">
                <span className="text-slate-500">Cited:</span>
                {ragResult.sources.map((s: any, idx: number) => (
                  <span key={idx} className="bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                    {s.document} (score: {s.relevance})
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Real-time Agent Chatter Stream */}
      <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wide mb-2 flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>Inter-Agent Communication Log</span>
        </h3>
        <div className="space-y-2 max-h-48 overflow-y-auto pr-1 text-[11px] font-mono">
          {logs.slice(0, 10).map((log, idx) => (
            <div key={idx} className="p-2 rounded bg-slate-950/60 border border-slate-900">
              <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                <span className="text-cyan-400 font-bold">{log.agent_id}</span>
                <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
              </div>
              <p className="text-slate-300 leading-snug">{log.reasoning}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

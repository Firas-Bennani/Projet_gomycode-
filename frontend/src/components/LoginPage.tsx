import React, { useEffect, useState } from 'react';
import { Cpu, Lock, User, AlertTriangle, Loader2 } from 'lucide-react';
import { login, takeSignOutReason } from '../services/auth';

/**
 * Sign-in gate for Industrial_Copilot. Same dark navy / cyan language as the dashboard.
 * No credentials are embedded here — the demo accounts are documented in docs/ai/DEMO.md.
 */
export const LoginPage: React.FC<{ onSignedIn: () => void }> = ({ onSignedIn }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setNotice(takeSignOutReason());
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      onSignedIn();
    } catch (err: any) {
      setError(err?.message || 'Sign-in failed');
      setPassword('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#050914] text-slate-100 font-sans overflow-hidden">
      {/* backdrop */}
      <div className="absolute inset-0 opacity-30 pointer-events-none"
           style={{ backgroundImage:
             'radial-gradient(circle at 25% 20%, rgba(6,182,212,0.18), transparent 45%), radial-gradient(circle at 75% 80%, rgba(14,116,144,0.16), transparent 45%)' }} />

      <form onSubmit={submit}
            className="relative w-[380px] glass-panel rounded-2xl border border-slate-800 bg-slate-950/70 p-8 shadow-2xl">
        <div className="flex flex-col items-center gap-2 mb-7">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30">
            <Cpu className="w-7 h-7 text-cyan-400" />
          </div>
          <h1 className="text-lg font-extrabold tracking-wider font-mono text-white">
            Industrial_Copilot
          </h1>
          <p className="text-[11px] text-slate-400 font-mono tracking-wide">
            SENSE → REASON → ACT
          </p>
        </div>

        {notice && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-600/40 bg-amber-950/30 px-3 py-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <span className="text-[11px] text-amber-200 leading-snug">{notice}</span>
          </div>
        )}

        <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1.5">
          Operator ID
        </label>
        <div className="relative mb-4">
          <User className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
            className="w-full bg-slate-900/80 border border-slate-700 focus:border-cyan-500 focus:outline-none rounded-lg pl-9 pr-3 py-2.5 text-sm font-mono text-slate-100 placeholder-slate-600"
            placeholder="operator id"
          />
        </div>

        <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1.5">
          Passphrase
        </label>
        <div className="relative mb-5">
          <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="w-full bg-slate-900/80 border border-slate-700 focus:border-cyan-500 focus:outline-none rounded-lg pl-9 pr-3 py-2.5 text-sm font-mono text-slate-100 placeholder-slate-600"
            placeholder="••••••••"
          />
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-600/40 bg-red-950/30 px-3 py-2 text-[11px] text-red-300 font-mono">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy || !username || !password}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-sm font-bold font-mono tracking-wide py-2.5 transition-colors"
        >
          {busy ? <><Loader2 className="w-4 h-4 animate-spin" /> SIGNING IN…</> : 'SIGN IN'}
        </button>

        <p className="mt-5 text-center text-[10px] text-slate-600 font-mono leading-relaxed">
          Authorised personnel only. Sessions end after 30 minutes<br />of inactivity or on token expiry.
        </p>
      </form>
    </div>
  );
};

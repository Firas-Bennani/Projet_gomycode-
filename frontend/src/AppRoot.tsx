import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { App } from './App';
import { LoginPage } from './components/LoginPage';
import {
  INACTIVITY_LIMIT_MS, WARNING_BEFORE_MS,
  isAuthenticated, logout, onAuthChange, secondsUntilExpiry,
} from './services/auth';

/**
 * Route guard for Industrial_Copilot.
 *
 * The dashboard is only mounted once signed in, so no authenticated-only request is ever fired
 * from a logged-out page. Two independent sign-out triggers, whichever fires first:
 *   - the server-issued token expiring (30 minutes)
 *   - 30 minutes without a mouse, key, click or scroll event
 * A banner appears one minute before either.
 */
export default function AppRoot() {
  const [authed, setAuthed] = useState(isAuthenticated());
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const lastActivity = useRef(Date.now());

  // Re-render whenever the session is established or dropped anywhere in the app.
  useEffect(() => onAuthChange(() => setAuthed(isAuthenticated())), []);

  const markActivity = useCallback(() => {
    lastActivity.current = Date.now();
  }, []);

  useEffect(() => {
    if (!authed) return;
    const events = ['mousemove', 'mousedown', 'keydown', 'wheel', 'touchstart', 'scroll'];
    events.forEach((e) => window.addEventListener(e, markActivity, { passive: true }));
    return () => events.forEach((e) => window.removeEventListener(e, markActivity));
  }, [authed, markActivity]);

  useEffect(() => {
    if (!authed) {
      setSecondsLeft(null);
      return;
    }
    const tick = setInterval(() => {
      const idleMs = Date.now() - lastActivity.current;
      const idleRemaining = Math.floor((INACTIVITY_LIMIT_MS - idleMs) / 1000);
      const tokenRemaining = secondsUntilExpiry();
      const remaining = Math.min(idleRemaining, tokenRemaining);

      if (remaining <= 0) {
        logout(
          tokenRemaining <= 0
            ? 'Your 30-minute session expired. Please sign in again.'
            : 'Signed out after 30 minutes of inactivity.',
        );
        return;
      }
      setSecondsLeft(remaining <= WARNING_BEFORE_MS / 1000 ? remaining : null);
    }, 1000);
    return () => clearInterval(tick);
  }, [authed]);

  if (!authed) {
    return <LoginPage onSignedIn={() => setAuthed(true)} />;
  }

  return (
    <>
      {secondsLeft !== null && (
        <div className="fixed top-2 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-3 rounded-lg border border-amber-500/50 bg-amber-950/90 px-4 py-2 shadow-xl backdrop-blur">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span className="text-[12px] font-mono text-amber-100">
            Session ends in <strong className="text-amber-300">{secondsLeft}s</strong> — move the
            mouse to stay signed in
          </span>
          <button
            onClick={() => { lastActivity.current = Date.now(); setSecondsLeft(null); }}
            className="text-[11px] font-mono font-bold text-amber-300 hover:text-white border border-amber-500/40 rounded px-2 py-0.5"
          >
            STAY
          </button>
        </div>
      )}
      <App />
    </>
  );
}

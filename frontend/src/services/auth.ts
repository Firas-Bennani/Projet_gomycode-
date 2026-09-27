/**
 * Authentication for Industrial_Copilot.
 *
 * The token lives in sessionStorage, so it dies with the tab and is never written to disk.
 * Two independent sign-out triggers, both required by the brief:
 *   - token expiry (30 minutes, decided by the server, read from the token payload)
 *   - 30 minutes of no user activity
 * whichever comes first, with a visible warning one minute before.
 */

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'copilot.token';
const USER_KEY = 'copilot.user';

export const INACTIVITY_LIMIT_MS = 30 * 60 * 1000;
export const WARNING_BEFORE_MS = 60 * 1000;

export interface AuthUser {
  username: string;
  role: 'owner' | 'operator' | string;
  display_name?: string;
  job_title?: string;
  expires_at: number; // unix seconds
  permissions?: { can_authorize_actions?: boolean; can_edit_records?: boolean };
}

let listeners: Array<() => void> = [];
export const onAuthChange = (fn: () => void) => {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
};
const notify = () => listeners.forEach((l) => l());

export const getToken = (): string | null => sessionStorage.getItem(TOKEN_KEY);

export const getUser = (): AuthUser | null => {
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
};

/** Seconds until the server-issued token expires. 0 once it has. */
export const secondsUntilExpiry = (): number => {
  const user = getUser();
  if (!user?.expires_at) return 0;
  return Math.max(0, user.expires_at - Math.floor(Date.now() / 1000));
};

export const isAuthenticated = (): boolean => !!getToken() && secondsUntilExpiry() > 0;

export const canAuthorizeActions = (): boolean => !!getUser()?.permissions?.can_authorize_actions;

export async function login(username: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    // The server deliberately returns the same message for unknown user and wrong password.
    const detail = await res.json().catch(() => ({ detail: 'Sign-in failed' }));
    throw new Error(detail.detail || 'Sign-in failed');
  }
  const data = await res.json();
  sessionStorage.setItem(TOKEN_KEY, data.token);
  const user: AuthUser = {
    username: data.username,
    role: data.role,
    display_name: data.display_name,
    job_title: data.job_title,
    expires_at: data.expires_at,
    permissions: data.permissions,
  };
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  notify();
  return user;
}

/** Clear local session. Tells the server too, but does not depend on it answering. */
export async function logout(reason?: string): Promise<void> {
  const token = getToken();
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  if (reason) sessionStorage.setItem('copilot.signOutReason', reason);
  notify();
  if (token) {
    try {
      await fetch(`${API_URL}/api/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      /* the local session is already gone; the token expires on its own */
    }
  }
}

export const takeSignOutReason = (): string | null => {
  const reason = sessionStorage.getItem('copilot.signOutReason');
  if (reason) sessionStorage.removeItem('copilot.signOutReason');
  return reason;
};

export const authHeader = (): Record<string, string> => {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

/** Any 401 from anywhere means the session is over: drop it and let the guard show the login. */
export const handleUnauthorized = () => {
  if (getToken()) logout('Your session ended. Please sign in again.');
};

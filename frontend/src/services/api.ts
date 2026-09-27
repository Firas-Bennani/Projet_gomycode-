import { authHeader, handleUnauthorized } from './auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${url}`, {
    ...options,
    // Every call carries the session token; any 401 ends the session and returns to the login.
    headers: { 'Content-Type': 'application/json', ...authHeader(), ...(options?.headers || {}) },
  });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error('Not authenticated');
  }
  if (res.status === 403) {
    const body = await res.json().catch(() => ({ detail: 'Not permitted' }));
    throw new Error(body.detail || 'Not permitted for your role');
  }
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  // Sensors
  getSensors: () => fetchJson<{ sensors: any[] }>('/api/sensors'),
  getSensorReadings: (id: string) => fetchJson<{ readings: any[] }>(`/api/sensors/${id}/readings`),

  // Machines
  getMachines: () => fetchJson<{ machines: any[] }>('/api/machines'),
  getMachine: (id: string) => fetchJson<any>(`/api/machines/${id}`),

  // Workers
  getWorkers: () => fetchJson<{ workers: any[] }>('/api/workers'),

  // Incidents
  getIncidents: () => fetchJson<{ incidents: any[] }>('/api/incidents'),
  updateIncidentStatus: (id: string, status: string) =>
    fetchJson<any>(`/api/incidents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    }),

  // Actions
  getActions: () => fetchJson<{ actions: any[] }>('/api/actions'),
  authorizeAction: (id: string, comment?: string) =>
    fetchJson<any>(`/api/actions/${id}/authorize`, {
      method: 'POST',
      body: JSON.stringify({ authorized_by: 'owner_01', comment })
    }),
  cancelAction: (id: string, reason?: string) =>
    fetchJson<any>(`/api/actions/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ cancelled_by: 'owner_01', reason })
    }),

  // AI & RAG
  getAgents: () => fetchJson<{ agents: any[] }>('/api/ai/agents'),
  getAgentLogs: () => fetchJson<{ logs: any[] }>('/api/ai/logs'),
  queryRAG: (query: string, context?: any) =>
    fetchJson<any>('/api/ai/rag/query', {
      method: 'POST',
      body: JSON.stringify({ query, context })
    }),

  // Digital Twin
  getDigitalTwinState: () => fetchJson<any>('/api/digital-twin/state'),

  // Plant Operations
  getInventory: () => fetchJson<{ inventory: any[] }>('/api/inventory'),
  getClients: () => fetchJson<{ clients: any[] }>('/api/clients'),
  getCollaborations: () => fetchJson<{ collaborations: any[] }>('/api/collaborations'),
  getEvents: () => fetchJson<{ events: any[] }>('/api/events'),
  getCameras: () => fetchJson<{ cameras: any[] }>('/api/cameras'),
  getRisks: () => fetchJson<{ risks: any[] }>('/api/risks'),

  // Demo Controls
  triggerScenario: (scenario: string) =>
    fetchJson<any>('/api/demo/scenario', {
      method: 'POST',
      body: JSON.stringify({ scenario })
    }),
  resetDemo: () =>
    fetchJson<any>('/api/demo/reset', { method: 'POST' }),
  getDemoStatus: () => fetchJson<any>('/api/demo/status'),
};

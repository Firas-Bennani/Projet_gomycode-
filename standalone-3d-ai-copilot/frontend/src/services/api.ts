const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
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

  // Cameras & Risks
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

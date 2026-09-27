type Listener = (data: any) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private listeners: Map<string, Set<Listener>> = new Map();
  private reconnectInterval = 3000;
  private shouldReconnect = true;

  constructor() {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
    this.url = `${wsUrl}/ws`;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WS] Connected to AI Industrial Copilot WebSocket bus');
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const channel = payload.channel || 'all';
          const eventType = payload.event_type || 'UNKNOWN';

          // Notify channel listeners
          this.notify(channel, payload);
          this.notify(eventType, payload);
          this.notify('all', payload);
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      this.ws.onclose = () => {
        console.warn('[WS] Disconnected. Reconnecting in 3s...');
        if (this.shouldReconnect) {
          setTimeout(() => this.connect(), this.reconnectInterval);
        }
      };

      this.ws.onerror = (err) => {
        console.error('[WS] Error:', err);
      };
    } catch (e) {
      console.error('[WS] Connection init error:', e);
      setTimeout(() => this.connect(), this.reconnectInterval);
    }
  }

  subscribe(topic: string, listener: Listener): () => void {
    if (!this.listeners.has(topic)) {
      this.listeners.set(topic, new Set());
    }
    this.listeners.get(topic)!.add(listener);

    return () => {
      const set = this.listeners.get(topic);
      if (set) {
        set.delete(listener);
      }
    };
  }

  private notify(topic: string, data: any) {
    const set = this.listeners.get(topic);
    if (set) {
      set.forEach((listener) => {
        try {
          listener(data);
        } catch (err) {
          console.error(`[WS] Error in listener for topic ${topic}:`, err);
        }
      });
    }
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
    }
  }
}

export const wsClient = new WebSocketClient();

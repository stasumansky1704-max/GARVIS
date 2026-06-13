// =============================================================================
// GARVIS WebSocket Client — Real-time cognition event streaming
// =============================================================================

import type { WebSocketMessage } from "./types";

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

export class GARVISWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private messageHandlers: Map<string, ((data: unknown) => void)[]> = new Map();
  private isConnected = false;
  private reconnectAttempts = 0;
  private url: string;
  private statusListeners: ((connected: boolean) => void)[] = [];

  constructor(url = "ws://localhost:8000/ws") {
    this.url = url;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.notifyStatusChange(true);
        console.log("[GARVIS-WS] Connected");
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          const handlers = this.messageHandlers.get(msg.type) || [];
          handlers.forEach((h) => {
            try { h(msg.data); } catch (e) { console.error("[GARVIS-WS] Handler error:", e); }
          });
        } catch (e) {
          console.error("[GARVIS-WS] Parse error:", e);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.notifyStatusChange(false);
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.error("[GARVIS-WS] Error:", err);
        this.ws?.close();
      };
    } catch (e) {
      console.error("[GARVIS-WS] Connection failed:", e);
      this.scheduleReconnect();
    }
  }

  on(type: string, handler: (data: unknown) => void): () => void {
    const handlers = this.messageHandlers.get(type) || [];
    handlers.push(handler);
    this.messageHandlers.set(type, handlers);

    // Return unsubscribe function
    return () => {
      const hs = this.messageHandlers.get(type) || [];
      this.messageHandlers.set(
        type,
        hs.filter((h) => h !== handler)
      );
    };
  }

  onStatusChange(listener: (connected: boolean) => void): () => void {
    this.statusListeners.push(listener);
    return () => {
      this.statusListeners = this.statusListeners.filter((l) => l !== listener);
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.notifyStatusChange(false);
  }

  send(type: string, data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data }));
    }
  }

  get connected(): boolean {
    return this.isConnected;
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn("[GARVIS-WS] Max reconnect attempts reached");
      return;
    }
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      console.log(`[GARVIS-WS] Reconnecting... (${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
      this.connect();
    }, RECONNECT_DELAY_MS);
  }

  private notifyStatusChange(connected: boolean): void {
    this.statusListeners.forEach((l) => {
      try { l(connected); } catch (e) { /* ignore */ }
    });
  }
}

// Singleton instance
let wsInstance: GARVISWebSocket | null = null;

export function getWebSocket(url?: string): GARVISWebSocket {
  if (!wsInstance) {
    wsInstance = new GARVISWebSocket(url);
  }
  return wsInstance;
}

export function resetWebSocket(): void {
  wsInstance?.disconnect();
  wsInstance = null;
}

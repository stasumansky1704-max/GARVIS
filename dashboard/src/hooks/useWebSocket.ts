// =============================================================================
// useWebSocket — Hook for WebSocket connection management
// =============================================================================

import { useState, useEffect, useRef, useCallback } from "react";
import { getWebSocket } from "@/websocket";

interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  messageTypes?: string[];
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { url, autoConnect = true, messageTypes = [] } = options;
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<Map<string, unknown>>(new Map());
  const wsRef = useRef(getWebSocket(url));
  const unsubscribers = useRef<(() => void)[]>([]);

  useEffect(() => {
    const ws = wsRef.current;

    // Listen for connection status
    const unsubStatus = ws.onStatusChange((isConnected) => {
      setConnected(isConnected);
    });
    unsubscribers.current.push(unsubStatus);

    // Subscribe to message types
    messageTypes.forEach((type) => {
      const unsub = ws.on(type, (data) => {
        setMessages((prev) => {
          const next = new Map(prev);
          next.set(type, data);
          return next;
        });
      });
      unsubscribers.current.push(unsub);
    });

    if (autoConnect) {
      ws.connect();
    }

    return () => {
      unsubscribers.current.forEach((u) => u());
      unsubscribers.current = [];
    };
  }, [url, autoConnect, messageTypes.join(",")]);

  const send = useCallback((type: string, data: unknown) => {
    wsRef.current.send(type, data);
  }, []);

  const reconnect = useCallback(() => {
    wsRef.current.connect();
  }, []);

  return {
    connected,
    messages,
    send,
    reconnect,
    ws: wsRef.current,
  };
}

export function useWebSocketMessage(type: string) {
  const [data, setData] = useState<unknown>(null);
  const wsRef = useRef(getWebSocket());

  useEffect(() => {
    const unsub = wsRef.current.on(type, (msg) => {
      setData(msg);
    });
    return unsub;
  }, [type]);

  return data;
}

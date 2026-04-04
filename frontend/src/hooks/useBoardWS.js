import { useCallback, useEffect, useRef, useState } from 'react';

function buildWsUrl(boardId) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/ws/boards/${encodeURIComponent(boardId)}`;
}

function nextDelay(attempt) {
  const base = Math.min(15000, 1000 * (2 ** Math.min(attempt, 4)));
  const jitter = Math.round(base * (0.2 * (Math.random() - 0.5)));
  return Math.max(1000, base + jitter);
}

export function useBoardWS(boardId, onEvent) {
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const staleTimerRef = useRef(null);
  const heartbeatTimerRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const onEventRef = useRef(onEvent);
  const [connected, setConnected] = useState(false);
  const [transport, setTransport] = useState('polling');
  const [lastMessageAt, setLastMessageAt] = useState(null);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
    if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    reconnectTimerRef.current = null;
    staleTimerRef.current = null;
    heartbeatTimerRef.current = null;
  }, []);

  const scheduleStaleCheck = useCallback(() => {
    if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
    staleTimerRef.current = setTimeout(() => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.close();
        } catch {
          // ignore
        }
      }
    }, 60000);
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!boardId || reconnectTimerRef.current) return;
    const delay = nextDelay(reconnectAttemptRef.current);
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      reconnectAttemptRef.current += 1;
      connect();
    }, delay);
  }, [boardId]);

  const connect = useCallback(() => {
    if (!boardId) return;

    const current = wsRef.current;
    if (current && (current.readyState === WebSocket.OPEN || current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const ws = new WebSocket(buildWsUrl(boardId));
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptRef.current = 0;
      setConnected(true);
      setTransport('ws');
      setLastMessageAt(Date.now());
      scheduleStaleCheck();
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send(JSON.stringify({ type: 'ping' }));
          } catch {
            // ignore
          }
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      setLastMessageAt(Date.now());
      scheduleStaleCheck();
      try {
        const payload = JSON.parse(event.data);
        if (payload?.type === 'pong' || payload?.type === 'heartbeat') return;
        onEventRef.current?.(payload);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      setConnected(false);
      setTransport('polling');
    };

    ws.onclose = () => {
      if (wsRef.current === ws) wsRef.current = null;
      setConnected(false);
      setTransport('polling');
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
      scheduleReconnect();
    };
  }, [boardId, scheduleReconnect, scheduleStaleCheck]);

  useEffect(() => {
    clearTimers();
    connect();
    return () => {
      clearTimers();
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        try {
          ws.close();
        } catch {
          // ignore
        }
      }
    };
  }, [boardId, connect, clearTimers]);

  return {
    connected,
    transport,
    lastMessageAt,
    reconnectAttempt: reconnectAttemptRef.current,
  };
}

export default useBoardWS;

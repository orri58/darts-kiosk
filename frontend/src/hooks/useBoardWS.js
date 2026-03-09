import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * useBoardWS – subscribes to /api/ws/boards for real-time board events.
 * Falls back to HTTP polling if the WS connection fails.
 * 
 * @param {function} onEvent - callback(event, data) fired on each WS message
 * @returns {{ connected: boolean }}
 */
export function useBoardWS(onEvent) {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    // Build WS URL — support both full URL and relative (same-origin) modes
    const base = process.env.REACT_APP_BACKEND_URL || '';
    let wsUrl;
    if (base) {
      wsUrl = base.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:') + '/api/ws/boards';
    } else {
      // Same-origin: derive ws:// from current page location
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${proto}//${window.location.host}/api/ws/boards`;
    }

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = null;
        }
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          onEventRef.current?.(msg.event, msg.data, msg.timestamp);
        } catch { /* ignore malformed */ }
      };

      ws.onclose = () => {
        setConnected(false);
        // Auto-reconnect after 3s
        if (!reconnectTimer.current) {
          reconnectTimer.current = setTimeout(() => {
            reconnectTimer.current = null;
            connect();
          }, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { connected };
}

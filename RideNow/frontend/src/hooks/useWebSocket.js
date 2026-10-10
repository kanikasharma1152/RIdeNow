import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

/**
 * useWebSocket
 * Manages authenticated WebSocket connection to RideNow backend gateway.
 * Features:
 * - Automatic connection with JWT query token
 * - Automatic reconnection with exponential backoff
 * - Periodic ping keepalive (every 30s)
 * - Event subscriber mechanism
 */
export const useWebSocket = (onMessage) => {
  const { user } = useAuth();
  const socketRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const retryCountRef = useRef(0);

  // Store latest onMessage callback to avoid reconnecting when callback changes
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const getWsUrl = useCallback(() => {
    const token = localStorage.getItem('token');
    if (!token) return null;

    if (import.meta.env.VITE_WS_URL) {
      const wsBase = import.meta.env.VITE_WS_URL.replace(/\/$/, '');
      const separator = wsBase.includes('?') ? '&' : '?';
      return `${wsBase}${separator}token=${encodeURIComponent(token)}`;
    }

    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
    const wsProto = apiBase.startsWith('https') ? 'wss' : 'ws';
    const host = apiBase.replace(/^https?:\/\//, '').replace(/\/$/, '');
    return `${wsProto}://${host}/ws?token=${encodeURIComponent(token)}`;
  }, []);


  const connect = useCallback(() => {
    const url = getWsUrl();
    if (!url || !user) return;

    // Prevent duplicate connections
    if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        retryCountRef.current = 0;

        // Start ping heartbeat
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'PONG') return; // Handled internally
          if (onMessageRef.current) {
            onMessageRef.current(data);
          }
        } catch {
          // ignore non-JSON frames
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

        // Don't reconnect if intentional or unauthorized
        if (event.code === 1008) return;

        // Exponential backoff up to 15s
        const backoff = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 15000);
        retryCountRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, backoff);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // Reconnect handled by onclose
    }
  }, [getWsUrl, user]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((msg) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(typeof msg === 'string' ? msg : JSON.stringify(msg));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    if (user) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [user, connect, disconnect]);

  return { isConnected, sendMessage };
};

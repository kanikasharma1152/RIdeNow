import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useAuth } from './AuthContext';
import toast from 'react-hot-toast';

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  const { user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState('DISCONNECTED');
  const [lastEvent, setLastEvent] = useState(null);
  const socketRef = useRef(null);
  const listenersRef = useRef(new Set());
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const retryCountRef = useRef(0);
  const processedEventsRef = useRef(new Set());

  const subscribe = useCallback((callback) => {
    listenersRef.current.add(callback);
    return () => {
      listenersRef.current.delete(callback);
    };
  }, []);

  const connect = useCallback(() => {
    const token = localStorage.getItem('token');
    if (!token || !user) return;

    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.OPEN ||
        socketRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    setConnectionState((prev) => (prev === 'DISCONNECTED' ? 'CONNECTING' : 'RECONNECTING'));

    let url;
    if (import.meta.env.VITE_WS_URL) {
      const wsBase = import.meta.env.VITE_WS_URL.replace(/\/$/, '');
      const separator = wsBase.includes('?') ? '&' : '?';
      url = `${wsBase}${separator}token=${encodeURIComponent(token)}`;
    } else {
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
      const wsProto = apiBase.startsWith('https') ? 'wss' : 'ws';
      const host = apiBase.replace(/^https?:\/\//, '').replace(/\/$/, '');
      url = `${wsProto}://${host}/ws?token=${encodeURIComponent(token)}`;
    }

    try {
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionState('CONNECTED');

        const wasReconnect = retryCountRef.current > 0;
        retryCountRef.current = 0;

        if (wasReconnect) {
          listenersRef.current.forEach((fn) => {
            try {
              fn({ type: 'WS_RECONNECTED', timestamp: Date.now() });
            } catch {
              // Isolated
            }
          });
        }

        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }));
          }
        }, 20000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'PONG') return;

          // Event deduplication: prevent duplicate processing of the same lifecycle event for a ride
          const isLifecycleEvent = [
            'RIDE_ASSIGNED',
            'DRIVER_MATCHED',
            'RIDE_ACCEPTED',
            'RIDE_STARTED',
            'RIDE_COMPLETED',
            'RIDE_CANCELLED',
          ].includes(data.type);

          if (isLifecycleEvent && data.ride_id) {
            const eventKey = `${data.type}:${data.ride_id}`;
            if (processedEventsRef.current.has(eventKey)) {
              return; // Already processed this exact lifecycle transition for this ride
            }
            processedEventsRef.current.add(eventKey);
          }

          setLastEvent(data);

          // Handle global toast notifications for key events
          if (data.type === 'RIDE_ASSIGNED') {
            toast.success('🚗 New ride request received!', { id: `ride-${data.ride_id}` });
          } else if (data.type === 'DRIVER_MATCHED') {
            toast.success('🎉 Driver found for your ride!', { id: `driver-matched-${data.ride_id}` });
          } else if (data.type === 'RIDE_ACCEPTED') {
            toast.success('✅ Ride accepted by driver!', { id: `ride-accepted-${data.ride_id}` });
          } else if (data.type === 'RIDE_STARTED') {
            toast('🚗 Trip started. Enjoy your ride!', {
              id: `ride-started-${data.ride_id}`,
              icon: '🏁',
            });
          } else if (data.type === 'RIDE_COMPLETED') {
            const fareMsg = data.data?.fare ? ` Total: ₹${data.data.fare}` : '';
            toast.success(`🏁 Ride completed!${fareMsg}`, {
              id: `ride-completed-${data.ride_id}`,
              duration: 6000,
            });
          } else if (data.type === 'RIDE_CANCELLED') {
            toast.error('❌ Ride was cancelled.', {
              id: `ride-cancelled-${data.ride_id}`,
            });
          }

          // Broadcast to all active subscribers
          listenersRef.current.forEach((fn) => {
            try {
              fn(data);
            } catch {
              // Subscriber handler error isolated
            }
          });
        } catch {
          // ignore non-JSON messages
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        setConnectionState('DISCONNECTED');
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

        if (event.code === 1008) return;

        const backoff = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 15000);
        retryCountRef.current += 1;
        setConnectionState('RECONNECTING');
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, backoff);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // Handled by onclose
    }
  }, [user]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    processedEventsRef.current.clear();
    setIsConnected(false);
    setConnectionState('DISCONNECTED');
  }, []);

  const send = useCallback((payload) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        typeof payload === 'string' ? payload : JSON.stringify(payload)
      );
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

  return (
    <WebSocketContext.Provider value={{ isConnected, connectionState, lastEvent, subscribe, send }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useSocket = () => {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error('useSocket must be used within a WebSocketProvider');
  }
  return ctx;
};

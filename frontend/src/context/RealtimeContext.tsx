import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  useCallback,
} from 'react';
import { RealtimeChannel } from '@supabase/supabase-js';
import { useAuth } from './AuthContext';
import { supabase, isSupabaseConfigured } from '../services/supabase';
import {
  RealtimeStatus,
  RealtimeTable,
  RealtimePayload,
  RealtimeListener,
  ReconnectListener,
  RealtimeContextValue,
} from '../types/realtime';

const RealtimeContext = createContext<RealtimeContextValue | undefined>(undefined);

// Maximum size for deduplication cache
const MAX_SEEN_EVENTS = 200;

export const RealtimeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { session, serverAuth } = useAuth();
  const token = session?.access_token;
  const activeBusinessId = serverAuth?.active_business?.business_id ?? null;

  const [status, setStatus] = useState<RealtimeStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);
  const [lastReconciledAt, setLastReconciledAt] = useState<Date | null>(null);
  const [reconnectTrigger, setReconnectTrigger] = useState<number>(0);

  // Active channel reference
  const channelRef = useRef<RealtimeChannel | null>(null);
  const subscribedBusinessIdRef = useRef<string | null>(null);

  // Listeners registry for each table
  const tableListenersRef = useRef<Map<RealtimeTable, Set<RealtimeListener>>>(
    new Map([
      ['products', new Set()],
      ['inventory', new Set()],
      ['orders', new Set()],
      ['stock_movements', new Set()],
      ['invoices', new Set()],
    ])
  );

  // Reconnection listeners
  const reconnectListenersRef = useRef<Set<ReconnectListener>>(new Set());

  // Deduplication cache: keeps record of `${table}:${id}:${eventType}:${timestamp}`
  const seenEventKeysRef = useRef<Set<string>>(new Set());

  const addSeenEventKey = (key: string): boolean => {
    if (seenEventKeysRef.current.has(key)) {
      return false; // already seen (duplicate)
    }
    seenEventKeysRef.current.add(key);
    if (seenEventKeysRef.current.size > MAX_SEEN_EVENTS) {
      // Remove oldest entries
      const iterator = seenEventKeysRef.current.values();
      const first = iterator.next().value;
      if (first !== undefined) {
        seenEventKeysRef.current.delete(first);
      }
    }
    return true; // newly observed event
  };

  const dispatchEvent = useCallback(
    (table: RealtimeTable, payload: any) => {
      const currentBizId = subscribedBusinessIdRef.current;
      if (!currentBizId) return;

      const newRecord = payload.new || {};
      const oldRecord = payload.old || {};
      const recordBizId = newRecord.business_id || oldRecord.business_id;

      // Tenant isolation: discard events that do not match the current active business
      if (recordBizId && recordBizId !== currentBizId) {
        return;
      }

      const recordId = newRecord.id || oldRecord.id || 'unknown';
      const commitTimestamp = payload.commit_timestamp || '';
      const eventType = payload.eventType || 'UPDATE';
      const dedupeKey = `${table}:${recordId}:${eventType}:${commitTimestamp}`;

      if (!addSeenEventKey(dedupeKey)) {
        // Discard duplicate event
        return;
      }

      const formattedPayload: RealtimePayload = {
        table,
        eventType,
        new: newRecord,
        old: oldRecord,
        commit_timestamp: commitTimestamp,
        business_id: recordBizId || currentBizId,
      };

      const listeners = tableListenersRef.current.get(table);
      if (listeners && listeners.size > 0) {
        listeners.forEach((listener) => {
          try {
            listener(formattedPayload);
          } catch (err) {
            console.error(`[Orqestra Realtime] Error in ${table} listener:`, err);
          }
        });
      }
    },
    []
  );

  const notifyReconnect = useCallback(() => {
    reconnectListenersRef.current.forEach((listener) => {
      try {
        listener();
      } catch (err) {
        console.error('[Orqestra Realtime] Error in reconnect listener:', err);
      }
    });
  }, []);

  const cleanupSubscription = useCallback(() => {
    if (channelRef.current && supabase) {
      try {
        supabase.removeChannel(channelRef.current);
      } catch (err) {
        console.error('[Orqestra Realtime] Error removing channel:', err);
      }
      channelRef.current = null;
    }
    subscribedBusinessIdRef.current = null;
    seenEventKeysRef.current.clear();
  }, []);

  // Main subscription lifecycle effect
  useEffect(() => {
    // 1. Guard against unauthenticated, unconfigured, or business-less state
    if (!isSupabaseConfigured || !supabase || !token || !activeBusinessId) {
      cleanupSubscription();
      setStatus('disconnected');
      setError(null);
      return;
    }

    // 2. Tear down existing subscription if business ID changed
    if (
      subscribedBusinessIdRef.current &&
      subscribedBusinessIdRef.current !== activeBusinessId
    ) {
      cleanupSubscription();
    }

    // 3. Initiate channel creation
    setStatus('connecting');
    setError(null);

    // Apply the current session access token to the Supabase Realtime client
    try {
      supabase.realtime.setAuth(token);
    } catch {
      // Ignore if setAuth is not supported by mock client in tests
    }

    const channelName = `realtime:business:${activeBusinessId}`;
    const channel = supabase.channel(channelName, {
      config: {
        broadcast: { self: false },
      },
    });

    subscribedBusinessIdRef.current = activeBusinessId;
    channelRef.current = channel;

    // Attach postgres_changes listeners with tenant filter
    const operationalTables: RealtimeTable[] = [
      'products',
      'inventory',
      'orders',
      'stock_movements',
      'invoices',
    ];

    operationalTables.forEach((table) => {
      channel.on(
        'postgres_changes' as any,
        {
          event: '*',
          schema: 'public',
          table,
          filter: `business_id=eq.${activeBusinessId}`,
        },
        (payload: any) => dispatchEvent(table, payload)
      );
    });

    channel.subscribe((subStatus, err) => {
      if (subStatus === 'SUBSCRIBED') {
        setStatus('connected');
        setError(null);
        setLastReconciledAt(new Date());
        notifyReconnect();
      } else if (subStatus === 'TIMED_OUT') {
        setStatus('error');
        setError('Realtime connection timed out.');
      } else if (subStatus === 'CLOSED') {
        setStatus('disconnected');
      } else if (subStatus === 'CHANNEL_ERROR') {
        setStatus('error');
        setError(err?.message || 'Realtime subscription rejected by database policy.');
      }
    });

    return () => {
      cleanupSubscription();
      setStatus('disconnected');
    };
  }, [
    token,
    activeBusinessId,
    reconnectTrigger,
    cleanupSubscription,
    dispatchEvent,
    notifyReconnect,
  ]);

  const reconnect = useCallback(() => {
    cleanupSubscription();
    setReconnectTrigger((prev) => prev + 1);
  }, [cleanupSubscription]);

  const subscribeToTable = useCallback(
    <T = Record<string, unknown>>(
      table: RealtimeTable,
      listener: RealtimeListener<T>
    ) => {
      let listeners = tableListenersRef.current.get(table);
      if (!listeners) {
        listeners = new Set();
        tableListenersRef.current.set(table, listeners);
      }
      listeners.add(listener as RealtimeListener);
      return () => {
        const currentListeners = tableListenersRef.current.get(table);
        if (currentListeners) {
          currentListeners.delete(listener as RealtimeListener);
        }
      };
    },
    []
  );

  const subscribeToReconnect = useCallback((listener: ReconnectListener) => {
    reconnectListenersRef.current.add(listener);
    return () => {
      reconnectListenersRef.current.delete(listener);
    };
  }, []);

  return (
    <RealtimeContext.Provider
      value={{
        status,
        error,
        activeBusinessId,
        reconnect,
        subscribeToTable,
        subscribeToReconnect,
        lastReconciledAt,
      }}
    >
      {children}
    </RealtimeContext.Provider>
  );
};

const defaultRealtimeValue: RealtimeContextValue = {
  status: 'disconnected',
  error: null,
  activeBusinessId: null,
  reconnect: () => {},
  subscribeToTable: () => () => {},
  subscribeToReconnect: () => () => {},
  lastReconciledAt: null,
};

export const useRealtime = (): RealtimeContextValue => {
  const context = useContext(RealtimeContext);
  return context ?? defaultRealtimeValue;
};

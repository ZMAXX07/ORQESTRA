import { useEffect, useRef, useCallback } from 'react';
import { useRealtime } from '../context/RealtimeContext';
import {
  RealtimeTable,
  RealtimePayload,
  RealtimeStatus,
} from '../types/realtime';

interface UseRealtimeTableOptions<T = Record<string, unknown>> {
  table: RealtimeTable;
  onEvent?: (payload: RealtimePayload<T>) => void;
  onReconcile?: () => void;
  debounceMs?: number;
}

export function useRealtimeTable<T = Record<string, unknown>>({
  table,
  onEvent,
  onReconcile,
  debounceMs = 300,
}: UseRealtimeTableOptions<T>): {
  status: RealtimeStatus;
  error: string | null;
  reconnect: () => void;
} {
  const { status, error, reconnect, subscribeToTable, subscribeToReconnect } = useRealtime();

  const onEventRef = useRef(onEvent);
  const onReconcileRef = useRef(onReconcile);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    onEventRef.current = onEvent;
    onReconcileRef.current = onReconcile;
  });

  const handleEvent = useCallback(
    (payload: RealtimePayload<T>) => {
      if (!onEventRef.current) return;

      if (debounceMs <= 0) {
        onEventRef.current(payload);
        return;
      }

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(() => {
        onEventRef.current?.(payload);
      }, debounceMs);
    },
    [debounceMs]
  );

  const handleReconnect = useCallback(() => {
    if (onReconcileRef.current) {
      onReconcileRef.current();
    }
  }, []);

  useEffect(() => {
    const unsubscribeTable = subscribeToTable<T>(table, handleEvent);
    const unsubscribeReconnect = subscribeToReconnect(handleReconnect);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      unsubscribeTable();
      unsubscribeReconnect();
    };
  }, [table, handleEvent, handleReconnect, subscribeToTable, subscribeToReconnect]);

  return { status, error, reconnect };
}

/**
 * Typed domain interfaces for Phase 4 Supabase Realtime synchronization.
 */

export type RealtimeStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

export type RealtimeTable = 'products' | 'inventory' | 'orders' | 'stock_movements' | 'invoices';

export type RealtimeEventType = 'INSERT' | 'UPDATE' | 'DELETE';

export interface RealtimePayload<T = Record<string, unknown>> {
  table: RealtimeTable;
  eventType: RealtimeEventType;
  new: T;
  old: Partial<T>;
  commit_timestamp: string;
  business_id?: string;
}

export type RealtimeListener<T = Record<string, unknown>> = (
  payload: RealtimePayload<T>
) => void;

export type ReconnectListener = () => void;

export interface RealtimeContextValue {
  status: RealtimeStatus;
  error: string | null;
  activeBusinessId: string | null;
  reconnect: () => void;
  subscribeToTable: <T = Record<string, unknown>>(
    table: RealtimeTable,
    listener: RealtimeListener<T>
  ) => () => void;
  subscribeToReconnect: (listener: ReconnectListener) => () => void;
  lastReconciledAt: Date | null;
}

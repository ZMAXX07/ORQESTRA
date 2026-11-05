import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { RealtimeProvider, useRealtime } from '../src/context/RealtimeContext';
import { useRealtimeTable } from '../src/hooks/useRealtimeTable';
import { RealtimeStatusBadge } from '../src/components/realtime/RealtimeStatusBadge';
import * as SupabaseService from '../src/services/supabase';
import * as AuthContextModule from '../src/context/AuthContext';
import { RealtimePayload } from '../src/types/realtime';

describe('Supabase Realtime Subscriptions & Lifecycle (Phase 4)', () => {
  let mockChannel: any;
  let mockSupabase: any;
  let postgresCallbacks: Map<string, (payload: any) => void>;
  let subscribeStatusCallback: (status: string, err?: any) => void;

  const sampleBusinessId = '11111111-1111-1111-1111-111111111111';
  const otherBusinessId = '22222222-2222-2222-2222-222222222222';
  const sampleToken = 'mock-jwt-token-alpha';

  beforeEach(() => {
    vi.restoreAllMocks();
    postgresCallbacks = new Map();

    mockChannel = {
      on: vi.fn().mockImplementation((_type: string, filter: any, callback: (p: any) => void) => {
        if (filter?.table) {
          postgresCallbacks.set(filter.table, callback);
        }
        return mockChannel;
      }),
      subscribe: vi.fn().mockImplementation((cb: (status: string, err?: any) => void) => {
        subscribeStatusCallback = cb;
        return mockChannel;
      }),
    };

    mockSupabase = {
      realtime: {
        setAuth: vi.fn(),
      },
      channel: vi.fn().mockReturnValue(mockChannel),
      removeChannel: vi.fn(),
    };

    // Override Supabase client export
    vi.spyOn(SupabaseService, 'supabase', 'get').mockReturnValue(mockSupabase as any);
    vi.spyOn(SupabaseService, 'isSupabaseConfigured', 'get').mockReturnValue(true);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  function setupAuthMock(token: string | null, businessId: string | null) {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      session: token ? ({ access_token: token } as any) : null,
      user: token ? ({ id: 'usr-123', email: 'test@orqestra.com' } as any) : null,
      serverAuth: businessId
        ? ({
            status: 'authenticated',
            user: { user_id: 'usr-123' },
            active_business: {
              business_id: businessId,
              business_name: 'Alpha Ltd',
              role: 'admin',
              is_active: true,
            },
            memberships: [],
          } as any)
        : null,
      isLoading: false,
      isConfigured: true,
      authError: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshServerAuth: vi.fn(),
    });
  }

  it('does NOT create a subscription before authentication or without active business', () => {
    setupAuthMock(null, null);

    const TestComponent = () => {
      const { status } = useRealtime();
      return <div data-testid="status">{status}</div>;
    };

    render(
      <RealtimeProvider>
        <TestComponent />
      </RealtimeProvider>
    );

    expect(mockSupabase.channel).not.toHaveBeenCalled();
    expect(screen.getByTestId('status').textContent).toBe('disconnected');
  });

  it('creates channel, applies token, registers tables, and transitions to connected on SUBSCRIBED', () => {
    setupAuthMock(sampleToken, sampleBusinessId);

    const TestComponent = () => {
      const { status } = useRealtime();
      return <div data-testid="status">{status}</div>;
    };

    render(
      <RealtimeProvider>
        <TestComponent />
      </RealtimeProvider>
    );

    // Verifies token was passed to realtime client
    expect(mockSupabase.realtime.setAuth).toHaveBeenCalledWith(sampleToken);

    // Verifies channel name is business-scoped
    expect(mockSupabase.channel).toHaveBeenCalledWith(
      `realtime:business:${sampleBusinessId}`,
      expect.any(Object)
    );

    // Verifies postgres_changes subscriptions for all 5 operational tables with tenant filter
    expect(mockChannel.on).toHaveBeenCalledWith(
      'postgres_changes',
      expect.objectContaining({
        table: 'products',
        filter: `business_id=eq.${sampleBusinessId}`,
      }),
      expect.any(Function)
    );
    expect(mockChannel.on).toHaveBeenCalledWith(
      'postgres_changes',
      expect.objectContaining({
        table: 'inventory',
        filter: `business_id=eq.${sampleBusinessId}`,
      }),
      expect.any(Function)
    );
    expect(mockChannel.on).toHaveBeenCalledWith(
      'postgres_changes',
      expect.objectContaining({
        table: 'orders',
        filter: `business_id=eq.${sampleBusinessId}`,
      }),
      expect.any(Function)
    );
    expect(mockChannel.on).toHaveBeenCalledWith(
      'postgres_changes',
      expect.objectContaining({
        table: 'stock_movements',
        filter: `business_id=eq.${sampleBusinessId}`,
      }),
      expect.any(Function)
    );
    expect(mockChannel.on).toHaveBeenCalledWith(
      'postgres_changes',
      expect.objectContaining({
        table: 'invoices',
        filter: `business_id=eq.${sampleBusinessId}`,
      }),
      expect.any(Function)
    );

    // Channel initially in connecting state before callback
    expect(screen.getByTestId('status').textContent).toBe('connecting');

    // Simulate SUBSCRIBED callback from Supabase
    act(() => {
      subscribeStatusCallback('SUBSCRIBED');
    });

    expect(screen.getByTestId('status').textContent).toBe('connected');
  });

  it('cleans up and removes channel on sign-out', () => {
    setupAuthMock(sampleToken, sampleBusinessId);

    const { unmount } = render(
      <RealtimeProvider>
        <div>Content</div>
      </RealtimeProvider>
    );

    expect(mockSupabase.removeChannel).not.toHaveBeenCalled();

    // Trigger unmount / sign-out
    unmount();

    expect(mockSupabase.removeChannel).toHaveBeenCalledWith(mockChannel);
  });

  it('tears down previous channel and establishes a new channel on business switch', () => {
    // Dynamic Auth wrapper to simulate changing business
    let currentBizId = sampleBusinessId;
    const authSpy = vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => ({
      session: { access_token: sampleToken } as any,
      user: { id: 'usr-123' } as any,
      serverAuth: {
        status: 'authenticated',
        user: { user_id: 'usr-123' },
        active_business: {
          business_id: currentBizId,
          business_name: 'Active Biz',
          role: 'admin',
          is_active: true,
        },
        memberships: [],
      } as any,
      isLoading: false,
      isConfigured: true,
      authError: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshServerAuth: vi.fn(),
    }));

    const TestComponent = () => {
      const { activeBusinessId } = useRealtime();
      return <div data-testid="biz-id">{activeBusinessId}</div>;
    };

    const { rerender } = render(
      <RealtimeProvider>
        <TestComponent />
      </RealtimeProvider>
    );

    expect(mockSupabase.channel).toHaveBeenCalledWith(`realtime:business:${sampleBusinessId}`, expect.any(Object));

    // Simulate switching active business
    currentBizId = otherBusinessId;
    authSpy.mockImplementation(() => ({
      session: { access_token: sampleToken } as any,
      user: { id: 'usr-123' } as any,
      serverAuth: {
        status: 'authenticated',
        user: { user_id: 'usr-123' },
        active_business: {
          business_id: otherBusinessId,
          business_name: 'Other Biz',
          role: 'admin',
          is_active: true,
        },
        memberships: [],
      } as any,
      isLoading: false,
      isConfigured: true,
      authError: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshServerAuth: vi.fn(),
    }));

    rerender(
      <RealtimeProvider>
        <TestComponent />
      </RealtimeProvider>
    );

    // Old channel removed
    expect(mockSupabase.removeChannel).toHaveBeenCalledWith(mockChannel);
    // New channel initialized for other business
    expect(mockSupabase.channel).toHaveBeenCalledWith(`realtime:business:${otherBusinessId}`, expect.any(Object));
  });

  it('enforces tenant isolation and drops events from a foreign business', () => {
    setupAuthMock(sampleToken, sampleBusinessId);

    const receivedEvents: RealtimePayload[] = [];
    const ConsumerComponent = () => {
      useRealtimeTable({
        table: 'products',
        debounceMs: 0,
        onEvent: (payload) => {
          receivedEvents.push(payload);
        },
      });
      return <div>Listening</div>;
    };

    render(
      <RealtimeProvider>
        <ConsumerComponent />
      </RealtimeProvider>
    );

    const productCb = postgresCallbacks.get('products');
    expect(productCb).toBeDefined();

    // 1. Dispatch event with foreign business_id
    act(() => {
      productCb!({
        eventType: 'INSERT',
        commit_timestamp: '2026-10-23T11:00:00Z',
        new: { id: 'prod-foreign', business_id: otherBusinessId, name: 'Foreign Product' },
      });
    });

    // Foreign event must NOT be delivered
    expect(receivedEvents).toHaveLength(0);

    // 2. Dispatch event matching active business_id
    act(() => {
      productCb!({
        eventType: 'INSERT',
        commit_timestamp: '2026-10-23T11:00:01Z',
        new: { id: 'prod-own', business_id: sampleBusinessId, name: 'Own Product' },
      });
    });

    expect(receivedEvents).toHaveLength(1);
    expect(receivedEvents[0].new.id).toBe('prod-own');
  });

  it('filters duplicate events with identical commit timestamp and record ID', () => {
    setupAuthMock(sampleToken, sampleBusinessId);

    const receivedEvents: RealtimePayload[] = [];
    const ConsumerComponent = () => {
      useRealtimeTable({
        table: 'orders',
        debounceMs: 0,
        onEvent: (payload) => {
          receivedEvents.push(payload);
        },
      });
      return <div>Listening Orders</div>;
    };

    render(
      <RealtimeProvider>
        <ConsumerComponent />
      </RealtimeProvider>
    );

    const ordersCb = postgresCallbacks.get('orders');
    expect(ordersCb).toBeDefined();

    const eventPayload = {
      eventType: 'UPDATE',
      commit_timestamp: '2026-10-23T11:05:00Z',
      new: { id: 'ord-100', business_id: sampleBusinessId, status: 'approved' },
      old: { id: 'ord-100', business_id: sampleBusinessId, status: 'pending_approval' },
    };

    // First arrival
    act(() => {
      ordersCb!(eventPayload);
    });
    expect(receivedEvents).toHaveLength(1);

    // Duplicate arrival (e.g. repeated network packet or duplicate socket event)
    act(() => {
      ordersCb!(eventPayload);
    });
    // Should still only have 1 event dispatched
    expect(receivedEvents).toHaveLength(1);
  });

  it('handles error states and notifies reconnect callbacks upon recovery', () => {
    setupAuthMock(sampleToken, sampleBusinessId);

    let reconcileCount = 0;
    const StatusConsumer = () => {
      const { status, error, reconnect } = useRealtime();
      useRealtimeTable({
        table: 'inventory',
        onReconcile: () => {
          reconcileCount++;
        },
      });

      return (
        <div>
          <span data-testid="status">{status}</span>
          <span data-testid="err">{error || 'none'}</span>
          <button data-testid="retry" onClick={reconnect}>
            Retry
          </button>
        </div>
      );
    };

    render(
      <RealtimeProvider>
        <StatusConsumer />
      </RealtimeProvider>
    );

    // Simulate error from database policy / RLS rejection
    act(() => {
      subscribeStatusCallback('CHANNEL_ERROR', new Error('RLS subscription denied'));
    });

    expect(screen.getByTestId('status').textContent).toBe('error');
    expect(screen.getByTestId('err').textContent).toBe('RLS subscription denied');

    // User triggers retry
    fireEvent.click(screen.getByTestId('retry'));

    // Old channel cleared and new subscription initiated
    expect(mockSupabase.removeChannel).toHaveBeenCalled();

    // Recover with SUBSCRIBED
    act(() => {
      subscribeStatusCallback('SUBSCRIBED');
    });

    expect(screen.getByTestId('status').textContent).toBe('connected');
    expect(reconcileCount).toBeGreaterThan(0);
  });

  it('renders RealtimeStatusBadge with appropriate connection state and retry trigger', () => {
    setupAuthMock(sampleToken, sampleBusinessId);

    const { rerender } = render(
      <RealtimeProvider>
        <RealtimeStatusBadge />
      </RealtimeProvider>
    );

    // Connecting state
    expect(screen.getByText(/Live Sync: Connecting.../i)).toBeInTheDocument();

    // Transition to Connected: permanent green badge must NOT be displayed in normal UI
    act(() => {
      subscribeStatusCallback('SUBSCRIBED');
    });
    expect(screen.queryByText(/Live Sync: Connected/i)).not.toBeInTheDocument();

    // When explicitly configured with showConnected={true}, badge is displayed
    rerender(
      <RealtimeProvider>
        <RealtimeStatusBadge showConnected={true} />
      </RealtimeProvider>
    );
    expect(screen.getByText(/Live Sync: Connected/i)).toBeInTheDocument();

    // Reset back to default normal interface (showConnected={false})
    rerender(
      <RealtimeProvider>
        <RealtimeStatusBadge />
      </RealtimeProvider>
    );
    expect(screen.queryByText(/Live Sync: Connected/i)).not.toBeInTheDocument();

    // Transition to Error: subtle warning and retry button appear
    act(() => {
      subscribeStatusCallback('CHANNEL_ERROR', new Error('Network offline'));
    });
    expect(screen.getByText(/Network offline/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry realtime connection/i })).toBeInTheDocument();
  });

  describe('Invoice Realtime Dispatch & Isolation (Phase 6)', () => {
    it('dispatches invoice postgres_changes events to useRealtimeTable listeners for own business', () => {
      setupAuthMock(sampleToken, sampleBusinessId);

      const receivedEvents: RealtimePayload[] = [];
      let reconcileCalled = false;

      const InvoiceConsumer = () => {
        useRealtimeTable({
          table: 'invoices',
          debounceMs: 0,
          onEvent: (payload) => {
            receivedEvents.push(payload);
          },
          onReconcile: () => {
            reconcileCalled = true;
          },
        });
        return <div>Listening Invoices</div>;
      };

      render(
        <RealtimeProvider>
          <InvoiceConsumer />
        </RealtimeProvider>
      );

      const invoicesCb = postgresCallbacks.get('invoices');
      expect(invoicesCb).toBeDefined();

      const invoicePayload = {
        eventType: 'INSERT',
        commit_timestamp: '2026-10-24T12:00:00Z',
        new: {
          id: 'inv-101',
          business_id: sampleBusinessId,
          invoice_number: 'INV-202610-0001',
          total_amount: 150.0,
          status: 'issued',
        },
        old: {},
      };

      act(() => {
        invoicesCb!(invoicePayload);
      });

      expect(receivedEvents).toHaveLength(1);
      expect(receivedEvents[0].table).toBe('invoices');
      expect(receivedEvents[0].new.id).toBe('inv-101');
      expect(receivedEvents[0].new.invoice_number).toBe('INV-202610-0001');

      // Verify reconnection triggers onReconcile
      expect(reconcileCalled).toBe(false);
      act(() => {
        subscribeStatusCallback('SUBSCRIBED');
      });
      expect(reconcileCalled).toBe(true);
    });

    it('enforces tenant isolation and drops foreign business invoice events', () => {
      setupAuthMock(sampleToken, sampleBusinessId);

      const receivedEvents: RealtimePayload[] = [];

      const InvoiceConsumer = () => {
        useRealtimeTable({
          table: 'invoices',
          debounceMs: 0,
          onEvent: (payload) => {
            receivedEvents.push(payload);
          },
        });
        return <div>Listening Invoices</div>;
      };

      render(
        <RealtimeProvider>
          <InvoiceConsumer />
        </RealtimeProvider>
      );

      const invoicesCb = postgresCallbacks.get('invoices');
      expect(invoicesCb).toBeDefined();

      // Foreign invoice event
      act(() => {
        invoicesCb!({
          eventType: 'INSERT',
          commit_timestamp: '2026-10-24T12:01:00Z',
          new: {
            id: 'inv-foreign-999',
            business_id: otherBusinessId,
            invoice_number: 'INV-202610-9999',
          },
          old: {},
        });
      });

      // Must be dropped
      expect(receivedEvents).toHaveLength(0);

      // Own business invoice event
      act(() => {
        invoicesCb!({
          eventType: 'UPDATE',
          commit_timestamp: '2026-10-24T12:02:00Z',
          new: {
            id: 'inv-own-202',
            business_id: sampleBusinessId,
            invoice_number: 'INV-202610-0002',
            status: 'paid',
          },
          old: {
            id: 'inv-own-202',
            business_id: sampleBusinessId,
            status: 'issued',
          },
        });
      });

      expect(receivedEvents).toHaveLength(1);
      expect(receivedEvents[0].new.id).toBe('inv-own-202');
    });

    it('unregisters invoice listeners on component unmount and avoids leaks', () => {
      setupAuthMock(sampleToken, sampleBusinessId);

      const receivedEvents: RealtimePayload[] = [];

      const InvoiceConsumer = () => {
        useRealtimeTable({
          table: 'invoices',
          debounceMs: 0,
          onEvent: (payload) => {
            receivedEvents.push(payload);
          },
        });
        return <div>Listening Invoices</div>;
      };

      const { unmount } = render(
        <RealtimeProvider>
          <InvoiceConsumer />
        </RealtimeProvider>
      );

      const invoicesCb = postgresCallbacks.get('invoices');
      expect(invoicesCb).toBeDefined();

      // Unmount the consuming component
      unmount();

      // Dispatch event after unmount
      act(() => {
        invoicesCb!({
          eventType: 'INSERT',
          commit_timestamp: '2026-10-24T12:05:00Z',
          new: {
            id: 'inv-post-unmount',
            business_id: sampleBusinessId,
            invoice_number: 'INV-202610-0003',
          },
          old: {},
        });
      });

      // No events should be delivered to unmounted listener
      expect(receivedEvents).toHaveLength(0);
    });
  });
});

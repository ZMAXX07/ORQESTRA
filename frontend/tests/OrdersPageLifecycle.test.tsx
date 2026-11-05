import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { OrdersPage } from '../src/pages/OrdersPage';
import * as operationsApi from '../src/services/operations';
import { Order } from '../src/types/operations';

const mockOrder: Order = {
  id: 'ord-test-100',
  business_id: 'biz-1',
  order_number: 'ORD-100',
  status: 'pending_approval',
  subtotal: '250.00',
  tax: '0.00',
  total_amount: '250.00',
  items: [],
  created_at: '2026-10-31T10:00:00Z',
  updated_at: '2026-10-31T10:00:00Z',
};

const mockApprovedOrder: Order = {
  ...mockOrder,
  status: 'approved',
  updated_at: '2026-10-31T10:05:00Z',
};

const mockCancelledOrder: Order = {
  ...mockOrder,
  status: 'cancelled',
  updated_at: '2026-10-31T10:06:00Z',
};

vi.mock('../src/context/AuthContext', () => ({
  useAuth: () => ({
    session: { access_token: 'fake-jwt-token' },
    user: { id: 'usr-1', email: 'owner@biz.com' },
    serverAuth: {
      authenticated: true,
      user_id: 'usr-1',
      email: 'owner@biz.com',
      active_business: {
        business_id: 'biz-1',
        business_name: 'Acme Test Corp',
        role: 'owner',
        currency: 'USD',
      },
    },
    isLoading: false,
    isConfigured: true,
    authError: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    refreshServerAuth: vi.fn(),
  }),
}));

vi.mock('../src/hooks/useRealtimeTable', () => ({
  useRealtimeTable: () => ({
    status: 'connected',
    error: null,
    reconnect: vi.fn(),
  }),
}));

vi.mock('../src/services/operations', () => ({
  fetchOrders: vi.fn(),
  fetchOrder: vi.fn(),
  createOrder: vi.fn(),
  submitOrder: vi.fn(),
  approveOrder: vi.fn(),
  rejectOrder: vi.fn(),
  cancelOrder: vi.fn(),
  fetchProducts: vi.fn(),
  fetchCustomers: vi.fn(),
  allocateInvoiceForOrder: vi.fn(),
  downloadInvoicePdf: vi.fn(),
}));

describe('OrdersPage Asynchronous Lifecycle & Mutation Guards', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(operationsApi.fetchOrders).mockResolvedValue({
      items: [mockOrder],
      total: 1,
      page: 1,
      page_size: 20,
    });

    vi.mocked(operationsApi.fetchOrder).mockResolvedValue(mockOrder);
    vi.mocked(operationsApi.fetchProducts).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    vi.mocked(operationsApi.fetchCustomers).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
  });

  it('safely tolerates unmount while order approval promise is pending without throwing unhandled errors', async () => {
    let resolveApprove: (val: Order) => void;
    const pendingPromise = new Promise<Order>((resolve) => {
      resolveApprove = resolve;
    });
    vi.mocked(operationsApi.approveOrder).mockImplementation(() => pendingPromise);
    vi.spyOn(window, 'confirm').mockImplementation(() => true);

    const { unmount } = render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-100')).toBeInTheDocument();
    });

    // Open detail modal
    fireEvent.click(screen.getByRole('button', { name: /View & Manage/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve & Deduct Stock/i })).toBeInTheDocument();
    });

    // Trigger approval
    fireEvent.click(screen.getByRole('button', { name: /Approve & Deduct Stock/i }));
    expect(screen.getByText(/Approving\.\.\./i)).toBeInTheDocument();

    // Unmount while approval is pending in-flight
    unmount();

    // Resolve after component has unmounted
    resolveApprove!(mockApprovedOrder);

    // Wait a tick to ensure promise microtask completes without unhandled error or throw
    await new Promise((r) => setTimeout(r, 20));
  });

  it('safely tolerates unmount while order cancellation promise is pending', async () => {
    let resolveCancel: (val: Order) => void;
    const pendingPromise = new Promise<Order>((resolve) => {
      resolveCancel = resolve;
    });
    vi.mocked(operationsApi.cancelOrder).mockImplementation(() => pendingPromise);
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
    vi.spyOn(window, 'prompt').mockImplementation(() => 'Customer requested cancel');

    const { unmount } = render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-100')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /View & Manage/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Cancel Order/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Cancel Order/i }));
    expect(screen.getByText(/Cancelling\.\.\./i)).toBeInTheDocument();

    unmount();

    resolveCancel!(mockCancelledOrder);
    await new Promise((r) => setTimeout(r, 20));
  });

  it('successfully approves order and reflects deducted stock state', async () => {
    vi.mocked(operationsApi.approveOrder).mockResolvedValue(mockApprovedOrder);
    vi.spyOn(window, 'confirm').mockImplementation(() => true);

    render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-100')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /View & Manage/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve & Deduct Stock/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Approve & Deduct Stock/i }));

    await waitFor(() => {
      expect(screen.getByText(/Order ORD-100 approved and stock deducted\./i)).toBeInTheDocument();
    });

    expect(operationsApi.approveOrder).toHaveBeenCalledWith('fake-jwt-token', 'biz-1', 'ord-test-100');
  });

  it('handles order approval failure by displaying the error message', async () => {
    vi.mocked(operationsApi.approveOrder).mockRejectedValue(new Error('Insufficient warehouse inventory'));
    vi.spyOn(window, 'confirm').mockImplementation(() => true);

    render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-100')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /View & Manage/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve & Deduct Stock/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Approve & Deduct Stock/i }));

    await waitFor(() => {
      expect(screen.getByText(/Insufficient warehouse inventory/i)).toBeInTheDocument();
    });

    // Modal remains open and button re-enabled for operator correction
    expect(screen.getByRole('button', { name: /Approve & Deduct Stock/i })).not.toBeDisabled();
  });

  it('successfully cancels order and displays confirmation', async () => {
    vi.mocked(operationsApi.cancelOrder).mockResolvedValue(mockCancelledOrder);
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
    vi.spyOn(window, 'prompt').mockImplementation(() => 'Duplicate request');

    render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-100')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /View & Manage/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Cancel Order/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Cancel Order/i }));

    await waitFor(() => {
      expect(screen.getByText(/Order ORD-100 cancelled\./i)).toBeInTheDocument();
    });

    expect(operationsApi.cancelOrder).toHaveBeenCalledWith(
      'fake-jwt-token',
      'biz-1',
      'ord-test-100',
      'Duplicate request'
    );
  });

  it('handles cancellation failure by displaying error alert', async () => {
    vi.mocked(operationsApi.cancelOrder).mockRejectedValue(new Error('Order already fulfilled'));
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
    vi.spyOn(window, 'prompt').mockImplementation(() => 'Reason');

    render(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-100')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /View & Manage/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Cancel Order/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Cancel Order/i }));

    await waitFor(() => {
      expect(screen.getByText(/Order already fulfilled/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Cancel Order/i })).not.toBeDisabled();
  });
});

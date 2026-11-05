import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FoundationDashboard } from '../src/pages/FoundationDashboard';
import { Pagination } from '../src/components/common/Pagination';
import { InvoicesPage } from '../src/pages/InvoicesPage';
import { OrdersPage } from '../src/pages/OrdersPage';
import * as operationsApi from '../src/services/operations';
import { HealthResponse } from '../src/types/api';

const mockAuthContext = {
  session: { access_token: 'fake-jwt-token' },
  user: { id: 'usr-1', email: 'operator@biz.com' },
  serverAuth: {
    authenticated: true,
    user_id: 'usr-1',
    email: 'operator@biz.com',
    active_business: {
      business_id: 'biz-1',
      business_name: 'Alpha Corp',
      role: 'admin',
    },
  },
  isLoading: false,
  isConfigured: true,
  authError: null,
  signIn: vi.fn(),
  signOut: vi.fn(),
  refreshServerAuth: vi.fn(),
};

vi.mock('../src/context/AuthContext', () => ({
  useAuth: () => mockAuthContext,
}));

vi.mock('../src/hooks/useRealtimeTable', () => ({
  useRealtimeTable: () => ({
    status: 'connected',
    error: null,
    reconnect: vi.fn(),
  }),
}));

vi.mock('../src/services/operations', () => ({
  fetchProducts: vi.fn(),
  fetchCustomers: vi.fn(),
  fetchInventory: vi.fn(),
  adjustStock: vi.fn(),
  fetchStockMovements: vi.fn(),
  fetchOrders: vi.fn(),
  fetchOrder: vi.fn(),
  createOrder: vi.fn(),
  submitOrder: vi.fn(),
  approveOrder: vi.fn(),
  rejectOrder: vi.fn(),
  cancelOrder: vi.fn(),
  extractOrderFromText: vi.fn(),
  fetchInvoices: vi.fn(),
  fetchInvoice: vi.fn(),
  allocateInvoiceForOrder: vi.fn(),
  downloadInvoicePdf: vi.fn(),
}));

const mockHealthData: HealthResponse = {
  status: 'healthy',
  app_name: 'Orqestra API',
  version: '0.1.0',
  environment: 'development',
  timestamp: '2026-10-23T12:00:00Z',
  uptime_seconds: 3600,
  components: {
    python_runtime: { status: 'operational', details: 'Python 3.11.0 runtime active' },
    fastapi_server: { status: 'operational', details: 'FastAPI router operational' },
    database: { status: 'operational', details: 'Supabase PostgreSQL connected' },
    ai_service: { status: 'operational', details: 'Configured AI intake engine' },
    authentication: { status: 'operational', details: 'Supabase JWT engine verified' },
  },
};

describe('Phase 6: Operational Dashboard & Workflow Hardening', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(operationsApi.fetchProducts).mockResolvedValue({
      items: [],
      total: 18,
      page: 1,
      page_size: 1,
    });

    vi.mocked(operationsApi.fetchInventory).mockImplementation((_token, _biz, params) => {
      if (params?.low_stock_only) {
        return Promise.resolve({
          items: [
            {
              id: 'inv-1',
              business_id: 'biz-1',
              product_id: 'p-1',
              product_name: 'Steel Rods',
              product_sku: 'SR-01',
              quantity_on_hand: 2,
              unit_price: '50.00',
              reorder_threshold: 10,
              is_low_stock: true,
              updated_at: '2026-10-23T10:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 5,
          total_low_stock: 1,
        });
      }
      return Promise.resolve({
        items: [],
        total: 25,
        page: 1,
        page_size: 1,
        total_low_stock: 1,
      });
    });

    vi.mocked(operationsApi.fetchOrders).mockImplementation((_token, _biz, params) => {
      if (params?.status === 'pending_approval') {
        return Promise.resolve({
          items: [
            {
              id: 'ord-1',
              business_id: 'biz-1',
              order_number: 'ORD-2026-001',
              customer_name: 'Metro Ltd',
              status: 'pending_approval',
              subtotal: '350.00',
              tax: '0.00',
              total_amount: '350.00',
              created_at: '2026-10-23T10:00:00Z',
              updated_at: '2026-10-23T10:00:00Z',
              items: [],
            },
          ],
          total: 1,
          page: 1,
          page_size: 5,
        });
      }
      return Promise.resolve({
        items: [
          {
            id: 'ord-1',
            business_id: 'biz-1',
            order_number: 'ORD-2026-001',
            customer_name: 'Metro Ltd',
            status: 'pending_approval',
            subtotal: '350.00',
            tax: '0.00',
            total_amount: '350.00',
            created_at: '2026-10-23T10:00:00Z',
            updated_at: '2026-10-23T10:00:00Z',
            items: [],
          },
        ],
        total: 12,
        page: 1,
        page_size: 5,
      });
    });

    vi.mocked(operationsApi.fetchStockMovements).mockResolvedValue({
      items: [
        {
          id: 'mov-1',
          business_id: 'biz-1',
          product_id: 'p-1',
          product_name: 'Steel Rods',
          quantity_change: -5,
          movement_type: 'order_fulfillment',
          notes: 'Fulfillment deduction',
          created_at: '2026-10-23T09:30:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });

    vi.mocked(operationsApi.fetchInvoices).mockResolvedValue({
      items: [],
      total: 8,
      page: 1,
      page_size: 1,
    });
  });

  describe('Pagination Component', () => {
    it('renders pagination info and handles page changes', () => {
      const handlePageChange = vi.fn();
      render(
        <Pagination
          currentPage={1}
          pageSize={20}
          totalItems={45}
          onPageChange={handlePageChange}
        />
      );

      expect(screen.getByText(/Showing/i)).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();

      const prevBtn = screen.getByRole('button', { name: /previous/i });
      const nextBtn = screen.getByRole('button', { name: /next/i });

      expect(prevBtn).toBeDisabled();
      expect(nextBtn).not.toBeDisabled();

      fireEvent.click(nextBtn);
      expect(handlePageChange).toHaveBeenCalledWith(2);
    });

    it('returns null when items fit on a single page', () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          pageSize={20}
          totalItems={10}
          onPageChange={vi.fn()}
        />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Operational Dashboard with Real API Integration', () => {
    it('loads and displays operational metrics when authenticated', async () => {
      const handleNavigate = vi.fn();

      render(
        <FoundationDashboard
          health={mockHealthData}
          isLoading={false}
          error={null}
          onRefresh={vi.fn()}
          onNavigate={handleNavigate}
        />
      );

      // Wait for operational metrics to resolve
      await waitFor(() => {
        expect(screen.getByText('Live Business Operations')).toBeInTheDocument();
      });

      // Verify real metrics are rendered
      expect(screen.getByText('25')).toBeInTheDocument(); // Total inventory
      expect(screen.getByText('12')).toBeInTheDocument(); // Total orders
      expect(screen.getByText('8')).toBeInTheDocument();  // Total invoices
      expect(screen.getByText('18')).toBeInTheDocument(); // Total products

      // Verify Low stock alert table
      expect(screen.getByText(/Low Stock Items \(1\)/i)).toBeInTheDocument();
      expect(screen.getAllByText('Steel Rods').length).toBeGreaterThan(0);

      // Verify Urgent attention pending orders table
      expect(screen.getByText(/Orders Awaiting Approval \(1\)/i)).toBeInTheDocument();
      expect(screen.getAllByText('ORD-2026-001').length).toBeGreaterThan(0);

      // Verify Quick Action buttons trigger navigation
      const quickOrdersBtn = screen.getByRole('button', { name: /^Orders$/i });
      fireEvent.click(quickOrdersBtn);
      expect(handleNavigate).toHaveBeenCalledWith('orders');
    });

    it('displays error notice and retry sync button if operational data query fails', async () => {
      vi.mocked(operationsApi.fetchInventory).mockRejectedValue(new Error('PostgreSQL timeout'));

      render(
        <FoundationDashboard
          health={mockHealthData}
          isLoading={false}
          error={null}
          onRefresh={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Operational Data Sync Notice/i)).toBeInTheDocument();
        expect(screen.getByText(/PostgreSQL timeout/i)).toBeInTheDocument();
      });

      const retryBtn = screen.getByRole('button', { name: /Retry Sync/i });
      expect(retryBtn).toBeInTheDocument();
    });
  });

  describe('InvoicesPage Snapshot Inspection & Pagination', () => {
    it('opens snapshot inspection modal on invoice click', async () => {
      vi.mocked(operationsApi.fetchInvoices).mockResolvedValue({
        items: [
          {
            id: 'inv-101',
            business_id: 'biz-1',
            order_id: 'ord-abc-12345678',
            invoice_number: 'INV-202610-0001',
            amount_due: '1250.00',
            status: 'issued',
            due_date: '2026-11-01',
            created_at: '2026-10-23T08:00:00Z',
            updated_at: '2026-10-23T08:00:00Z',
            customer_snapshot: {
              name: 'Global Corp Ltd',
              email: 'ap@global.corp',
              address: '100 Industrial Parkway',
            },
            line_items_snapshot: [
              { product_name: 'Hydraulic Valve', quantity: 2, unit_price: '625.00', total_price: '1250.00' },
            ],
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      });

      render(<InvoicesPage />);

      await waitFor(() => {
        expect(screen.getByText('INV-202610-0001')).toBeInTheDocument();
      });

      // Click on Details button
      const detailsBtn = screen.getByRole('button', { name: /^Details$/i });
      fireEvent.click(detailsBtn);

      // Verify Snapshot modal opens and displays persisted records
      expect(screen.getByText('Invoice Details: INV-202610-0001')).toBeInTheDocument();
      expect(screen.getByText('Immutable Customer Snapshot')).toBeInTheDocument();
      expect(screen.getByText(/Global Corp Ltd/i)).toBeInTheDocument();
      expect(screen.getByText('Hydraulic Valve')).toBeInTheDocument();
      expect(screen.getAllByText('$1250.00').length).toBeGreaterThan(0);
    });
  });

  describe('OrdersPage Mutation Guard', () => {
    it('prevents duplicate submissions with isActionPending state', async () => {
      vi.mocked(operationsApi.fetchOrders).mockResolvedValue({
        items: [
          {
            id: 'ord-999',
            business_id: 'biz-1',
            order_number: 'ORD-999',
            status: 'pending_approval',
            subtotal: '100.00',
            tax: '0.00',
            total_amount: '100.00',
            created_at: '2026-10-23T10:00:00Z',
            updated_at: '2026-10-23T10:00:00Z',
            items: [],
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      });

      vi.mocked(operationsApi.fetchOrder).mockResolvedValue({
        id: 'ord-999',
        business_id: 'biz-1',
        order_number: 'ORD-999',
        status: 'pending_approval',
        subtotal: '100.00',
        tax: '0.00',
        total_amount: '100.00',
        items: [],
        created_at: '2026-10-23T10:00:00Z',
        updated_at: '2026-10-23T10:00:00Z',
      });

      // Make approveOrder return a slow promise to inspect in-flight mutation state
      vi.mocked(operationsApi.approveOrder).mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                id: 'ord-999',
                business_id: 'biz-1',
                order_number: 'ORD-999',
                status: 'approved',
                subtotal: '100.00',
                tax: '0.00',
                total_amount: '100.00',
                items: [],
                created_at: '2026-10-23T10:00:00Z',
                updated_at: '2026-10-23T10:05:00Z',
              });
            }, 50);
          })
      );

      vi.spyOn(window, 'confirm').mockImplementation(() => true);

      render(<OrdersPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD-999')).toBeInTheDocument();
      });

      // Open manage modal
      const viewBtn = screen.getByRole('button', { name: /View & Manage/i });
      fireEvent.click(viewBtn);

      await waitFor(() => {
        expect(screen.getByText(/Approve & Deduct Stock/i)).toBeInTheDocument();
      });

      const approveBtn = screen.getByRole('button', { name: /Approve & Deduct Stock/i });
      fireEvent.click(approveBtn);

      // Verify button shows pending state and is disabled immediately
      expect(screen.getByText(/Approving\.\.\./i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Approving\.\.\./i })).toBeDisabled();
    });
  });
});

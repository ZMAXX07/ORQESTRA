import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ProductsPage } from '../src/pages/ProductsPage';
import { InventoryPage } from '../src/pages/InventoryPage';
import { CustomersPage } from '../src/pages/CustomersPage';
import { OrdersPage } from '../src/pages/OrdersPage';
import { AIOpsPage } from '../src/pages/AIOpsPage';
import * as operationsApi from '../src/services/operations';

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
        business_name: 'Acme Biz',
        role: 'owner',
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

vi.mock('../src/services/operations', () => ({
  fetchProducts: vi.fn(),
  createProduct: vi.fn(),
  updateProduct: vi.fn(),
  deactivateProduct: vi.fn(),
  fetchInventory: vi.fn(),
  fetchStockMovements: vi.fn(),
  adjustStock: vi.fn(),
  fetchCustomers: vi.fn(),
  createCustomer: vi.fn(),
  updateCustomer: vi.fn(),
  deactivateCustomer: vi.fn(),
  fetchOrders: vi.fn(),
  createOrder: vi.fn(),
  submitOrderForReview: vi.fn(),
  approveOrder: vi.fn(),
  rejectOrder: vi.fn(),
  cancelOrder: vi.fn(),
}));

describe('Phase 3 Operations Frontend Components', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('ProductsPage', () => {
    it('renders products list and handles empty state', async () => {
      vi.mocked(operationsApi.fetchProducts).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
      });

      render(<ProductsPage />);
      expect(screen.getByText('Product Catalog')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText(/No products found/i)).toBeInTheDocument();
      });
    });

    it('renders products with price and SKU when items exist', async () => {
      vi.mocked(operationsApi.fetchProducts).mockResolvedValueOnce({
        items: [
          {
            id: 'prod-1',
            business_id: 'biz-1',
            sku: 'WIDGET-01',
            name: 'Precision Widget',
            description: 'A test widget',
            unit_price: '49.99',
            cost_price: '20.00',
            is_active: true,
            quantity_on_hand: 15,
            reorder_threshold: 5,
            is_low_stock: false,
            created_at: '2026-10-23T00:00:00Z',
            updated_at: '2026-10-23T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      });

      render(<ProductsPage />);

      await waitFor(() => {
        expect(screen.getByText('Precision Widget')).toBeInTheDocument();
        expect(screen.getByText('WIDGET-01')).toBeInTheDocument();
        expect(screen.getByText('$49.99')).toBeInTheDocument();
      });
    });

    it('opens add product modal and submits successfully', async () => {
      vi.mocked(operationsApi.fetchProducts).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
      });
      vi.mocked(operationsApi.createProduct).mockResolvedValueOnce({
        id: 'prod-new',
        business_id: 'biz-1',
        sku: 'NEW-SKU',
        name: 'New Product',
        description: '',
        unit_price: '15.00',
        is_active: true,
        quantity_on_hand: 10,
        reorder_threshold: 5,
        is_low_stock: false,
        created_at: '2026-10-23T00:00:00Z',
        updated_at: '2026-10-23T00:00:00Z',
      });

      render(<ProductsPage />);

      const addBtn = screen.getByRole('button', { name: /New Product/i });
      fireEvent.click(addBtn);

      await waitFor(() => {
        expect(screen.getByText('Create New Product')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText(/SKU \(Unique\)/i), { target: { value: 'NEW-SKU' } });
      fireEvent.change(screen.getByLabelText(/Product Name/i), { target: { value: 'New Product' } });
      fireEvent.change(screen.getByLabelText(/Unit Price \(\$\)/i), { target: { value: '15.00' } });

      const saveBtn = screen.getByRole('button', { name: /Create Product/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(operationsApi.createProduct).toHaveBeenCalledWith(
          'fake-jwt-token',
          'biz-1',
          expect.objectContaining({
            sku: 'NEW-SKU',
            name: 'New Product',
            unit_price: '15.00',
          })
        );
      });
    });
  });

  describe('InventoryPage', () => {
    it('renders inventory with stock levels and low-stock indicators', async () => {
      vi.mocked(operationsApi.fetchInventory).mockResolvedValueOnce({
        items: [
          {
            id: 'inv-1',
            business_id: 'biz-1',
            product_id: 'prod-1',
            product_sku: 'WIDGET-01',
            product_name: 'Precision Widget',
            unit_price: '49.99',
            quantity_on_hand: 3,
            reorder_threshold: 10,
            is_low_stock: true,
            updated_at: '2026-10-23T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_low_stock: 1,
      });

      render(<InventoryPage />);

      await waitFor(() => {
        expect(screen.getByText('Precision Widget')).toBeInTheDocument();
        expect(screen.getByText('3')).toBeInTheDocument();
        expect(screen.getByText('Low Stock Alert')).toBeInTheDocument();
      });
    });

    it('opens stock adjustment modal and validates mandatory reason', async () => {
      vi.mocked(operationsApi.fetchInventory).mockResolvedValueOnce({
        items: [
          {
            id: 'inv-1',
            business_id: 'biz-1',
            product_id: 'prod-1',
            product_sku: 'WIDGET-01',
            product_name: 'Precision Widget',
            unit_price: '49.99',
            quantity_on_hand: 20,
            reorder_threshold: 5,
            is_low_stock: false,
            updated_at: '2026-10-23T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_low_stock: 0,
      });
      vi.mocked(operationsApi.adjustStock).mockResolvedValueOnce({
        inventory_id: 'inv-1',
        product_id: 'prod-1',
        new_quantity: 25,
        movement_id: 'mov-1',
      });

      render(<InventoryPage />);

      await waitFor(() => {
        expect(screen.getByText('Precision Widget')).toBeInTheDocument();
      });

      const rowAdjustBtn = screen.getByRole('button', { name: /Adjust$/i });
      fireEvent.click(rowAdjustBtn);

      await waitFor(() => {
        expect(screen.getByText(/Adjust Stock: Precision Widget/i)).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText(/Quantity Delta \(\+ Add \/ - Deduct\)/i), { target: { value: '5' } });
      fireEvent.change(screen.getByLabelText(/Mandatory Audit Reason \(Required\)/i), {
        target: { value: 'Restocking arrived from supplier' },
      });

      const applyBtn = screen.getByRole('button', { name: /Record Adjustment/i });
      fireEvent.click(applyBtn);

      await waitFor(() => {
        expect(operationsApi.adjustStock).toHaveBeenCalledWith(
          'fake-jwt-token',
          'biz-1',
          expect.objectContaining({
            product_id: 'prod-1',
            quantity_change: 5,
            notes: 'Restocking arrived from supplier',
          })
        );
      });
    });
  });

  describe('CustomersPage', () => {
    it('renders customer list and allows creating customer', async () => {
      vi.mocked(operationsApi.fetchCustomers).mockResolvedValueOnce({
        items: [
          {
            id: 'cust-1',
            business_id: 'biz-1',
            name: 'Acme Corp',
            email: 'procurement@acme.com',
            phone: '+1 555-0192',
            address: '123 Industrial Way',
            notes: 'Preferred client',
            is_active: true,
            created_at: '2026-10-23T00:00:00Z',
            updated_at: '2026-10-23T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      });

      render(<CustomersPage />);

      await waitFor(() => {
        expect(screen.getByText('Acme Corp')).toBeInTheDocument();
        expect(screen.getByText('procurement@acme.com')).toBeInTheDocument();
        expect(screen.getByText('+1 555-0192')).toBeInTheDocument();
      });
    });
  });

  describe('OrdersPage', () => {
    it('renders order list and provides status badges', async () => {
      vi.mocked(operationsApi.fetchOrders).mockResolvedValueOnce({
        items: [
          {
            id: 'ord-1',
            business_id: 'biz-1',
            order_number: 'ORD-20261023-0001',
            customer_id: 'cust-1',
            customer_name: 'Acme Corp',
            status: 'pending_approval',
            subtotal: '100.00',
            tax: '0.00',
            total_amount: '100.00',
            notes: 'Rush delivery',
            created_at: '2026-10-23T00:00:00Z',
            updated_at: '2026-10-23T00:00:00Z',
            items: [
              {
                id: 'item-1',
                order_id: 'ord-1',
                product_id: 'prod-1',
                product_name: 'Precision Widget',
                product_sku: 'WIDGET-01',
                quantity: 2,
                unit_price: '50.00',
                total_price: '100.00',
              },
            ],
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      });

      render(<OrdersPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD-20261023-0001')).toBeInTheDocument();
        expect(screen.getByText('Acme Corp')).toBeInTheDocument();
        expect(screen.getByText('$100.00')).toBeInTheDocument();
        expect(screen.getAllByText('Review Required').length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('Operations Layout, Loading States, and Error Recovery Regression Suite', () => {
    it('ProductsPage handles error state with safe in-table retry button', async () => {
      vi.mocked(operationsApi.fetchProducts)
        .mockRejectedValueOnce(new Error('Network timeout: failed to fetch'))
        .mockResolvedValueOnce({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
        });

      render(<ProductsPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Network timeout: failed to fetch/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });

      // Trigger retry
      fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

      await waitFor(() => {
        expect(operationsApi.fetchProducts).toHaveBeenCalledTimes(2);
        expect(screen.getByText(/No products found/i)).toBeInTheDocument();
      });
    });

    it('InventoryPage handles error state with safe in-table retry button and provides empty action', async () => {
      vi.mocked(operationsApi.fetchInventory)
        .mockRejectedValueOnce(new Error('Database query failure'))
        .mockResolvedValueOnce({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
          total_low_stock: 0,
        });

      render(<InventoryPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Database query failure/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });

      // Trigger retry
      fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

      await waitFor(() => {
        expect(operationsApi.fetchInventory).toHaveBeenCalledTimes(2);
        expect(screen.getByText(/No inventory records found/i)).toBeInTheDocument();
        // Should provide clear action
        expect(screen.getAllByRole('button', { name: /Adjust Stock/i }).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('CustomersPage handles error state with safe in-table retry button', async () => {
      vi.mocked(operationsApi.fetchCustomers)
        .mockRejectedValueOnce(new Error('Connection dropped'))
        .mockResolvedValueOnce({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
        });

      render(<CustomersPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Connection dropped/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });

      // Trigger retry
      fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

      await waitFor(() => {
        expect(operationsApi.fetchCustomers).toHaveBeenCalledTimes(2);
        expect(screen.getByText(/No customer records found/i)).toBeInTheDocument();
      });
    });

    it('OrdersPage handles error state with safe in-table retry button', async () => {
      vi.mocked(operationsApi.fetchOrders)
        .mockRejectedValueOnce(new Error('Gateway 504 error'))
        .mockResolvedValueOnce({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
        });

      render(<OrdersPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Gateway 504 error/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });

      // Trigger retry
      fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

      await waitFor(() => {
        expect(operationsApi.fetchOrders).toHaveBeenCalledTimes(2);
        expect(screen.getByText(/No orders recorded yet/i)).toBeInTheDocument();
      });
    });

    it('AIOpsPage renders message textarea with character counter and disabled state guards', async () => {
      vi.mocked(operationsApi.fetchProducts).mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 100 });
      vi.mocked(operationsApi.fetchCustomers).mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 100 });

      render(<AIOpsPage />);

      expect(screen.getByText('AI Order Extraction & Intake')).toBeInTheDocument();
      expect(screen.getByText('Customer Order Message')).toBeInTheDocument();

      const textarea = screen.getByTestId('ai-intake-textarea');
      const analyzeBtn = screen.getByTestId('ai-analyze-button');

      // Initially empty -> button disabled
      expect(analyzeBtn).toBeDisabled();
      expect(screen.getByText(/0 \/ 4000 characters/i)).toBeInTheDocument();

      // Enter short text (< 5 chars) -> still disabled
      fireEvent.change(textarea, { target: { value: 'Hey' } });
      expect(analyzeBtn).toBeDisabled();
      expect(screen.getByText(/3 \/ 4000 characters/i)).toBeInTheDocument();

      // Enter valid message (>= 5 chars) -> enabled
      fireEvent.change(textarea, { target: { value: 'Please send 10 notebooks tomorrow' } });
      expect(analyzeBtn).not.toBeDisabled();
    });
  });
});

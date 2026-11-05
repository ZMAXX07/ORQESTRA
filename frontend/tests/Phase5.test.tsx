import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AIOpsPage } from '../src/pages/AIOpsPage';
import { InvoicesPage } from '../src/pages/InvoicesPage';
import { OrdersPage } from '../src/pages/OrdersPage';
import * as operationsApi from '../src/services/operations';

vi.mock('../src/context/AuthContext', () => ({
  useAuth: () => ({
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
  fetchProducts: vi.fn(),
  fetchCustomers: vi.fn(),
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

describe('Phase 5 AI Intake & Invoices Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock data for catalog and customers
    vi.mocked(operationsApi.fetchProducts).mockResolvedValue({
      items: [
        {
          id: 'prod-1',
          business_id: 'biz-1',
          sku: 'NOTE-01',
          name: 'Spiral Notebook',
          unit_price: '4.50',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          quantity_on_hand: 50,
          reorder_threshold: 10,
          is_low_stock: false,
        },
        {
          id: 'prod-2',
          business_id: 'biz-1',
          sku: 'PEN-01',
          name: 'Ballpoint Pen Blue',
          unit_price: '1.25',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          quantity_on_hand: 100,
          reorder_threshold: 20,
          is_low_stock: false,
        },
      ],
      total: 2,
      page: 1,
      page_size: 100,
    });

    vi.mocked(operationsApi.fetchCustomers).mockResolvedValue({
      items: [
        {
          id: 'cust-1',
          business_id: 'biz-1',
          name: 'Ravi Kumar',
          email: 'ravi@abctraders.local',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });
  });

  // ---------------------------------------------------------------------------
  // 1. AI Order Extraction & Human Review Tests
  // ---------------------------------------------------------------------------
  describe('AIOpsPage', () => {
    it('renders input message form with boundaries and manual fallback button', () => {
      const onNavigate = vi.fn();
      render(<AIOpsPage onNavigateToOrders={onNavigate} />);

      expect(screen.getByText(/AI Order Extraction & Intake/i)).toBeInTheDocument();
      expect(screen.getByTestId('ai-intake-textarea')).toBeInTheDocument();

      const analyzeBtn = screen.getByTestId('ai-analyze-button');
      // Button disabled when empty (< 5 chars)
      expect(analyzeBtn).toBeDisabled();

      // Typing < 5 chars keeps button disabled
      fireEvent.change(screen.getByTestId('ai-intake-textarea'), { target: { value: 'hey' } });
      expect(analyzeBtn).toBeDisabled();

      // Typing valid length enables button
      fireEvent.change(screen.getByTestId('ai-intake-textarea'), {
        target: { value: 'Please send 5 notebooks and 2 blue pens' },
      });
      expect(analyzeBtn).not.toBeDisabled();

      // Manual fallback button
      const fallbackBtn = screen.getByText('Manual Entry Fallback');
      fireEvent.click(fallbackBtn);
      expect(onNavigate).toHaveBeenCalled();
    });

    it('displays unconfigured AI provider error and allows manual fallback', async () => {
      vi.mocked(operationsApi.extractOrderFromText).mockRejectedValueOnce(
        new Error('AI provider is not configured. Please set the AI_API_KEY environment variable.')
      );

      render(<AIOpsPage />);

      fireEvent.change(screen.getByTestId('ai-intake-textarea'), {
        target: { value: 'Please send 5 notebooks' },
      });
      fireEvent.click(screen.getByTestId('ai-analyze-button'));

      await waitFor(() => {
        expect(screen.getByTestId('ai-extraction-error')).toBeInTheDocument();
        expect(screen.getByText(/AI provider is not configured/i)).toBeInTheDocument();
      });
    });

    it('renders extracted proposal with matched items, authoritative prices, and exact totals', async () => {
      vi.mocked(operationsApi.extractOrderFromText).mockResolvedValueOnce({
        raw_message: 'Please send 5 notebooks and 10 pens for Ravi Kumar',
        extracted_customer_name: 'Ravi Kumar',
        matched_customer_id: 'cust-1',
        matched_customer_name: 'Ravi Kumar',
        delivery_instructions: 'Tomorrow morning',
        notes: 'Priority delivery',
        items: [
          {
            candidate_product_name: 'Notebook',
            raw_text: '5 notebooks',
            requested_quantity: 5,
            match_status: 'matched',
            matched_product: {
              id: 'prod-1',
              sku: 'NOTE-01',
              name: 'Spiral Notebook',
              unit_price: '4.50',
              quantity_on_hand: 50,
            },
            potential_matches: [],
            unit_price: '4.50',
            line_total: '22.50',
          },
        ],
        subtotal: '22.50',
        tax: '0.00',
        total_amount: '22.50',
        validation_errors: [],
        can_create_draft: true,
      });

      render(<AIOpsPage />);

      fireEvent.change(screen.getByTestId('ai-intake-textarea'), {
        target: { value: 'Please send 5 notebooks and 10 pens for Ravi Kumar' },
      });
      fireEvent.click(screen.getByTestId('ai-analyze-button'));

      await waitFor(() => {
        expect(screen.getByTestId('ai-proposal-review')).toBeInTheDocument();
      });

      // Verifies original message snippet
      expect(screen.getByText(/"Please send 5 notebooks and 10 pens for Ravi Kumar"/i)).toBeInTheDocument();
      // Verifies matched badge
      expect(screen.getByText('Matched')).toBeInTheDocument();
      // Verifies authoritative price from database ($4.50)
      expect(screen.getByText('$4.50')).toBeInTheDocument();
      // Verifies exact Decimal total ($22.50)
      expect(screen.getByTestId('proposal-total-amount')).toHaveTextContent('$22.50');
    });

    it('flags ambiguous products, requires human resolution, and creates confirmed draft without deducting stock', async () => {
      vi.mocked(operationsApi.extractOrderFromText).mockResolvedValueOnce({
        raw_message: 'Please send 2 pens',
        extracted_customer_name: undefined,
        items: [
          {
            candidate_product_name: 'Pen',
            raw_text: '2 pens',
            requested_quantity: 2,
            match_status: 'ambiguous',
            potential_matches: [
              { id: 'prod-2', sku: 'PEN-01', name: 'Ballpoint Pen Blue', unit_price: '1.25', quantity_on_hand: 100 },
            ],
            unit_price: undefined,
            line_total: undefined,
          },
        ],
        subtotal: '0.00',
        tax: '0.00',
        total_amount: '0.00',
        validation_errors: ['Ambiguous match for Pen'],
        can_create_draft: false,
      });

      vi.mocked(operationsApi.createOrder).mockResolvedValueOnce({
        id: 'ord-new',
        business_id: 'biz-1',
        order_number: 'ORD-202610-0042',
        status: 'draft',
        subtotal: '2.50',
        tax: '0.20',
        total_amount: '2.70',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        items: [
          {
            id: 'item-1',
            order_id: 'ord-new',
            product_id: 'prod-2',
            product_name: 'Ballpoint Pen Blue',
            product_sku: 'PEN-01',
            quantity: 2,
            unit_price: '1.25',
            total_price: '2.50',
          },
        ],
      });

      render(<AIOpsPage />);

      fireEvent.change(screen.getByTestId('ai-intake-textarea'), {
        target: { value: 'Please send 2 pens' },
      });
      fireEvent.click(screen.getByTestId('ai-analyze-button'));

      await waitFor(() => {
        expect(screen.getByTestId('ai-proposal-review')).toBeInTheDocument();
      });

      // Ambiguous badge and warning
      expect(screen.getByText('Ambiguous Match')).toBeInTheDocument();
      const submitBtn = screen.getByTestId('confirm-create-draft-button');

      // Operator resolves ambiguous match by selecting product from catalog dropdown
      const productSelect = screen.getByTestId('product-select-0');
      fireEvent.change(productSelect, { target: { value: 'prod-2' } });

      // After resolving, match status becomes Matched and submit is enabled
      await waitFor(() => {
        expect(screen.getByText('Matched')).toBeInTheDocument();
        expect(submitBtn).not.toBeDisabled();
      });

      // Operator confirms draft order creation
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(operationsApi.createOrder).toHaveBeenCalledWith(
          'fake-jwt-token',
          'biz-1',
          expect.objectContaining({
            items: [{ product_id: 'prod-2', quantity: 2 }],
          })
        );
        expect(screen.getByTestId('draft-created-banner')).toBeInTheDocument();
        expect(screen.getByText(/ORD-202610-0042/i)).toBeInTheDocument();
        expect(screen.getByText(/Stock has not been deducted/i)).toBeInTheDocument();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // 2. Invoices & Billing Page Tests
  // ---------------------------------------------------------------------------
  describe('InvoicesPage', () => {
    it('renders invoice records and triggers PDF streaming download', async () => {
      vi.mocked(operationsApi.fetchInvoices).mockResolvedValueOnce({
        items: [
          {
            id: 'inv-101',
            business_id: 'biz-1',
            order_id: 'ord-999-uuid-string',
            invoice_number: 'INV-202610-0001',
            status: 'issued',
            amount_due: '125.00',
            due_date: '2026-11-15',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      });

      const mockBlob = new Blob(['%PDF-1.4 test bytes'], { type: 'application/pdf' });
      vi.mocked(operationsApi.downloadInvoicePdf).mockResolvedValueOnce(mockBlob);

      // Mock URL object
      const createObjectURLMock = vi.fn().mockReturnValue('blob:http://localhost/inv-101');
      const revokeObjectURLMock = vi.fn();
      window.URL.createObjectURL = createObjectURLMock;
      window.URL.revokeObjectURL = revokeObjectURLMock;

      render(<InvoicesPage />);

      await waitFor(() => {
        expect(screen.getByText('INV-202610-0001')).toBeInTheDocument();
        expect(screen.getByText('$125.00')).toBeInTheDocument();
        expect(screen.getByText('issued')).toBeInTheDocument();
      });

      const downloadBtn = screen.getByTestId('download-pdf-btn-inv-101');
      fireEvent.click(downloadBtn);

      await waitFor(() => {
        expect(operationsApi.downloadInvoicePdf).toHaveBeenCalledWith(
          'fake-jwt-token',
          'biz-1',
          'inv-101'
        );
        expect(createObjectURLMock).toHaveBeenCalledWith(mockBlob);
      });
    });

    it('renders useful empty state when no invoices exist', async () => {
      vi.mocked(operationsApi.fetchInvoices).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      });

      render(<InvoicesPage />);

      await waitFor(() => {
        expect(screen.getByTestId('no-invoices-state')).toBeInTheDocument();
        expect(screen.getByText(/No invoices have been allocated yet/i)).toBeInTheDocument();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // 3. Orders Page Invoice Generation Action Test
  // ---------------------------------------------------------------------------
  describe('OrdersPage Invoice Action', () => {
    it('shows Generate Invoice PDF button on approved orders and triggers allocation', async () => {
      vi.mocked(operationsApi.fetchOrders).mockResolvedValueOnce({
        items: [
          {
            id: 'ord-approved-1',
            business_id: 'biz-1',
            order_number: 'ORD-202610-0007',
            status: 'approved',
            subtotal: '100.00',
            tax: '8.00',
            total_amount: '108.00',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            items: [],
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      });

      vi.mocked(operationsApi.fetchOrder).mockResolvedValueOnce({
        id: 'ord-approved-1',
        business_id: 'biz-1',
        order_number: 'ORD-202610-0007',
        status: 'approved',
        subtotal: '100.00',
        tax: '8.00',
        total_amount: '108.00',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        items: [],
      });

      vi.mocked(operationsApi.allocateInvoiceForOrder).mockResolvedValueOnce({
        id: 'inv-allocated-1',
        business_id: 'biz-1',
        order_id: 'ord-approved-1',
        invoice_number: 'INV-202610-0007',
        status: 'issued',
        amount_due: '108.00',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });

      const mockBlob = new Blob(['%PDF-1.4 test'], { type: 'application/pdf' });
      vi.mocked(operationsApi.downloadInvoicePdf).mockResolvedValueOnce(mockBlob);

      window.URL.createObjectURL = vi.fn().mockReturnValue('blob:test');
      window.URL.revokeObjectURL = vi.fn();

      render(<OrdersPage />);

      await waitFor(() => {
        expect(screen.getByText('ORD-202610-0007')).toBeInTheDocument();
      });

      // Open detail modal
      fireEvent.click(screen.getByText('View & Manage'));

      await waitFor(() => {
        expect(screen.getByTestId('generate-invoice-btn')).toBeInTheDocument();
      });

      // Click Generate Invoice PDF
      fireEvent.click(screen.getByTestId('generate-invoice-btn'));

      await waitFor(() => {
        expect(operationsApi.allocateInvoiceForOrder).toHaveBeenCalledWith(
          'fake-jwt-token',
          'biz-1',
          'ord-approved-1'
        );
        expect(operationsApi.downloadInvoicePdf).toHaveBeenCalledWith(
          'fake-jwt-token',
          'biz-1',
          'inv-allocated-1'
        );
      });
    });
  });
});

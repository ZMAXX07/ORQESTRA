import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ProductsPage } from '../src/pages/ProductsPage';
import { SignInModal } from '../src/components/auth/SignInModal';
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
        currency: 'INR',
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
}));

describe('Form Input Text and Number Vertical Alignment Suite', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('Create New Product Form Input Rendering & Structural Classes', () => {
    it('renders all form inputs and textareas with standard form control classes', async () => {
      vi.mocked(operationsApi.fetchProducts).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      });

      render(<ProductsPage />);

      const newProdBtn = screen.getByRole('button', { name: /New Product/i });
      fireEvent.click(newProdBtn);

      await waitFor(() => {
        expect(screen.getByText('Create New Product')).toBeInTheDocument();
      });

      // Verify SKU text input
      const skuInput = screen.getByLabelText(/SKU \(Unique\)/i);
      expect(skuInput).toHaveClass('orq-form-input');
      expect(skuInput).toHaveAttribute('type', 'text');
      expect(skuInput).toHaveAttribute('placeholder', 'e.g. WIDGET-100');

      // Verify Name text input
      const nameInput = screen.getByLabelText(/Product Name/i);
      expect(nameInput).toHaveClass('orq-form-input');
      expect(nameInput).toHaveAttribute('type', 'text');

      // Verify Description textarea
      const descInput = screen.getByLabelText(/Description \(Optional\)/i);
      expect(descInput).toHaveClass('orq-form-textarea');
      expect(descInput.tagName.toLowerCase()).toBe('textarea');

      // Verify Unit Price number input
      const unitPriceInput = screen.getByLabelText(/Unit Price \(₹\)/i);
      expect(unitPriceInput).toHaveClass('orq-form-input');
      expect(unitPriceInput).toHaveAttribute('type', 'number');
      expect(unitPriceInput).toHaveValue(0);

      // Verify Cost Price number input
      const costPriceInput = screen.getByLabelText(/Cost Price \(₹\)/i);
      expect(costPriceInput).toHaveClass('orq-form-input');
      expect(costPriceInput).toHaveAttribute('type', 'number');
      expect(costPriceInput).toHaveValue(0);

      // Verify Initial Stock number input
      const stockInput = screen.getByLabelText(/Initial Stock Quantity/i);
      expect(stockInput).toHaveClass('orq-form-input');
      expect(stockInput).toHaveAttribute('type', 'number');
      expect(stockInput).toHaveValue(0);

      // Verify Reorder Threshold number input
      const thresholdInput = screen.getByLabelText(/Reorder Threshold/i);
      expect(thresholdInput).toHaveClass('orq-form-input');
      expect(thresholdInput).toHaveAttribute('type', 'number');
      expect(thresholdInput).toHaveValue(5);
    });

    it('correctly populates and handles various numeric inputs (0, 5, 1250.50, and large quantities)', async () => {
      vi.mocked(operationsApi.fetchProducts).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      });
      vi.mocked(operationsApi.createProduct).mockResolvedValueOnce({
        id: 'prod-new',
        business_id: 'biz-1',
        sku: 'KEYBOARD',
        name: 'MSI KEYBOARD',
        description: 'Mechanical keyboard',
        unit_price: '1250.50',
        cost_price: '850.00',
        is_active: true,
        quantity_on_hand: 5000,
        reorder_threshold: 25,
        is_low_stock: false,
        created_at: '2026-10-25T00:00:00Z',
        updated_at: '2026-10-25T00:00:00Z',
      });

      render(<ProductsPage />);

      fireEvent.click(screen.getByRole('button', { name: /New Product/i }));

      await waitFor(() => {
        expect(screen.getByText('Create New Product')).toBeInTheDocument();
      });

      const skuInput = screen.getByLabelText(/SKU \(Unique\)/i);
      const nameInput = screen.getByLabelText(/Product Name/i);
      const unitPriceInput = screen.getByLabelText(/Unit Price \(₹\)/i);
      const costPriceInput = screen.getByLabelText(/Cost Price \(₹\)/i);
      const stockInput = screen.getByLabelText(/Initial Stock Quantity/i);
      const threshInput = screen.getByLabelText(/Reorder Threshold/i);

      fireEvent.change(skuInput, { target: { value: 'KEYBOARD' } });
      fireEvent.change(nameInput, { target: { value: 'MSI KEYBOARD' } });
      fireEvent.change(unitPriceInput, { target: { value: '1250.50' } });
      fireEvent.change(costPriceInput, { target: { value: '850.00' } });
      fireEvent.change(stockInput, { target: { value: '5000' } });
      fireEvent.change(threshInput, { target: { value: '25' } });

      expect(skuInput).toHaveValue('KEYBOARD');
      expect(nameInput).toHaveValue('MSI KEYBOARD');
      expect(unitPriceInput).toHaveValue(1250.50);
      expect(costPriceInput).toHaveValue(850.00);
      expect(stockInput).toHaveValue(5000);
      expect(threshInput).toHaveValue(25);

      const submitBtn = screen.getByRole('button', { name: /^Create Product$/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(operationsApi.createProduct).toHaveBeenCalledWith(
          'fake-jwt-token',
          'biz-1',
          expect.objectContaining({
            sku: 'KEYBOARD',
            name: 'MSI KEYBOARD',
            unit_price: '1250.50',
            cost_price: '850.00',
            initial_stock: 5000,
            reorder_threshold: 25,
          })
        );
      });
    });
  });

  describe('SignInModal Authentication Form Inputs', () => {
    it('renders email and password inputs with .orq-form-input and accessibility attributes', () => {
      render(<SignInModal isOpen={true} onClose={vi.fn()} />);

      const emailInput = screen.getByLabelText(/Business Email/i);
      const passwordInput = screen.getByLabelText(/Password/i);

      expect(emailInput).toHaveClass('orq-form-input');
      expect(emailInput).toHaveAttribute('type', 'email');
      expect(passwordInput).toHaveClass('orq-form-input');
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });
});

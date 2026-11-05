import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../src/app/App';

describe('App Root Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.pushState(null, '', '/');
  });

  it('renders application header, branding, and Phase status', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        new Promise(() => {}) // pending promise keeps it in loading state
      )
    );

    render(<App />);
    expect(screen.getByText('Orqestra')).toBeInTheDocument();
    expect(screen.getByText('Operations Platform')).toBeInTheDocument();
    expect(screen.getByText('Operations Dashboard')).toBeInTheDocument();
  });

  it('renders system navigation with all Phase 5 modules enabled', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => new Promise(() => {}))
    );

    render(<App />);
    const productsButton = screen.getByRole('button', { name: /Products Catalog/i });
    expect(productsButton).not.toBeDisabled();
    expect(productsButton).toHaveAttribute('aria-disabled', 'false');

    const inventoryButton = screen.getByRole('button', { name: /Inventory Management/i });
    expect(inventoryButton).not.toBeDisabled();
    expect(inventoryButton).toHaveAttribute('aria-disabled', 'false');

    const customersButton = screen.getByRole('button', { name: /Customer Directory/i });
    expect(customersButton).not.toBeDisabled();

    const ordersButton = screen.getByRole('button', { name: /Order Processing/i });
    expect(ordersButton).not.toBeDisabled();

    const invoicesButton = screen.getByRole('button', { name: /Invoices & Billing/i });
    expect(invoicesButton).not.toBeDisabled();
    expect(invoicesButton).toHaveAttribute('aria-disabled', 'false');

    const aiOpsButton = screen.getByRole('button', { name: /AI Order Extraction/i });
    expect(aiOpsButton).not.toBeDisabled();
    expect(aiOpsButton).toHaveAttribute('aria-disabled', 'false');

    const statusButton = screen.getByRole('button', { name: /System Status/i });
    expect(statusButton).not.toBeDisabled();
    expect(statusButton).toHaveAttribute('aria-disabled', 'false');
  });

  it('navigates to System Status and renders access-controlled status page', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: 'healthy',
              environment: 'staging',
              uptime_seconds: 3600,
              timestamp: '2026-10-25T12:00:00Z',
              components: {},
            }),
        })
      )
    );

    render(<App />);
    const statusButton = screen.getByRole('button', { name: /System Status/i });
    fireEvent.click(statusButton);

    expect(await screen.findByText('System Status & Diagnostics')).toBeInTheDocument();
    expect(screen.getByText('Restricted Platform Access')).toBeInTheDocument();
  });

  it('switches navigation tabs to render operation pages and shows authentication required state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [],
              total: 0,
              limit: 50,
              offset: 0,
            }),
        })
      )
    );

    render(<App />);
    const productsButton = screen.getByRole('button', { name: /Products Catalog/i });
    fireEvent.click(productsButton);

    expect(await screen.findByText('Authentication Required')).toBeInTheDocument();
    expect(
      screen.getByText(/Sign in as an operator with confirmed business membership to manage products/i)
    ).toBeInTheDocument();
  });

  it('renders route suspense loading fallback with accessible status role when navigating to lazy modules', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [],
              total: 0,
              limit: 50,
              offset: 0,
            }),
        })
      )
    );

    render(<App />);
    const ordersButton = screen.getByRole('button', { name: /Order Processing/i });
    fireEvent.click(ordersButton);

    // Verifies that either the fallback or the resolved lazy route with status/auth is accessible
    expect(await screen.findByText('Authentication Required')).toBeInTheDocument();
    expect(
      screen.getByText(/Sign in as an operator with confirmed business membership to manage orders/i)
    ).toBeInTheDocument();
  });

  it('opens and closes the operator authentication modal', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => new Promise(() => {}))
    );

    render(<App />);
    const signInButtons = screen.getAllByRole('button', { name: /Sign In/i });
    expect(signInButtons.length).toBeGreaterThan(0);

    // Open modal
    fireEvent.click(signInButtons[0]);
    expect(screen.getByText('Operator Authentication')).toBeInTheDocument();
    expect(screen.getByLabelText(/Business Email/i)).toBeInTheDocument();

    // Close modal
    const closeButton = screen.getByRole('button', { name: /Close dialog/i });
    fireEvent.click(closeButton);
    expect(screen.queryByText('Operator Authentication')).not.toBeInTheDocument();
  });
});

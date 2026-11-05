import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FoundationDashboard } from '../src/pages/FoundationDashboard';
import { AuthProvider } from '../src/context/AuthContext';
import * as operationsApi from '../src/services/operations';
import { HealthResponse } from '../src/types/api';

vi.mock('../src/services/operations', () => ({
  fetchProducts: vi.fn(),
  fetchInventory: vi.fn(),
  fetchOrders: vi.fn(),
  fetchInvoices: vi.fn(),
  fetchStockMovements: vi.fn(),
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
    ai_service: { status: 'not_configured', details: 'AI provider API key (AI_API_KEY) is not configured in backend/.env' },
    authentication: { status: 'operational', details: 'Supabase JWT engine verified' },
  },
};

const renderWithAuth = (ui: React.ReactElement) => {
  return render(<AuthProvider>{ui}</AuthProvider>);
};

describe('FoundationDashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(operationsApi.fetchProducts).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    vi.mocked(operationsApi.fetchInventory).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, total_low_stock: 0 });
    vi.mocked(operationsApi.fetchOrders).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    vi.mocked(operationsApi.fetchInvoices).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    vi.mocked(operationsApi.fetchStockMovements).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  });

  it('renders operational dashboard header, subtitle, and unauthenticated empty state', () => {
    renderWithAuth(
      <FoundationDashboard
        health={mockHealthData}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText('Operational Dashboard')).toBeInTheDocument();
    expect(
      screen.getByText(/Real-time summary of warehouse stock, pending orders, revenue, and store activity./i)
    ).toBeInTheDocument();
    expect(screen.getByText('Business Operations Portal')).toBeInTheDocument();
    expect(screen.getByText('Sign In Required')).toBeInTheDocument();
  });

  it('displays error state when backend connection fails', () => {
    const handleRefresh = vi.fn();
    renderWithAuth(
      <FoundationDashboard
        health={null}
        isLoading={false}
        error="Connection refused on port 8000"
        onRefresh={handleRefresh}
      />
    );

    expect(screen.getByText('Backend Connection Failure')).toBeInTheDocument();
    expect(screen.getByText('Connection refused on port 8000')).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /Retry Check/i });
    fireEvent.click(retryButton);
    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });

  it('triggers onRefresh when clicking Refresh Data button', () => {
    const handleRefresh = vi.fn();
    renderWithAuth(
      <FoundationDashboard
        health={mockHealthData}
        isLoading={false}
        error={null}
        onRefresh={handleRefresh}
      />
    );

    const refreshButton = screen.getByRole('button', { name: /Refresh health diagnostics/i });
    fireEvent.click(refreshButton);
    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SystemStatusPage } from '../src/pages/SystemStatusPage';
import { HealthResponse } from '../src/types/api';
import { AuthContextValue } from '../src/context/AuthContext';

const mockHealthData: HealthResponse = {
  status: 'healthy',
  app_name: 'Orqestra API',
  version: '0.1.0',
  environment: 'development',
  timestamp: '2026-10-23T12:00:00Z',
  uptime_seconds: 3600,
  components: {
    python_runtime: {
      status: 'operational',
      details: 'Python 3.11.0 runtime active',
    },
    fastapi_server: {
      status: 'operational',
      details: 'FastAPI router operational',
    },
    database: {
      status: 'not_connected',
      details: 'Schema migrations defined in supabase/migrations; SUPABASE_URL awaiting local .env configuration',
    },
    ai_service: {
      status: 'not_configured',
      details: 'AI provider API key (AI_API_KEY) is not configured in backend/.env',
    },
    authentication: {
      status: 'not_connected',
      details: 'Auth verification engine active; SUPABASE_JWT_SECRET awaiting local .env configuration',
    },
  },
};

const defaultOwnerAuth: AuthContextValue = {
  session: { access_token: 'mock-jwt-token' } as any,
  user: { id: 'usr-admin-1', email: 'owner@biz.com' } as any,
  serverAuth: {
    status: 'authenticated',
    user: { user_id: 'usr-admin-1', email: 'owner@biz.com' },
    active_business: {
      business_id: 'biz-1',
      business_name: 'Orqestra HQ',
      role: 'owner',
      is_active: true,
    },
    memberships: [
      {
        business_id: 'biz-1',
        business_name: 'Orqestra HQ',
        role: 'owner',
        is_active: true,
      },
    ],
  },
  isLoading: false,
  isConfigured: true,
  authError: null,
  signIn: vi.fn(),
  signOut: vi.fn(),
  refreshServerAuth: vi.fn(),
};

let currentAuthMock: AuthContextValue = { ...defaultOwnerAuth };

vi.mock('../src/context/AuthContext', () => ({
  useAuth: () => currentAuthMock,
}));

describe('SystemStatusPage Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    currentAuthMock = { ...defaultOwnerAuth };
  });

  it('displays verified health diagnostics and component telemetry for authorized owner/admin', () => {
    render(
      <SystemStatusPage
        health={mockHealthData}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText('System Status & Diagnostics')).toBeInTheDocument();
    expect(screen.getByText(/Backend Foundation Connected/i)).toBeInTheDocument();
    expect(screen.getByText('Python 3.11.0 runtime active')).toBeInTheDocument();
    expect(screen.getByText(/Schema migrations defined in supabase\/migrations/i)).toBeInTheDocument();
    expect(screen.getByText(/AI provider API key \(AI_API_KEY\) is not configured in backend\/\.env/i)).toBeInTheDocument();
    expect(screen.getByText('Realtime Live Sync')).toBeInTheDocument();
    expect(screen.getByText('realtime_sync')).toBeInTheDocument();
  });

  it('displays error state when backend connection fails', () => {
    const handleRefresh = vi.fn();
    render(
      <SystemStatusPage
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

  it('triggers onRefresh when clicking Refresh Diagnostics button', () => {
    const handleRefresh = vi.fn();
    render(
      <SystemStatusPage
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

  it('renders architecture boundaries and subsystem diagnostics table for authorized owner/admin', () => {
    render(
      <SystemStatusPage
        health={mockHealthData}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText(/Architecture & Implementation Boundaries/i)).toBeInTheDocument();
    expect(screen.getByText(/Phase 1 through Phase 5.2/i)).toBeInTheDocument();
    expect(screen.getByText(/Phase 6 Quality Hardening \(Active\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Route-level code splitting with optimized bundle loading/i)).toBeInTheDocument();
    expect(screen.getByText(/Strict backend JWT token verification and multi-tenant boundary/i)).toBeInTheDocument();
  });

  it('blocks unauthenticated visitors and renders Restricted Platform Access guard', () => {
    currentAuthMock = {
      ...defaultOwnerAuth,
      session: null,
      user: null,
      serverAuth: null,
    };

    const handleSignIn = vi.fn();
    render(
      <SystemStatusPage
        health={mockHealthData}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
        onOpenSignIn={handleSignIn}
      />
    );

    expect(screen.getByText('Restricted Platform Access')).toBeInTheDocument();
    expect(screen.getByText('Authentication Required')).toBeInTheDocument();
    expect(
      screen.getByText(/System status diagnostics, server telemetry, and architecture inspection are restricted/i)
    ).toBeInTheDocument();

    // Sensitive technical components and boundaries must NOT be rendered
    expect(screen.queryByText('Python 3.11.0 runtime active')).not.toBeInTheDocument();
    expect(screen.queryByText(/Architecture & Implementation Boundaries/i)).not.toBeInTheDocument();

    const signInBtn = screen.getByRole('button', { name: /Sign In as Operator/i });
    fireEvent.click(signInBtn);
    expect(handleSignIn).toHaveBeenCalledTimes(1);
  });

  it('blocks non-admin staff operators and renders Administrative Privilege Required guard', () => {
    currentAuthMock = {
      ...defaultOwnerAuth,
      session: { access_token: 'staff-token' } as any,
      user: { id: 'usr-staff-9', email: 'staff@biz.com' } as any,
      serverAuth: {
        status: 'authenticated',
        user: { user_id: 'usr-staff-9', email: 'staff@biz.com' },
        active_business: {
          business_id: 'biz-1',
          business_name: 'Orqestra HQ',
          role: 'staff',
          is_active: true,
        },
        memberships: [
          {
            business_id: 'biz-1',
            business_name: 'Orqestra HQ',
            role: 'staff',
            is_active: true,
          },
        ],
      },
    };

    render(
      <SystemStatusPage
        health={mockHealthData}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText('Administrative Privilege Required')).toBeInTheDocument();
    expect(screen.getByText('Restricted')).toBeInTheDocument();
    expect(
      screen.getByText(/Subsystem telemetry, server metrics, and architecture boundary verification require Business Owner or Administrator privileges/i)
    ).toBeInTheDocument();

    // Sensitive technical components and boundaries must NOT be rendered for staff
    expect(screen.queryByText('Python 3.11.0 runtime active')).not.toBeInTheDocument();
    expect(screen.queryByText(/Architecture & Implementation Boundaries/i)).not.toBeInTheDocument();
  });
});

import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { RealtimeProvider } from '../context/RealtimeContext';
import { MainLayout } from '../layouts/MainLayout';
import { FoundationDashboard } from '../pages/FoundationDashboard';
import { SignInModal } from '../components/auth/SignInModal';
import { CreateBusinessModal } from '../components/onboarding/CreateBusinessModal';
import { LegalModal } from '../components/legal/LegalModal';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { fetchHealthStatus } from '../services/api';
import { HealthResponse } from '../types/api';
import '../styles/globals.css';

// Route-level lazy loading for operational and AI workspace modules
const ProductsPage = lazy(() =>
  import('../pages/ProductsPage').then((m) => ({ default: m.ProductsPage }))
);
const InventoryPage = lazy(() =>
  import('../pages/InventoryPage').then((m) => ({ default: m.InventoryPage }))
);
const CustomersPage = lazy(() =>
  import('../pages/CustomersPage').then((m) => ({ default: m.CustomersPage }))
);
const OrdersPage = lazy(() =>
  import('../pages/OrdersPage').then((m) => ({ default: m.OrdersPage }))
);
const InvoicesPage = lazy(() =>
  import('../pages/InvoicesPage').then((m) => ({ default: m.InvoicesPage }))
);
const AIOpsPage = lazy(() =>
  import('../pages/AIOpsPage').then((m) => ({ default: m.AIOpsPage }))
);
const SystemStatusPage = lazy(() =>
  import('../pages/SystemStatusPage').then((m) => ({ default: m.SystemStatusPage }))
);

export function RouteLoadingFallback({ label }: { label: string }) {
  return (
    <div className="orq-route-loading" role="status" aria-label={label}>
      <LoadingSpinner label={label} size="lg" />
    </div>
  );
}

function getInitialNavId(): string {
  if (typeof window === 'undefined') return 'foundation';
  const path = window.location.pathname.replace(/^\/+/, '').split('/')[0].toLowerCase();
  const hash = window.location.hash.replace(/^#\/?/, '').split('/')[0].toLowerCase();
  const target = hash || path;
  if (target === 'system-status' || target === 'status') return 'system-status';
  if (['products', 'inventory', 'customers', 'orders', 'invoices', 'ai-ops'].includes(target)) {
    return target;
  }
  return 'foundation';
}

function AppContent() {
  const {
    user,
    session,
    serverAuth,
    isLoading: isAuthLoading,
    isRecoveryMode,
    setIsRecoveryMode,
  } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isSignInOpen, setIsSignInOpen] = useState<boolean>(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState<boolean>(false);
  const [legalModalDoc, setLegalModalDoc] = useState<'terms' | 'privacy' | null>(null);
  const [activeNavId, setActiveNavId] = useState<string>(getInitialNavId);

  const handleNavSelect = useCallback((navId: string) => {
    setActiveNavId(navId);
    if (typeof window !== 'undefined') {
      const targetUrl = navId === 'foundation' ? '/' : `/${navId}`;
      if (window.location.pathname !== targetUrl) {
        window.history.pushState(null, '', targetUrl);
      }
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setActiveNavId(getInitialNavId());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Determine if authenticated operator has no active business membership
  const hasNoBusiness = Boolean(
    user &&
    session &&
    !isAuthLoading &&
    serverAuth !== null &&
    (!serverAuth.active_business || serverAuth.memberships.length === 0)
  );

  const showOnboarding = hasNoBusiness || isOnboardingOpen;

  const loadHealthStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchHealthStatus();
      setHealth(data);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Unable to query backend health probe.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHealthStatus();
  }, [loadHealthStatus]);

  const isBackendHealthy = health ? health.status === 'healthy' : error ? false : null;

  const renderActivePage = () => {
    switch (activeNavId) {
      case 'products':
        return (
          <Suspense fallback={<RouteLoadingFallback label="Loading product catalog..." />}>
            <ProductsPage />
          </Suspense>
        );
      case 'inventory':
        return (
          <Suspense fallback={<RouteLoadingFallback label="Loading stock & inventory..." />}>
            <InventoryPage />
          </Suspense>
        );
      case 'customers':
        return (
          <Suspense fallback={<RouteLoadingFallback label="Loading customer ledger..." />}>
            <CustomersPage />
          </Suspense>
        );
      case 'orders':
        return (
          <Suspense fallback={<RouteLoadingFallback label="Loading orders & transactions..." />}>
            <OrdersPage />
          </Suspense>
        );
      case 'invoices':
        return (
          <Suspense fallback={<RouteLoadingFallback label="Loading invoices & billing..." />}>
            <InvoicesPage />
          </Suspense>
        );
      case 'ai-ops':
        return (
          <Suspense fallback={<RouteLoadingFallback label="Loading AI intake workspace..." />}>
            <AIOpsPage onNavigateToOrders={() => handleNavSelect('orders')} />
          </Suspense>
        );
      case 'system-status':
      case 'status':
        return (
          <Suspense fallback={<RouteLoadingFallback label="Loading system status & diagnostics..." />}>
            <SystemStatusPage
              health={health}
              isLoading={isLoading}
              error={error}
              onRefresh={loadHealthStatus}
              onOpenSignIn={() => setIsSignInOpen(true)}
              onOpenOnboarding={() => setIsOnboardingOpen(true)}
            />
          </Suspense>
        );
      case 'foundation':
      default:
        return (
          <FoundationDashboard
            health={health}
            isLoading={isLoading}
            error={error}
            onRefresh={loadHealthStatus}
            onOpenSignIn={() => setIsSignInOpen(true)}
            onOpenOnboarding={() => setIsOnboardingOpen(true)}
            onNavigate={handleNavSelect}
          />
        );
    }
  };

  return (
    <>
      <MainLayout
        isBackendHealthy={isBackendHealthy}
        environmentName={health?.environment ? `Env: ${health.environment}` : 'Phase 5 AI & Invoices'}
        activeNavId={activeNavId}
        onNavSelect={handleNavSelect}
        onOpenSignIn={() => setIsSignInOpen(true)}
        onOpenStatus={() => handleNavSelect('system-status')}
        onOpenLegal={(doc) => setLegalModalDoc(doc)}
      >
        {renderActivePage()}
      </MainLayout>
      <SignInModal
        isOpen={isSignInOpen || Boolean(isRecoveryMode)}
        onClose={() => {
          setIsSignInOpen(false);
          setIsRecoveryMode?.(false);
        }}
        initialMode={isRecoveryMode ? 'recovery' : 'signin'}
      />
      <CreateBusinessModal
        isOpen={showOnboarding}
        onSuccess={() => setIsOnboardingOpen(false)}
      />
      <LegalModal
        isOpen={legalModalDoc !== null}
        onClose={() => setLegalModalDoc(null)}
        initialDoc={legalModalDoc || 'terms'}
      />
    </>
  );
}

export function App() {
  return (
    <AuthProvider>
      <RealtimeProvider>
        <AppContent />
      </RealtimeProvider>
    </AuthProvider>
  );
}

export default App;

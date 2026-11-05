import React, { useState, useEffect, useCallback } from 'react';
import { HealthResponse } from '../types/api';
import {
  InventoryItem,
  Order,
  StockMovement,
} from '../types/operations';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Alert } from '../components/common/Alert';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { ErrorState } from '../components/feedback/ErrorState';
import {
  RefreshIcon,
  ShieldCheckIcon,
  ClockIcon,
  LayersIcon,
  PackageIcon,
  ShoppingCartIcon,
  AlertTriangleIcon,
  UsersIcon,
} from '../components/icons/Icons';
import { formatCurrency } from '../utils/currencies';
import { useAuth } from '../context/AuthContext';
import {
  fetchInventory,
  fetchOrders,
  fetchStockMovements,
  fetchInvoices,
  fetchProducts,
} from '../services/operations';
import './FoundationDashboard.css';

export interface FoundationDashboardProps {
  health: HealthResponse | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onOpenSignIn?: () => void;
  onOpenOnboarding?: () => void;
  onNavigate?: (navId: string) => void;
}

export const FoundationDashboard: React.FC<FoundationDashboardProps> = ({
  health,
  isLoading,
  error,
  onRefresh,
  onOpenSignIn,
  onOpenOnboarding,
  onNavigate,
}) => {
  const { user, session, serverAuth } = useAuth();
  const businessId = serverAuth?.active_business?.business_id;
  const businessName = serverAuth?.active_business?.business_name;
  const businessRole = serverAuth?.active_business?.role;
  const activeCurrency = serverAuth?.active_business?.currency || 'USD';
  const token = session?.access_token;

  // Operational Data State
  const [isOpsLoading, setIsOpsLoading] = useState<boolean>(false);
  const [opsError, setOpsError] = useState<string | null>(null);

  // Business Operational Metrics
  const [totalProducts, setTotalProducts] = useState<number>(0);
  const [totalInventory, setTotalInventory] = useState<number>(0);
  const [lowStockCount, setLowStockCount] = useState<number>(0);
  const [lowStockItems, setLowStockItems] = useState<InventoryItem[]>([]);
  const [totalOrders, setTotalOrders] = useState<number>(0);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [pendingOrders, setPendingOrders] = useState<Order[]>([]);
  const [recentMovements, setRecentMovements] = useState<StockMovement[]>([]);
  const [totalInvoices, setTotalInvoices] = useState<number>(0);

  const loadOperationalMetrics = useCallback(async () => {
    if (!token || !businessId) {
      return;
    }

    setIsOpsLoading(true);
    setOpsError(null);

    try {
      const results = await Promise.allSettled([
        fetchProducts(token, businessId, { page_size: 1 }),
        fetchInventory(token, businessId, { page_size: 1 }),
        fetchInventory(token, businessId, { low_stock_only: true, page_size: 5 }),
        fetchOrders(token, businessId, { page_size: 5 }),
        fetchOrders(token, businessId, { status: 'pending_approval', page_size: 5 }),
        fetchStockMovements(token, businessId, { page_size: 5 }),
        fetchInvoices(token, businessId, { page_size: 1 }),
      ]);

      const [
        prodsRes,
        invRes,
        lowStockRes,
        ordersRes,
        pendingRes,
        movementsRes,
        invoicesRes,
      ] = results;

      if (prodsRes.status === 'fulfilled') setTotalProducts(prodsRes.value.total);
      if (invRes.status === 'fulfilled') {
        setTotalInventory(invRes.value.total);
        setLowStockCount(invRes.value.total_low_stock);
      }
      if (lowStockRes.status === 'fulfilled') setLowStockItems(lowStockRes.value.items);
      if (ordersRes.status === 'fulfilled') {
        setTotalOrders(ordersRes.value.total);
        setRecentOrders(ordersRes.value.items);
      }
      if (pendingRes.status === 'fulfilled') setPendingOrders(pendingRes.value.items);
      if (movementsRes.status === 'fulfilled') setRecentMovements(movementsRes.value.items);
      if (invoicesRes.status === 'fulfilled') setTotalInvoices(invoicesRes.value.total);

      const rejected = results.find(
        (r): r is PromiseRejectedResult => r.status === 'rejected'
      );
      if (rejected) {
        const rawMsg =
          rejected.reason instanceof Error
            ? rejected.reason.message
            : 'Unable to query operational business data.';
        const friendlyMsg =
          rawMsg === 'Failed to fetch'
            ? 'Unable to connect to Orqestra backend. Verify server is running and reachable.'
            : rawMsg;
        setOpsError(friendlyMsg);
      }
    } catch (err: unknown) {
      const rawMsg = err instanceof Error ? err.message : 'Unable to query operational business data.';
      const friendlyMsg =
        rawMsg === 'Failed to fetch'
          ? 'Unable to connect to Orqestra backend. Verify server is running and reachable.'
          : rawMsg;
      setOpsError(friendlyMsg);
    } finally {
      setIsOpsLoading(false);
    }
  }, [token, businessId]);

  useEffect(() => {
    if (token && businessId) {
      loadOperationalMetrics();
    }
  }, [token, businessId, loadOperationalMetrics]);

  const handleRefreshAll = () => {
    onRefresh();
    if (token && businessId) {
      loadOperationalMetrics();
    }
  };

  return (
    <div className="orq-dashboard" data-testid="operational-dashboard">
      {/* Business Dashboard Header */}
      <header className="orq-dashboard-header">
        <div>
          <div className="orq-dashboard-title-wrap">
            <h1 className="orq-dashboard-title">Operational Dashboard</h1>
            {businessName && (
              <Badge variant="operational">
                <span>{businessName}</span>
              </Badge>
            )}
          </div>
          <p className="orq-dashboard-subtitle">
            Real-time summary of warehouse stock, pending orders, revenue, and store activity.
          </p>
        </div>
        <div className="orq-dashboard-actions">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRefreshAll}
            isLoading={isLoading || isOpsLoading}
            aria-label="Refresh health diagnostics"
          >
            <RefreshIcon size={14} />
            <span>Refresh Data</span>
          </Button>
        </div>
      </header>

      {/* Backend Connection Error Feedback */}
      {isLoading && !health && (
        <LoadingSpinner label="Connecting to Orqestra business services..." size="lg" />
      )}

      {error && (
        <ErrorState
          title="Backend Connection Failure"
          message={error}
          onRetry={onRefresh}
          isRetrying={isLoading}
        />
      )}

      {/* Operational Sync Error Notice */}
      {opsError && (
        <Alert type="warning" title="Operational Data Sync Notice">
          {opsError}{' '}
          <button
            type="button"
            className="orq-ops-card-link"
            onClick={loadOperationalMetrics}
            style={{ marginLeft: 'var(--space-2)' }}
          >
            Retry Sync
          </button>
        </Alert>
      )}

      {/* Operator Session State for Unauthenticated / New Businesses */}
      {!user && (
        <Card>
          <CardHeader>
            <CardTitle>Business Operations Portal</CardTitle>
            <Badge variant="neutral">Sign In Required</Badge>
          </CardHeader>
          <CardBody>
            <p className="orq-auth-notice">
              Sign in with your authorized operator credentials to access inventory controls, approve orders, and manage sales.
            </p>
            {onOpenSignIn && (
              <div className="orq-auth-actions">
                <Button variant="primary" size="sm" onClick={onOpenSignIn}>
                  <UsersIcon size={14} />
                  <span>Sign In as Operator</span>
                </Button>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {user && !businessId && (
        <Card>
          <CardHeader>
            <CardTitle>Welcome to Orqestra</CardTitle>
            <Badge variant="info">Setup Required</Badge>
          </CardHeader>
          <CardBody>
            <p className="orq-auth-notice">
              You are signed in as <strong>{user.email}</strong>. Create a business workspace to begin orchestrating operations.
            </p>
            {onOpenOnboarding && (
              <div className="orq-auth-actions">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onOpenOnboarding}
                  data-testid="onboarding-trigger-btn"
                >
                  <span>Create Your Business</span>
                  <span aria-hidden="true">→</span>
                </Button>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Quick Operational Shortcuts Bar */}
      {user && businessId && onNavigate && (
        <div className="orq-quick-actions-bar" role="navigation" aria-label="Quick Operational Actions">
          <span className="orq-quick-actions-label">Quick Actions:</span>
          <Button variant="outline" size="sm" onClick={() => onNavigate('orders')}>
            <ShoppingCartIcon size={14} />
            <span>Orders</span>
          </Button>
          <Button variant="outline" size="sm" onClick={() => onNavigate('inventory')}>
            <LayersIcon size={14} />
            <span>Inventory</span>
          </Button>
          <Button variant="outline" size="sm" onClick={() => onNavigate('products')}>
            <PackageIcon size={14} />
            <span>Products</span>
          </Button>
          <Button variant="outline" size="sm" onClick={() => onNavigate('ai-ops')}>
            <ShieldCheckIcon size={14} />
            <span>AI Intake</span>
          </Button>
          <Button variant="outline" size="sm" onClick={() => onNavigate('invoices')}>
            <ClockIcon size={14} />
            <span>Invoices</span>
          </Button>
          <Button variant="outline" size="sm" onClick={() => onNavigate('customers')}>
            <UsersIcon size={14} />
            <span>Customers</span>
          </Button>
        </div>
      )}

      {/* Key Business Operations Overview Cards */}
      {user && businessId && (
        <section aria-labelledby="section-ops-overview">
          <h2 id="section-ops-overview" className="orq-section-heading">
            Live Business Operations
          </h2>
          <div className="orq-ops-overview-grid">
            <Card>
              <CardBody>
                <div className="orq-ops-card-header">
                  <span className="orq-ops-card-title">
                    <LayersIcon size={14} />
                    <span>Inventory Levels</span>
                  </span>
                  {lowStockCount > 0 ? (
                    <Badge variant="degraded">{lowStockCount} Low Stock</Badge>
                  ) : (
                    <Badge variant="operational">Optimal</Badge>
                  )}
                </div>
                <div className="orq-ops-card-stat">{totalInventory}</div>
                <div className="orq-ops-progress-track" aria-hidden="true">
                  <div
                    className="orq-ops-progress-bar orq-ops-progress-bar--periwinkle"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(15, totalInventory > 0 ? (totalInventory / (totalInventory + lowStockCount)) * 100 : 40)
                      )}%`,
                    }}
                  />
                </div>
                <div className="orq-ops-card-meta">
                  <span className="orq-ops-card-meta-text">Tracked SKUs in warehouse</span>
                  {onNavigate && (
                    <button
                      type="button"
                      className="orq-ops-card-link"
                      onClick={() => onNavigate('inventory')}
                    >
                      Manage
                    </button>
                  )}
                </div>
              </CardBody>
            </Card>

            <Card className="orq-card--gradient">
              <CardBody>
                <div className="orq-ops-card-header">
                  <span className="orq-ops-card-title">
                    <ShoppingCartIcon size={14} />
                    <span>Order Pipeline</span>
                  </span>
                  {pendingOrders.length > 0 ? (
                    <Badge variant="degraded">{pendingOrders.length} Pending Review</Badge>
                  ) : (
                    <Badge variant="neutral">Normal</Badge>
                  )}
                </div>
                <div className="orq-ops-card-stat">{totalOrders}</div>
                <div className="orq-ops-progress-track" aria-hidden="true">
                  <div
                    className="orq-ops-progress-bar orq-ops-progress-bar--rose"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(20, totalOrders > 0 ? ((totalOrders - pendingOrders.length) / totalOrders) * 100 : 50)
                      )}%`,
                    }}
                  />
                </div>
                <div className="orq-ops-card-meta">
                  <span className="orq-ops-card-meta-text">Total lifetime orders</span>
                  {onNavigate && (
                    <button
                      type="button"
                      className="orq-ops-card-link"
                      onClick={() => onNavigate('orders')}
                    >
                      View Pipeline
                    </button>
                  )}
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <div className="orq-ops-card-header">
                  <span className="orq-ops-card-title">
                    <ClockIcon size={14} />
                    <span>Invoices Issued</span>
                  </span>
                  <Badge variant="operational">Sequential</Badge>
                </div>
                <div className="orq-ops-card-stat">{totalInvoices}</div>
                <div className="orq-ops-progress-track" aria-hidden="true">
                  <div
                    className="orq-ops-progress-bar orq-ops-progress-bar--emerald"
                    style={{ width: `${Math.min(100, Math.max(25, totalInvoices > 0 ? 80 : 35))}%` }}
                  />
                </div>
                <div className="orq-ops-card-meta">
                  <span className="orq-ops-card-meta-text">Immutable snapshots allocated</span>
                  {onNavigate && (
                    <button
                      type="button"
                      className="orq-ops-card-link"
                      onClick={() => onNavigate('invoices')}
                    >
                      View Invoices
                    </button>
                  )}
                </div>
              </CardBody>
            </Card>

            <Card className="orq-card--gradient">
              <CardBody>
                <div className="orq-ops-card-header">
                  <span className="orq-ops-card-title">
                    <PackageIcon size={14} />
                    <span>Active Catalog</span>
                  </span>
                  <Badge variant="info">Active</Badge>
                </div>
                <div className="orq-ops-card-stat">{totalProducts}</div>
                <div className="orq-ops-progress-track" aria-hidden="true">
                  <div
                    className="orq-ops-progress-bar orq-ops-progress-bar--periwinkle"
                    style={{ width: `${Math.min(100, Math.max(30, totalProducts > 0 ? 75 : 45))}%` }}
                  />
                </div>
                <div className="orq-ops-card-meta">
                  <span className="orq-ops-card-meta-text">Registered sales items</span>
                  {onNavigate && (
                    <button
                      type="button"
                      className="orq-ops-card-link"
                      onClick={() => onNavigate('products')}
                    >
                      Catalog
                    </button>
                  )}
                </div>
              </CardBody>
            </Card>
          </div>
        </section>
      )}

      {/* Urgent Attention Section: Low Stock & Orders Awaiting Approval */}
      {user && businessId && (lowStockItems.length > 0 || pendingOrders.length > 0) && (
        <section aria-labelledby="section-urgent-attention">
          <h2 id="section-urgent-attention" className="orq-section-heading">
            Operational Attention Needed
          </h2>
          <div className="orq-dashboard-split-grid">
            {lowStockItems.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>
                    <AlertTriangleIcon size={16} style={{ color: 'var(--color-warning-text)' }} />
                    <span>Low Stock Items ({lowStockCount})</span>
                  </CardTitle>
                  {onNavigate && (
                    <Button variant="outline" size="sm" onClick={() => onNavigate('inventory')}>
                      Adjust Stock
                    </Button>
                  )}
                </CardHeader>
                <CardBody>
                  <table className="orq-table-compact" aria-label="Low stock items alert table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>SKU</th>
                        <th>On Hand</th>
                        <th>Threshold</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lowStockItems.map((item) => (
                        <tr key={item.id}>
                          <td><strong>{item.product_name}</strong></td>
                          <td><span className="orq-cell-mono">{item.product_sku}</span></td>
                          <td>
                            <Badge variant="degraded">{item.quantity_on_hand}</Badge>
                          </td>
                          <td>{item.reorder_threshold}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardBody>
              </Card>
            )}

            {pendingOrders.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>
                    <ShoppingCartIcon size={16} />
                    <span>Orders Awaiting Approval ({pendingOrders.length})</span>
                  </CardTitle>
                  {onNavigate && (
                    <Button variant="outline" size="sm" onClick={() => onNavigate('orders')}>
                      Review Orders
                    </Button>
                  )}
                </CardHeader>
                <CardBody>
                  <table className="orq-table-compact" aria-label="Pending orders alert table">
                    <thead>
                      <tr>
                        <th>Order #</th>
                        <th>Customer</th>
                        <th>Amount</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pendingOrders.map((ord) => (
                        <tr key={ord.id}>
                          <td><strong>{ord.order_number}</strong></td>
                          <td>{ord.customer_name || 'Anonymous'}</td>
                          <td>{formatCurrency(ord.total_amount, activeCurrency, { useGrouping: false })}</td>
                          <td><Badge variant="degraded">Review</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardBody>
              </Card>
            )}
          </div>
        </section>
      )}

      {/* Recent Activity: Orders and Stock Adjustments */}
      {user && businessId && (
        <section aria-labelledby="section-recent-activity">
          <h2 id="section-recent-activity" className="orq-section-heading">
            Recent Activity & Inventory Movements
          </h2>
          <div className="orq-dashboard-split-grid">
            <Card>
              <CardHeader>
                <CardTitle>Recent Orders</CardTitle>
                {onNavigate && (
                  <button
                    type="button"
                    className="orq-ops-card-link"
                    onClick={() => onNavigate('orders')}
                  >
                    View All Orders
                  </button>
                )}
              </CardHeader>
              <CardBody>
                {recentOrders.length === 0 ? (
                  <p className="orq-empty-activity">No orders recorded yet. Create an order or use AI Intake to start.</p>
                ) : (
                  <table className="orq-table-compact" aria-label="Recent orders table">
                    <thead>
                      <tr>
                        <th>Order</th>
                        <th>Customer</th>
                        <th>Amount</th>
                        <th>Status</th>
                        <th>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentOrders.map((ord) => (
                        <tr key={ord.id}>
                          <td><strong>{ord.order_number}</strong></td>
                          <td>{ord.customer_name || 'Anonymous'}</td>
                          <td>{formatCurrency(ord.total_amount, activeCurrency, { useGrouping: false })}</td>
                          <td>
                            <Badge
                              variant={
                                ord.status === 'approved' || ord.status === 'fulfilled'
                                  ? 'operational'
                                  : ord.status === 'pending_approval'
                                  ? 'degraded'
                                  : 'neutral'
                              }
                            >
                              {ord.status}
                            </Badge>
                          </td>
                          <td style={{ color: 'var(--color-text-muted)' }}>
                            {new Date(ord.created_at).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Recent Stock Movements</CardTitle>
                {onNavigate && (
                  <button
                    type="button"
                    className="orq-ops-card-link"
                    onClick={() => onNavigate('inventory')}
                  >
                    Movement Ledger
                  </button>
                )}
              </CardHeader>
              <CardBody>
                {recentMovements.length === 0 ? (
                  <p className="orq-empty-activity">No stock adjustments recorded yet.</p>
                ) : (
                  <table className="orq-table-compact" aria-label="Recent stock movements table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Change</th>
                        <th>Type</th>
                        <th>Reason</th>
                        <th>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentMovements.map((m) => (
                        <tr key={m.id}>
                          <td><strong>{m.product_name || 'Product'}</strong></td>
                          <td>
                            <span
                              className={
                                m.quantity_change > 0
                                  ? 'orq-movement-delta-pos'
                                  : 'orq-movement-delta-neg'
                              }
                            >
                              {m.quantity_change > 0 ? `+${m.quantity_change}` : m.quantity_change}
                            </span>
                          </td>
                          <td>
                            <Badge variant="neutral">{m.movement_type}</Badge>
                          </td>
                          <td style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {m.notes || 'Routine update'}
                          </td>
                          <td style={{ color: 'var(--color-text-muted)' }}>
                            {new Date(m.created_at).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardBody>
            </Card>
          </div>
        </section>
      )}

      {/* Active Workspace Details (Clean, Business-Facing) */}
      {user && businessId && (
        <section aria-labelledby="section-workspace-details">
          <Card>
            <CardHeader>
              <CardTitle id="section-workspace-details">Business Workspace Details</CardTitle>
              <Badge variant="operational">Active Session</Badge>
            </CardHeader>
            <CardBody>
              <div className="orq-auth-grid">
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Business Name</span>
                  <span className="orq-auth-value"><strong>{businessName}</strong></span>
                </div>
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Operating Currency</span>
                  <span className="orq-auth-value">{activeCurrency}</span>
                </div>
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Operator Account</span>
                  <span className="orq-auth-value">{user.email ?? 'Authenticated'}</span>
                </div>
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Workspace Role</span>
                  <span className="orq-auth-value">
                    <Badge variant="info">{(businessRole || 'OWNER').toUpperCase()}</Badge>
                  </span>
                </div>
              </div>
            </CardBody>
          </Card>
        </section>
      )}
    </div>
  );
};

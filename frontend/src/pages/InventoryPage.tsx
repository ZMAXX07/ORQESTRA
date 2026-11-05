import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRealtimeTable } from '../hooks/useRealtimeTable';
import {
  fetchInventory,
  adjustStock,
  fetchStockMovements,
  fetchProducts,
} from '../services/operations';
import {
  InventoryItem,
  Product,
  StockAdjustmentInput,
  StockMovement,
} from '../types/operations';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Pagination } from '../components/common/Pagination';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import {
  AlertCircleIcon,
  CheckIcon,
  ClockIcon,
  PackageIcon,
  PlusIcon,
  SearchIcon,
  XIcon,
} from '../components/icons/Icons';
import './Operations.css';

export const InventoryPage: React.FC = () => {
  const { session, serverAuth, isLoading: isAuthLoading } = useAuth();
  const businessId = serverAuth?.active_business?.business_id;
  const token = session?.access_token;
  const userRole = serverAuth?.active_business?.role;
  const canManage = userRole === 'owner' || userRole === 'admin';

  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [lowStockCount, setLowStockCount] = useState<number>(0);
  const [lowStockOnly, setLowStockOnly] = useState<boolean>(false);
  const [search, setSearch] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Stock Adjustment Modal
  const [isAdjustOpen, setIsAdjustOpen] = useState<boolean>(false);
  const [targetProduct, setTargetProduct] = useState<InventoryItem | null>(null);
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [adjustProductId, setAdjustProductId] = useState<string>('');
  const [adjustDelta, setAdjustDelta] = useState<number>(1);
  const [adjustType, setAdjustType] = useState<'adjustment' | 'restock' | 'return'>('adjustment');
  const [adjustNotes, setAdjustNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [adjustError, setAdjustError] = useState<string | null>(null);

  // History Drawer/Modal
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [historyItems, setHistoryItems] = useState<StockMovement[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [historyProductId, setHistoryProductId] = useState<string | null>(null);

  const loadInventory = useCallback(async () => {
    if (!token || !businessId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchInventory(token, businessId, {
        search: search.trim() || undefined,
        low_stock_only: lowStockOnly,
        page,
        page_size: 20,
      });
      setInventory(data.items);
      setTotal(data.total);
      setLowStockCount(data.total_low_stock);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load inventory');
    } finally {
      setIsLoading(false);
    }
  }, [token, businessId, search, lowStockOnly, page]);

  useEffect(() => {
    loadInventory();
  }, [loadInventory]);

  // Realtime updates reconciliation for inventory & stock movements
  useRealtimeTable<InventoryItem>({
    table: 'inventory',
    onEvent: () => {
      loadInventory();
    },
    onReconcile: () => {
      loadInventory();
    },
  });

  useRealtimeTable<StockMovement>({
    table: 'stock_movements',
    onEvent: () => {
      loadInventory();
    },
  });

  const handleOpenAdjust = async (item?: InventoryItem) => {
    if (item) {
      setTargetProduct(item);
      setAdjustProductId(item.product_id);
    } else {
      setTargetProduct(null);
      setAdjustProductId('');
      if (token && businessId) {
        try {
          const prods = await fetchProducts(token, businessId, { is_active: true, page_size: 100 });
          setAllProducts(prods.items);
          if (prods.items.length > 0) {
            setAdjustProductId(prods.items[0].id);
          }
        } catch {
          // ignore
        }
      }
    }
    setAdjustDelta(1);
    setAdjustType('adjustment');
    setAdjustNotes('');
    setAdjustError(null);
    setIsAdjustOpen(true);
  };

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId) return;

    if (!adjustProductId) {
      setAdjustError('Please select a product');
      return;
    }

    if (adjustDelta === 0) {
      setAdjustError('Quantity change must be non-zero');
      return;
    }

    if (!adjustNotes.trim() || adjustNotes.trim().length < 3) {
      setAdjustError('A mandatory reason (at least 3 characters) is required for stock changes');
      return;
    }

    setIsSubmitting(true);
    setAdjustError(null);

    try {
      const payload: StockAdjustmentInput = {
        product_id: adjustProductId,
        quantity_change: adjustDelta,
        movement_type: adjustType,
        notes: adjustNotes.trim(),
      };

      const result = await adjustStock(token, businessId, payload);
      setIsAdjustOpen(false);
      setSuccessMsg(
        `Stock updated: New quantity is ${result.new_quantity} units.`
      );
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadInventory();
    } catch (err: unknown) {
      setAdjustError(err instanceof Error ? err.message : 'Stock adjustment failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenHistory = async (productId?: string) => {
    if (!token || !businessId) return;
    setIsHistoryOpen(true);
    setHistoryLoading(true);
    setHistoryProductId(productId || null);
    try {
      const data = await fetchStockMovements(token, businessId, {
        product_id: productId,
        page_size: 50,
      });
      setHistoryItems(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load stock movements');
    } finally {
      setHistoryLoading(false);
    }
  };

  if (isAuthLoading) {
    return (
      <div className="orq-ops-container">
        <div className="orq-ops-table-loading" style={{ minHeight: '300px' }}>
          <LoadingSpinner size="md" label="Verifying session and permissions..." />
        </div>
      </div>
    );
  }

  if (!businessId) {
    return (
      <div className="orq-ops-container">
        <Card className="orq-ops-empty">
          <PackageIcon size={32} />
          <div className="orq-ops-empty-title">Authentication Required</div>
          <p className="orq-ops-empty-desc">
            Sign in as an operator with confirmed business membership to manage inventory.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="orq-ops-container">
      <div className="orq-ops-header">
        <div>
          <h1 className="orq-ops-title">Inventory & Stock Control</h1>
          <p className="orq-ops-subtitle">
            Monitor real-time on-hand quantities, reorder thresholds, and perform audited stock adjustments.
          </p>
        </div>
        <div className="orq-ops-header-actions">
          <Button variant="secondary" onClick={() => handleOpenHistory()}>
            <ClockIcon size={16} />
            <span>Movement Ledger</span>
          </Button>
          {canManage && (
            <Button variant="primary" onClick={() => handleOpenAdjust()}>
              <PlusIcon size={16} />
              <span>Adjust Stock</span>
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="orq-ops-error-banner" role="alert">
          <AlertCircleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="orq-ops-success-banner" role="status">
          <CheckIcon size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      <div className="orq-ops-toolbar">
        <div className="orq-ops-search-box">
          <SearchIcon size={16} />
          <input
            type="text"
            className="orq-ops-search-input"
            placeholder="Search products or SKU..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="orq-ops-filters">
          <button
            type="button"
            className={`orq-ops-filter-btn ${!lowStockOnly ? 'is-active' : ''}`}
            onClick={() => setLowStockOnly(false)}
          >
            All Stock ({total})
          </button>
          <button
            type="button"
            className={`orq-ops-filter-btn ${lowStockOnly ? 'is-active' : ''}`}
            onClick={() => setLowStockOnly(true)}
          >
            Low Stock Alerts ({lowStockCount})
          </button>
          <button
            type="button"
            className="orq-btn-sm"
            onClick={() => loadInventory()}
            disabled={isLoading}
            title="Refresh inventory records"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="orq-ops-table-wrapper">
        <table className="orq-ops-table" aria-label="Inventory table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Product Title</th>
              <th>On Hand</th>
              <th>Threshold</th>
              <th>Alert State</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-loading">
                    <LoadingSpinner size="sm" label="Loading stock data..." />
                  </div>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-error">
                    <AlertCircleIcon size={20} />
                    <p>{error}</p>
                    <Button variant="secondary" size="sm" onClick={() => loadInventory()}>
                      Retry
                    </Button>
                  </div>
                </td>
              </tr>
            ) : inventory.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-empty">
                    <p>
                      {search.trim()
                        ? `No products match "${search.trim()}".`
                        : lowStockOnly
                        ? 'No products are currently at or below their reorder threshold.'
                        : 'No inventory records found. Add catalog products to begin tracking stock levels.'}
                    </p>
                    {lowStockOnly ? (
                      <Button variant="secondary" size="sm" onClick={() => setLowStockOnly(false)}>
                        View All Stock
                      </Button>
                    ) : canManage && (
                      <Button variant="primary" size="sm" onClick={() => handleOpenAdjust()}>
                        <PlusIcon size={14} />
                        <span>Adjust Stock</span>
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              inventory.map((inv) => (
                <tr key={inv.id}>
                  <td>
                    <span className="orq-cell-mono">{inv.product_sku}</span>
                  </td>
                  <td>
                    <strong>{inv.product_name}</strong>
                  </td>
                  <td>
                    <span style={{ fontSize: '15px', fontWeight: 'bold' }}>
                      {inv.quantity_on_hand}
                    </span>
                  </td>
                  <td>
                    <span className="orq-cell-mono">{inv.reorder_threshold} units</span>
                  </td>
                  <td>
                    {inv.is_low_stock ? (
                      <Badge variant="degraded">Low Stock Alert</Badge>
                    ) : (
                      <Badge variant="operational">Optimal</Badge>
                    )}
                  </td>
                  <td>
                    <div className="orq-cell-actions">
                      <button
                        type="button"
                        className="orq-btn-sm"
                        onClick={() => handleOpenHistory(inv.product_id)}
                      >
                        History
                      </button>
                      {canManage && (
                        <button
                          type="button"
                          className="orq-btn-sm"
                          onClick={() => handleOpenAdjust(inv)}
                        >
                          Adjust
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <Pagination
          currentPage={page}
          pageSize={20}
          totalItems={total}
          onPageChange={(newPage) => setPage(newPage)}
          disabled={isLoading}
        />
      </div>

      {/* Manual Stock Adjustment Modal */}
      {isAdjustOpen && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal">
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">
                {targetProduct
                  ? `Adjust Stock: ${targetProduct.product_name}`
                  : 'Manual Stock Adjustment'}
              </h2>
              <button
                type="button"
                className="orq-ops-modal-close"
                onClick={() => setIsAdjustOpen(false)}
                aria-label="Close"
              >
                <XIcon size={18} />
              </button>
            </div>
            <form onSubmit={handleAdjustSubmit} className="orq-ops-form">
              {adjustError && (
                <div className="orq-ops-error-banner">
                  <AlertCircleIcon size={16} />
                  <span>{adjustError}</span>
                </div>
              )}

              {!targetProduct && (
                <div className="orq-form-group">
                  <label className="orq-form-label">Select Product</label>
                  <select
                    className="orq-form-select"
                    value={adjustProductId}
                    onChange={(e) => setAdjustProductId(e.target.value)}
                  >
                    {allProducts.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} - {p.name} (Current: {p.quantity_on_hand})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label htmlFor="adjust-delta-input" className="orq-form-label">
                    Quantity Delta (+ Add / - Deduct)
                  </label>
                  <input
                    id="adjust-delta-input"
                    type="number"
                    step="1"
                    required
                    className="orq-form-input"
                    value={adjustDelta}
                    onChange={(e) => setAdjustDelta(parseInt(e.target.value, 10) || 0)}
                  />
                </div>
                <div className="orq-form-group">
                  <label htmlFor="adjust-type-select" className="orq-form-label">Classification</label>
                  <select
                    id="adjust-type-select"
                    className="orq-form-select"
                    value={adjustType}
                    onChange={(e) =>
                      setAdjustType(e.target.value as 'adjustment' | 'restock' | 'return')
                    }
                  >
                    <option value="adjustment">Manual Adjustment</option>
                    <option value="restock">Restock Shipment</option>
                    <option value="return">Customer Return</option>
                  </select>
                </div>
              </div>

              <div className="orq-form-group">
                <label htmlFor="adjust-notes-input" className="orq-form-label">
                  Mandatory Audit Reason (Required)
                </label>
                <textarea
                  id="adjust-notes-input"
                  required
                  className="orq-form-textarea"
                  placeholder="Specify count variance, damage disposal, or PO number..."
                  value={adjustNotes}
                  onChange={(e) => setAdjustNotes(e.target.value)}
                />
              </div>

              <div className="orq-form-actions">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAdjustOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Recording Adjustment...' : 'Record Adjustment'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Stock Movement Ledger Modal */}
      {isHistoryOpen && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal" style={{ maxWidth: '820px' }}>
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">
                {historyProductId ? 'Product Movement History' : 'Full Stock Movement Ledger'}
              </h2>
              <button
                type="button"
                className="orq-ops-modal-close"
                onClick={() => setIsHistoryOpen(false)}
                aria-label="Close"
              >
                <XIcon size={18} />
              </button>
            </div>
            <div style={{ padding: 'var(--space-4)', maxHeight: '60vh', overflowY: 'auto' }}>
              <div className="orq-ops-table-wrapper">
                <table className="orq-ops-table">
                  <thead>
                    <tr>
                      <th>Timestamp (UTC)</th>
                      <th>Product</th>
                      <th>Change</th>
                      <th>Type</th>
                      <th>Reason / Notes</th>
                    </tr>
                  </thead>
                <tbody>
                  {historyLoading ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '24px' }}>
                        Loading movements...
                      </td>
                    </tr>
                  ) : historyItems.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '24px' }}>
                        No stock movement records logged.
                      </td>
                    </tr>
                  ) : (
                    historyItems.map((m) => (
                      <tr key={m.id}>
                        <td>
                          <span className="orq-cell-mono">
                            {new Date(m.created_at).toLocaleString()}
                          </span>
                        </td>
                        <td>
                          <strong>{m.product_name || m.product_sku || 'Product'}</strong>
                        </td>
                        <td>
                          <span
                            style={{
                              fontWeight: 'bold',
                              color:
                                m.quantity_change > 0
                                  ? 'var(--color-success-text)'
                                  : 'var(--color-error-text)',
                            }}
                          >
                            {m.quantity_change > 0 ? `+${m.quantity_change}` : m.quantity_change}
                          </span>
                        </td>
                        <td>
                          <span className="orq-cell-mono">{m.movement_type}</span>
                        </td>
                        <td>
                          <span>{m.notes || 'No description provided'}</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

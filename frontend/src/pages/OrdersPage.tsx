import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRealtimeTable } from '../hooks/useRealtimeTable';
import {
  fetchOrders,
  fetchOrder,
  createOrder,
  submitOrder,
  approveOrder,
  rejectOrder,
  cancelOrder,
  fetchProducts,
  fetchCustomers,
  allocateInvoiceForOrder,
  downloadInvoicePdf,
} from '../services/operations';
import {
  Customer,
  Order,
  OrderCreateInput,
  OrderItemInput,
  OrderStatus,
  Product,
} from '../types/operations';
import { formatCurrency } from '../utils/currencies';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Pagination } from '../components/common/Pagination';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import {
  AlertCircleIcon,
  CheckIcon,
  PlusIcon,
  ShoppingCartIcon,
  XIcon,
} from '../components/icons/Icons';
import './Operations.css';

export const OrdersPage: React.FC = () => {
  const { session, serverAuth, isLoading: isAuthLoading } = useAuth();
  const businessId = serverAuth?.active_business?.business_id;
  const activeCurrency = serverAuth?.active_business?.currency || 'USD';
  const token = session?.access_token;
  const userRole = serverAuth?.active_business?.role;
  const canApprove = userRole === 'owner' || userRole === 'admin';

  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Detail Modal
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isGeneratingInvoice, setIsGeneratingInvoice] = useState<boolean>(false);
  const [isActionPending, setIsActionPending] = useState<boolean>(false);

  // Create Order Modal
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [availableProducts, setAvailableProducts] = useState<Product[]>([]);
  const [availableCustomers, setAvailableCustomers] = useState<Customer[]>([]);
  const [orderCustomerId, setOrderCustomerId] = useState<string>('');
  const [orderNotes, setOrderNotes] = useState<string>('');
  const [lineItems, setLineItems] = useState<OrderItemInput[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    if (!token || !businessId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchOrders(token, businessId, {
        status: statusFilter || undefined,
        page,
        page_size: 20,
      });
      setOrders(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load orders');
    } finally {
      setIsLoading(false);
    }
  }, [token, businessId, statusFilter, page]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  // Realtime updates reconciliation for orders & active detail modal
  useRealtimeTable<Order>({
    table: 'orders',
    onEvent: (payload) => {
      loadOrders();
      // If order detail modal is viewing the updated order, reconcile its detail view
      const modifiedId = payload.new?.id || payload.old?.id;
      if (selectedOrder && modifiedId === selectedOrder.id && token && businessId) {
        fetchOrder(token, businessId, selectedOrder.id)
          .then((fresh) => setSelectedOrder(fresh))
          .catch(() => {});
      }
    },
    onReconcile: () => {
      loadOrders();
    },
  });

  const handleOpenCreate = async () => {
    if (!token || !businessId) return;
    setOrderCustomerId('');
    setOrderNotes('');
    setFormError(null);

    try {
      const [prods, custs] = await Promise.all([
        fetchProducts(token, businessId, { is_active: true, page_size: 100 }),
        fetchCustomers(token, businessId, { is_active: true, page_size: 100 }),
      ]);
      setAvailableProducts(prods.items);
      setAvailableCustomers(custs.items);

      if (prods.items.length > 0) {
        setLineItems([{ product_id: prods.items[0].id, quantity: 1 }]);
      } else {
        setLineItems([]);
      }
      setIsCreateOpen(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to initialize order form');
    }
  };

  const handleAddLineItem = () => {
    if (availableProducts.length === 0) return;
    setLineItems([...lineItems, { product_id: availableProducts[0].id, quantity: 1 }]);
  };

  const handleRemoveLineItem = (index: number) => {
    if (lineItems.length <= 1) return;
    setLineItems(lineItems.filter((_, i) => i !== index));
  };

  const handleLineItemChange = (index: number, field: keyof OrderItemInput, val: unknown) => {
    const updated = [...lineItems];
    updated[index] = { ...updated[index], [field]: val };
    setLineItems(updated);
  };

  const calculatePreviewTotals = () => {
    let subtotal = 0;
    for (const item of lineItems) {
      const p = availableProducts.find((x) => x.id === item.product_id);
      const price = item.unit_price ? parseFloat(item.unit_price) : p ? parseFloat(p.unit_price) : 0;
      subtotal += price * (item.quantity || 1);
    }
    return {
      subtotal: subtotal.toFixed(2),
      tax: '0.00',
      total: subtotal.toFixed(2),
    };
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId) return;

    if (lineItems.length === 0) {
      setFormError('At least one product line item is required');
      return;
    }

    for (const it of lineItems) {
      if (!it.product_id) {
        setFormError('Please select a valid product for each line item');
        return;
      }
      if (it.quantity < 1) {
        setFormError('Item quantity must be at least 1');
        return;
      }
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      const payload: OrderCreateInput = {
        customer_id: orderCustomerId || undefined,
        notes: orderNotes.trim() || undefined,
        items: lineItems,
      };

      const created = await createOrder(token, businessId, payload);
      setIsCreateOpen(false);
      setSuccessMsg(`Draft Order ${created.order_number} created successfully.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadOrders();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create order');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenDetail = async (orderId: string) => {
    if (!token || !businessId) return;
    setDetailLoading(true);
    setActionError(null);
    try {
      const ord = await fetchOrder(token, businessId, orderId);
      setSelectedOrder(ord);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load order detail');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSubmitForReview = async (orderId: string) => {
    if (!token || !businessId || isActionPending) return;
    setIsActionPending(true);
    setActionError(null);
    try {
      const updated = await submitOrder(token, businessId, orderId);
      setSelectedOrder(updated);
      setSuccessMsg(`Order ${updated.order_number} submitted for operator approval.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadOrders();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to submit order');
    } finally {
      setIsActionPending(false);
    }
  };

  const handleApprove = async (orderId: string) => {
    if (!token || !businessId || isActionPending) return;
    const confirmed = window.confirm(
      'Confirm order approval? This will atomically reserve and deduct product inventory stock from the warehouse.'
    );
    if (!confirmed) return;

    setIsActionPending(true);
    setActionError(null);
    try {
      const updated = await approveOrder(token, businessId, orderId);
      setSelectedOrder(updated);
      setSuccessMsg(`Order ${updated.order_number} approved and stock deducted.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadOrders();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Approval failed');
    } finally {
      setIsActionPending(false);
    }
  };

  const handleReject = async (orderId: string) => {
    if (!token || !businessId || isActionPending) return;
    const reason = window.prompt('Specify reason for order rejection:');
    if (reason === null) return;

    setIsActionPending(true);
    setActionError(null);
    try {
      const updated = await rejectOrder(token, businessId, orderId, reason);
      setSelectedOrder(updated);
      setSuccessMsg(`Order ${updated.order_number} marked as rejected.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadOrders();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Rejection failed');
    } finally {
      setIsActionPending(false);
    }
  };

  const handleCancel = async (orderId: string, wasApproved: boolean) => {
    if (!token || !businessId || isActionPending) return;
    const warning = wasApproved
      ? 'This order was approved. Cancelling will atomically restore all deducted inventory items to on-hand stock. Proceed?'
      : 'Cancel this order?';
    const confirmed = window.confirm(warning);
    if (!confirmed) return;

    const reason = window.prompt('Cancellation reason (optional):') || undefined;

    setIsActionPending(true);
    setActionError(null);
    try {
      const updated = await cancelOrder(token, businessId, orderId, reason);
      setSelectedOrder(updated);
      setSuccessMsg(`Order ${updated.order_number} cancelled.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadOrders();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Cancellation failed');
    } finally {
      setIsActionPending(false);
    }
  };

  const handleGenerateInvoice = async (orderId: string) => {
    if (!token || !businessId) return;

    setIsGeneratingInvoice(true);
    setActionError(null);

    try {
      const invoice = await allocateInvoiceForOrder(token, businessId, orderId);
      const blob = await downloadInvoicePdf(token, businessId, invoice.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `invoice-${invoice.invoice_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setSuccessMsg(`Invoice ${invoice.invoice_number} allocated and downloaded successfully.`);
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Invoice generation failed');
    } finally {
      setIsGeneratingInvoice(false);
    }
  };

  const getStatusBadge = (status: OrderStatus) => {
    switch (status) {
      case 'approved':
        return <Badge variant="operational">Approved</Badge>;
      case 'pending_approval':
        return <Badge variant="degraded">Review Required</Badge>;
      case 'draft':
        return <Badge variant="not_connected">Draft</Badge>;
      case 'rejected':
      case 'cancelled':
        return <Badge variant="not_connected">{status.toUpperCase()}</Badge>;
      case 'fulfilled':
        return <Badge variant="operational">Fulfilled</Badge>;
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
          <ShoppingCartIcon size={32} />
          <div className="orq-ops-empty-title">Authentication Required</div>
          <p className="orq-ops-empty-desc">
            Sign in as an operator with confirmed business membership to manage orders and transactions.
          </p>
        </Card>
      </div>
    );
  }

  const totals = calculatePreviewTotals();

  return (
    <div className="orq-ops-container">
      <div className="orq-ops-header">
        <div>
          <h1 className="orq-ops-title">Orders & Transactions</h1>
          <p className="orq-ops-subtitle">
            Draft sales orders, review pending requests, and execute transaction-safe stock fulfillment.
          </p>
        </div>
        <div className="orq-ops-header-actions">
          <Button variant="primary" onClick={handleOpenCreate}>
            <PlusIcon size={16} />
            <span>New Order</span>
          </Button>
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
        <div className="orq-ops-filters">
          <button
            type="button"
            className={`orq-ops-filter-btn ${statusFilter === '' ? 'is-active' : ''}`}
            onClick={() => {
              setStatusFilter('');
              setPage(1);
            }}
          >
            All Orders
          </button>
          <button
            type="button"
            className={`orq-ops-filter-btn ${statusFilter === 'pending_approval' ? 'is-active' : ''}`}
            onClick={() => {
              setStatusFilter('pending_approval');
              setPage(1);
            }}
          >
            Review Required
          </button>
          <button
            type="button"
            className={`orq-ops-filter-btn ${statusFilter === 'draft' ? 'is-active' : ''}`}
            onClick={() => {
              setStatusFilter('draft');
              setPage(1);
            }}
          >
            Drafts
          </button>
          <button
            type="button"
            className={`orq-ops-filter-btn ${statusFilter === 'approved' ? 'is-active' : ''}`}
            onClick={() => {
              setStatusFilter('approved');
              setPage(1);
            }}
          >
            Approved
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="orq-cell-mono">{total} total orders</span>
          <button
            type="button"
            className="orq-btn-sm"
            onClick={() => loadOrders()}
            disabled={isLoading}
            title="Refresh order records"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="orq-ops-table-wrapper">
        <table className="orq-ops-table" aria-label="Orders table">
          <thead>
            <tr>
              <th>Order Number</th>
              <th>Date</th>
              <th>Customer</th>
              <th>Status</th>
              <th>Total Amount</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-loading">
                    <LoadingSpinner size="sm" label="Loading orders..." />
                  </div>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-error">
                    <AlertCircleIcon size={20} />
                    <p>{error}</p>
                    <Button variant="secondary" size="sm" onClick={() => loadOrders()}>
                      Retry
                    </Button>
                  </div>
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-empty">
                    <p>
                      {statusFilter
                        ? `No orders currently match the "${statusFilter.replace('_', ' ')}" filter.`
                        : 'No orders recorded yet. Create a new draft order to begin.'}
                    </p>
                    {statusFilter ? (
                      <Button variant="secondary" size="sm" onClick={() => setStatusFilter('')}>
                        View All Orders
                      </Button>
                    ) : (
                      <Button variant="primary" size="sm" onClick={handleOpenCreate}>
                        <PlusIcon size={14} />
                        <span>New Order</span>
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              orders.map((o) => (
                <tr key={o.id}>
                  <td>
                    <span className="orq-cell-mono">{o.order_number}</span>
                  </td>
                  <td>
                    <span style={{ fontSize: '12px' }}>
                      {new Date(o.created_at).toLocaleDateString()}
                    </span>
                  </td>
                  <td>
                    <span>{o.customer_name || 'Walk-in / Direct'}</span>
                  </td>
                  <td>{getStatusBadge(o.status)}</td>
                  <td>
                    <span className="orq-cell-price">
                      {formatCurrency(o.total_amount, activeCurrency, { useGrouping: false })}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="orq-btn-sm"
                      disabled={detailLoading}
                      onClick={() => handleOpenDetail(o.id)}
                    >
                      {detailLoading ? 'Loading...' : 'View & Manage'}
                    </button>
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

      {/* Create Order Modal */}
      {isCreateOpen && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal" style={{ maxWidth: '720px' }}>
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">Create Sales Order (Draft)</h2>
              <button
                type="button"
                className="orq-ops-modal-close"
                onClick={() => setIsCreateOpen(false)}
                aria-label="Close"
              >
                <XIcon size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateSubmit} className="orq-ops-form">
              {formError && (
                <div className="orq-ops-error-banner">
                  <AlertCircleIcon size={16} />
                  <span>{formError}</span>
                </div>
              )}

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label className="orq-form-label">Customer (Optional)</label>
                  <select
                    className="orq-form-select"
                    value={orderCustomerId}
                    onChange={(e) => setOrderCustomerId(e.target.value)}
                  >
                    <option value="">-- Direct Customer / Anonymous --</option>
                    {availableCustomers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} {c.email ? `(${c.email})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="orq-form-group">
                  <label className="orq-form-label">Order Notes</label>
                  <input
                    type="text"
                    className="orq-form-input"
                    placeholder="Instructions, PO number..."
                    value={orderNotes}
                    onChange={(e) => setOrderNotes(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '8px',
                  }}
                >
                  <span className="orq-form-label">Order Line Items</span>
                  <button
                    type="button"
                    className="orq-btn-sm"
                    onClick={handleAddLineItem}
                  >
                    + Add Item
                  </button>
                </div>

                <div className="orq-order-items-builder">
                  {lineItems.map((item, idx) => {
                    const prod = availableProducts.find((p) => p.id === item.product_id);
                    const lineTotal = (
                      (parseFloat(prod?.unit_price || '0') || 0) * (item.quantity || 1)
                    ).toFixed(2);
                    return (
                      <div key={idx} className="orq-order-item-row">
                        <select
                          className="orq-form-select"
                          value={item.product_id}
                          onChange={(e) => handleLineItemChange(idx, 'product_id', e.target.value)}
                        >
                          {availableProducts.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.sku} - {p.name} (${p.unit_price})
                            </option>
                          ))}
                        </select>
                        <input
                          type="number"
                          min="1"
                          required
                          className="orq-form-input"
                          placeholder="Qty"
                          value={item.quantity}
                          onChange={(e) =>
                            handleLineItemChange(
                              idx,
                              'quantity',
                              parseInt(e.target.value, 10) || 1
                            )
                          }
                        />
                        <div className="orq-cell-price" style={{ textAlign: 'right' }}>
                          ${lineTotal}
                        </div>
                        <button
                          type="button"
                          className="orq-btn-sm"
                          disabled={lineItems.length <= 1}
                          onClick={() => handleRemoveLineItem(idx)}
                        >
                          Remove
                        </button>
                      </div>
                    );
                  })}

                  <div className="orq-order-totals-summary">
                    <div className="orq-order-total-line">
                      <span>Subtotal:</span>
                      <span className="orq-cell-price">
                        {formatCurrency(totals.subtotal, activeCurrency, { useGrouping: false })}
                      </span>
                    </div>
                    <div className="orq-order-total-line">
                      <span>Tax (0.00%):</span>
                      <span className="orq-cell-price">
                        {formatCurrency(totals.tax, activeCurrency, { useGrouping: false })}
                      </span>
                    </div>
                    <div className="orq-order-total-line is-grand-total">
                      <span>Total Amount:</span>
                      <span className="orq-cell-price">
                        {formatCurrency(totals.total, activeCurrency, { useGrouping: false })}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="orq-form-actions">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsCreateOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating Order...' : 'Create Draft Order'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Order Detail & Action Drawer */}
      {selectedOrder && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal" style={{ maxWidth: '780px' }}>
            <div className="orq-ops-modal-header">
              <div>
                <h2 className="orq-ops-modal-title">
                  Order: {selectedOrder.order_number}
                </h2>
                <div style={{ display: 'flex', gap: '8px', marginTop: '4px', alignItems: 'center' }}>
                  {getStatusBadge(selectedOrder.status)}
                  <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                    Created: {new Date(selectedOrder.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="orq-ops-modal-close"
                onClick={() => setSelectedOrder(null)}
                aria-label="Close"
              >
                <XIcon size={18} />
              </button>
            </div>

            <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              {actionError && (
                <div className="orq-ops-error-banner" role="alert">
                  <AlertCircleIcon size={16} />
                  <span>{actionError}</span>
                </div>
              )}

              <div className="orq-form-row" style={{ fontSize: '13px' }}>
                <div>
                  <span className="orq-form-label">Customer Name:</span>
                  <div>{selectedOrder.customer_name || 'Walk-in / Direct'}</div>
                </div>
                <div>
                  <span className="orq-form-label">Internal Notes:</span>
                  <div>{selectedOrder.notes || 'No special notes'}</div>
                </div>
              </div>

              <div>
                <span className="orq-form-label">Verified Order Line Items</span>
                <div className="orq-ops-table-wrapper" style={{ marginTop: '8px' }}>
                  <table className="orq-ops-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>SKU</th>
                        <th>Unit Price</th>
                        <th>Quantity</th>
                        <th>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedOrder.items.map((it) => (
                        <tr key={it.id}>
                          <td>{it.product_name}</td>
                          <td>
                            <span className="orq-cell-mono">{it.product_sku}</span>
                          </td>
                          <td>
                            <span className="orq-cell-price">
                              {formatCurrency(it.unit_price, activeCurrency, { useGrouping: false })}
                            </span>
                          </td>
                          <td>{it.quantity}</td>
                          <td>
                            <span className="orq-cell-price">
                              {formatCurrency(it.total_price, activeCurrency, { useGrouping: false })}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="orq-order-totals-summary">
                <div className="orq-order-total-line">
                  <span>Subtotal:</span>
                  <span className="orq-cell-price">
                    {formatCurrency(selectedOrder.subtotal, activeCurrency, { useGrouping: false })}
                  </span>
                </div>
                <div className="orq-order-total-line">
                  <span>Tax:</span>
                  <span className="orq-cell-price">
                    {formatCurrency(selectedOrder.tax, activeCurrency, { useGrouping: false })}
                  </span>
                </div>
                <div className="orq-order-total-line is-grand-total">
                  <span>Total Amount:</span>
                  <span className="orq-cell-price">
                    {formatCurrency(selectedOrder.total_amount, activeCurrency, { useGrouping: false })}
                  </span>
                </div>
              </div>

              {/* Action Buttons based on order lifecycle */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  paddingTop: '16px',
                  borderTop: '1px solid var(--color-border-subtle)',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  {selectedOrder.status !== 'cancelled' &&
                    selectedOrder.status !== 'fulfilled' && (
                      <button
                        type="button"
                        className="orq-btn-sm"
                        disabled={isActionPending}
                        style={{ color: 'var(--color-error-text)', borderColor: 'var(--color-error-border)' }}
                        onClick={() =>
                          handleCancel(selectedOrder.id, selectedOrder.status === 'approved')
                        }
                      >
                        {isActionPending ? 'Cancelling...' : 'Cancel Order'}
                      </button>
                    )}
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  {selectedOrder.status === 'draft' && (
                    <Button
                      variant="primary"
                      disabled={isActionPending}
                      onClick={() => handleSubmitForReview(selectedOrder.id)}
                    >
                      {isActionPending ? 'Submitting...' : 'Submit for Review'}
                    </Button>
                  )}

                  {selectedOrder.status === 'pending_approval' && canApprove && (
                    <>
                      <Button
                        variant="outline"
                        disabled={isActionPending}
                        onClick={() => handleReject(selectedOrder.id)}
                      >
                        {isActionPending ? 'Rejecting...' : 'Reject Order'}
                      </Button>
                      <Button
                        variant="primary"
                        disabled={isActionPending}
                        onClick={() => handleApprove(selectedOrder.id)}
                      >
                        {isActionPending ? 'Approving...' : 'Approve & Deduct Stock'}
                      </Button>
                    </>
                  )}

                  {(selectedOrder.status === 'approved' || selectedOrder.status === 'fulfilled') && (
                    <Button
                      variant="primary"
                      disabled={isGeneratingInvoice || isActionPending}
                      onClick={() => handleGenerateInvoice(selectedOrder.id)}
                      data-testid="generate-invoice-btn"
                    >
                      {isGeneratingInvoice ? 'Generating Invoice...' : 'Generate Invoice PDF'}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

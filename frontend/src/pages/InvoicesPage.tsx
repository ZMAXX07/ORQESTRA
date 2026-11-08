import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRealtimeTable } from '../hooks/useRealtimeTable';
import { fetchInvoices, downloadInvoicePdf } from '../services/operations';
import { Invoice, InvoiceStatus } from '../types/operations';
import { Badge, BadgeVariant } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Pagination } from '../components/common/Pagination';
import {
  AlertCircleIcon,
  ClockIcon,
  RefreshIcon,
  SearchIcon,
  XIcon,
} from '../components/icons/Icons';
import { formatCurrency } from '../utils/currencies';
import './Operations.css';

export const InvoicesPage: React.FC = () => {
  const { session, serverAuth } = useAuth();
  const businessId = serverAuth?.active_business?.business_id;
  const activeCurrency = serverAuth?.active_business?.currency || 'USD';
  const token = session?.access_token;

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Snapshot Inspection Modal
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);

  const loadInvoices = useCallback(async () => {
    if (!token || !businessId) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchInvoices(token, businessId, { page, page_size: 20 });
      setInvoices(response.items);
      setTotal(response.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load invoices.');
    } finally {
      setIsLoading(false);
    }
  }, [token, businessId, page]);

  useEffect(() => {
    loadInvoices();
  }, [loadInvoices]);

  // Realtime updates
  useRealtimeTable({
    table: 'invoices',
    onEvent: () => {
      loadInvoices();
    },
    onReconcile: loadInvoices,
  });

  const handleDownloadPdf = async (invoice: Invoice) => {
    if (!token || !businessId) return;

    setDownloadingId(invoice.id);
    setDownloadError(null);

    try {
      const blob = await downloadInvoicePdf(token, businessId, invoice.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `invoice-${invoice.invoice_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setDownloadError(
        `Failed to download invoice ${invoice.invoice_number}: ${
          err instanceof Error ? err.message : 'Unknown download error'
        }`
      );
    } finally {
      setDownloadingId(null);
    }
  };

  const getStatusBadgeVariant = (status: InvoiceStatus): BadgeVariant => {
    switch (status) {
      case 'issued':
        return 'info';
      case 'paid':
        return 'operational';
      case 'draft':
        return 'neutral';
      case 'void':
      case 'cancelled':
        return 'not_connected';
      default:
        return 'neutral';
    }
  };

  const filteredInvoices = search.trim()
    ? invoices.filter(
        (inv) =>
          inv.invoice_number.toLowerCase().includes(search.trim().toLowerCase()) ||
          inv.order_id.toLowerCase().includes(search.trim().toLowerCase())
      )
    : invoices;

  return (
    <div className="orq-ops-container" data-testid="invoices-page">
      <div className="orq-ops-header">
        <div>
          <h1 className="orq-ops-title">Invoices & Billing</h1>
          <p className="orq-ops-subtitle">
            Authoritative, sequential invoices generated from persisted approved orders with exact Decimal math.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Button
            variant="secondary"
            onClick={loadInvoices}
            disabled={isLoading}
            id="refresh-invoices-btn"
          >
            <RefreshIcon size={14} /> Refresh
          </Button>
        </div>
      </div>

      {downloadError && (
        <div className="orq-ops-alert orq-ops-alert-danger" data-testid="download-error-banner">
          <AlertCircleIcon size={18} />
          <span>{downloadError}</span>
        </div>
      )}

      {error && (
        <div className="orq-ops-alert orq-ops-alert-danger" data-testid="invoices-error-banner">
          <AlertCircleIcon size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Search and Filters */}
      <div className="orq-ops-toolbar">
        <div className="orq-ops-search-box">
          <SearchIcon size={16} />
          <input
            type="text"
            className="orq-ops-search-input"
            placeholder="Search by invoice number or order ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="orq-ops-filters">
          <span className="orq-cell-mono">{total} invoices recorded</span>
        </div>
      </div>

      <Card title={`Invoice Records (${total})`}>
        {isLoading ? (
          <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            Loading invoices...
          </div>
        ) : filteredInvoices.length === 0 ? (
          <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--color-text-muted)' }} data-testid="no-invoices-state">
            <ClockIcon size={32} style={{ margin: '0 auto var(--space-2)', opacity: 0.5 }} />
            <p style={{ margin: 0, fontWeight: 'var(--font-weight-medium)' }}>
              {search.trim() ? 'No invoices match your search.' : 'No invoices have been allocated yet.'}
            </p>
            <p style={{ margin: 'var(--space-1) 0 0 0', fontSize: 'var(--font-size-xs)' }}>
              Invoices are issued automatically or on-demand from approved orders in Order Processing.
            </p>
          </div>
        ) : (
          <div className="orq-ops-table-container">
            <table className="orq-ops-table" data-testid="invoices-table">
              <thead>
                <tr>
                  <th>Invoice Number</th>
                  <th>Order Reference</th>
                  <th>Amount Due</th>
                  <th>Due Date</th>
                  <th>Status</th>
                  <th>Issued Date</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredInvoices.map((inv) => (
                  <tr key={inv.id} data-testid={`invoice-row-${inv.id}`}>
                    <td style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)' }}>
                      <button
                        type="button"
                        className="orq-ops-card-link"
                        onClick={() => setSelectedInvoice(inv)}
                        style={{ fontWeight: 'var(--font-weight-semibold)' }}
                      >
                        {inv.invoice_number}
                      </button>
                    </td>
                    <td>
                      <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                        {inv.order_id.slice(0, 8)}...
                      </span>
                    </td>
                    <td style={{ fontWeight: 'var(--font-weight-medium)' }}>
                      {formatCurrency(inv.amount_due, activeCurrency, { useGrouping: false })}
                    </td>
                    <td>
                      {inv.due_date ? new Date(inv.due_date).toLocaleDateString() : 'Immediate'}
                    </td>
                    <td>
                      <Badge variant={getStatusBadgeVariant(inv.status)}>
                        {inv.status}
                      </Badge>
                    </td>
                    <td style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                      {new Date(inv.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ textAlign: 'right', display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        className="orq-btn-sm"
                        onClick={() => setSelectedInvoice(inv)}
                      >
                        Details
                      </button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleDownloadPdf(inv)}
                        disabled={downloadingId === inv.id}
                        data-testid={`download-pdf-btn-${inv.id}`}
                      >
                        {downloadingId === inv.id ? 'Generating...' : 'Download PDF'}
                      </Button>
                    </td>
                  </tr>
                ))}
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
        )}
      </Card>

      {/* Invoice Snapshot Inspection Modal */}
      {selectedInvoice && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal" style={{ maxWidth: '640px' }}>
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">
                Invoice Details: {selectedInvoice.invoice_number}
              </h2>
              <button
                type="button"
                className="orq-ops-modal-close"
                onClick={() => setSelectedInvoice(null)}
                aria-label="Close"
              >
                <XIcon size={18} />
              </button>
            </div>

            <div style={{ padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 'var(--space-3)' }}>
                <div>
                  <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Status
                  </span>
                  <div>
                    <Badge variant={getStatusBadgeVariant(selectedInvoice.status)}>
                      {selectedInvoice.status}
                    </Badge>
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Amount Due
                  </span>
                  <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-bold)' }}>
                    {formatCurrency(selectedInvoice.amount_due, activeCurrency, { useGrouping: false })}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Order ID
                  </span>
                  <div className="orq-cell-mono">{selectedInvoice.order_id}</div>
                </div>
                <div>
                  <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Issued Date
                  </span>
                  <div>{new Date(selectedInvoice.created_at).toLocaleString()}</div>
                </div>
              </div>

              {/* Customer Snapshot if present */}
              {selectedInvoice.customer_snapshot && (
                <div style={{ borderTop: '1px solid var(--color-border-subtle)', paddingTop: 'var(--space-3)' }}>
                  <h3 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-2)' }}>
                    Immutable Customer Snapshot
                  </h3>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                    <div><strong>Name:</strong> {selectedInvoice.customer_snapshot.name || 'N/A'}</div>
                    {selectedInvoice.customer_snapshot.email && <div><strong>Email:</strong> {selectedInvoice.customer_snapshot.email}</div>}
                    {selectedInvoice.customer_snapshot.phone && <div><strong>Phone:</strong> {selectedInvoice.customer_snapshot.phone}</div>}
                    {selectedInvoice.customer_snapshot.address && <div><strong>Address:</strong> {selectedInvoice.customer_snapshot.address}</div>}
                  </div>
                </div>
              )}

              {/* Line Items Snapshot if present */}
              {selectedInvoice.line_items_snapshot && selectedInvoice.line_items_snapshot.length > 0 && (
                <div style={{ borderTop: '1px solid var(--color-border-subtle)', paddingTop: 'var(--space-3)' }}>
                  <h3 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-2)' }}>
                    Snapshot Line Items
                  </h3>
                  <div className="orq-table-compact-wrapper">
                    <table className="orq-table-compact">
                      <thead>
                        <tr>
                          <th>Item</th>
                          <th>Qty</th>
                          <th>Unit Price</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedInvoice.line_items_snapshot.map((item, idx) => (
                          <tr key={idx}>
                            <td><strong>{item.product_name}</strong></td>
                            <td>{item.quantity}</td>
                            <td>{formatCurrency(item.unit_price, activeCurrency, { useGrouping: false })}</td>
                            <td>{formatCurrency(item.total_price || item.line_total, activeCurrency, { useGrouping: false })}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', borderTop: '1px solid var(--color-border-subtle)', paddingTop: 'var(--space-3)' }}>
                <Button
                  variant="primary"
                  onClick={() => handleDownloadPdf(selectedInvoice)}
                  disabled={downloadingId === selectedInvoice.id}
                >
                  {downloadingId === selectedInvoice.id ? 'Generating...' : 'Download PDF Document'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

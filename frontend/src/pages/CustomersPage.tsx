import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  fetchCustomers,
  createCustomer,
  updateCustomer,
  deactivateCustomer,
} from '../services/operations';
import { Customer, CustomerCreateInput } from '../types/operations';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Pagination } from '../components/common/Pagination';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import {
  AlertCircleIcon,
  CheckIcon,
  PlusIcon,
  SearchIcon,
  UsersIcon,
  XIcon,
} from '../components/icons/Icons';
import './Operations.css';

export const CustomersPage: React.FC = () => {
  const { session, serverAuth, isLoading: isAuthLoading } = useAuth();
  const businessId = serverAuth?.active_business?.business_id;
  const token = session?.access_token;

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Form states
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formAddress, setFormAddress] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const loadCustomers = useCallback(async () => {
    if (!token || !businessId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchCustomers(token, businessId, {
        search: search.trim() || undefined,
        page,
        page_size: 20,
      });
      setCustomers(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load customers');
    } finally {
      setIsLoading(false);
    }
  }, [token, businessId, search, page]);

  useEffect(() => {
    loadCustomers();
  }, [loadCustomers]);

  const handleOpenCreate = () => {
    setFormName('');
    setFormEmail('');
    setFormPhone('');
    setFormAddress('');
    setFormNotes('');
    setFormError(null);
    setIsCreateOpen(true);
  };

  const handleOpenEdit = (customer: Customer) => {
    setEditingCustomer(customer);
    setFormName(customer.name);
    setFormEmail(customer.email || '');
    setFormPhone(customer.phone || '');
    setFormAddress(customer.address || '');
    setFormNotes(customer.notes || '');
    setFormError(null);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId) return;

    if (!formName.trim()) {
      setFormError('Customer name is required');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      const payload: CustomerCreateInput = {
        name: formName.trim(),
        email: formEmail.trim() || undefined,
        phone: formPhone.trim() || undefined,
        address: formAddress.trim() || undefined,
        notes: formNotes.trim() || undefined,
      };

      await createCustomer(token, businessId, payload);
      setIsCreateOpen(false);
      setSuccessMsg(`Customer "${payload.name}" created successfully.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadCustomers();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create customer');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId || !editingCustomer) return;

    if (!formName.trim()) {
      setFormError('Customer name is required');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      await updateCustomer(token, businessId, editingCustomer.id, {
        name: formName.trim(),
        email: formEmail.trim() || undefined,
        phone: formPhone.trim() || undefined,
        address: formAddress.trim() || undefined,
        notes: formNotes.trim() || undefined,
      });

      setEditingCustomer(null);
      setSuccessMsg(`Customer "${formName}" updated successfully.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadCustomers();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to update customer');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeactivate = async (customer: Customer) => {
    if (!token || !businessId) return;
    const confirmed = window.confirm(
      `Are you sure you want to deactivate customer "${customer.name}"? Active selection in orders will omit this record.`
    );
    if (!confirmed) return;

    try {
      await deactivateCustomer(token, businessId, customer.id);
      setSuccessMsg(`Customer "${customer.name}" deactivated.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadCustomers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to deactivate customer');
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
          <UsersIcon size={32} />
          <div className="orq-ops-empty-title">Authentication Required</div>
          <p className="orq-ops-empty-desc">
            Sign in as an operator with confirmed business membership to manage customer records.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="orq-ops-container">
      <div className="orq-ops-header">
        <div>
          <h1 className="orq-ops-title">Customer Directory</h1>
          <p className="orq-ops-subtitle">
            Maintain verified customer contact records, delivery destinations, and client histories.
          </p>
        </div>
        <div className="orq-ops-header-actions">
          <Button variant="primary" onClick={handleOpenCreate}>
            <PlusIcon size={16} />
            <span>New Customer</span>
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
        <div className="orq-ops-search-box">
          <SearchIcon size={16} />
          <input
            type="text"
            className="orq-ops-search-input"
            placeholder="Search by name, email, or phone..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="orq-ops-filters">
          <span className="orq-cell-mono">{total} total customers</span>
          <button
            type="button"
            className="orq-btn-sm"
            onClick={() => loadCustomers()}
            disabled={isLoading}
            title="Refresh customer records"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="orq-ops-table-wrapper">
        <table className="orq-ops-table" aria-label="Customer directory table">
          <thead>
            <tr>
              <th>Customer Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Address</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-loading">
                    <LoadingSpinner size="sm" label="Loading customer records..." />
                  </div>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-error">
                    <AlertCircleIcon size={20} />
                    <p>{error}</p>
                    <Button variant="secondary" size="sm" onClick={() => loadCustomers()}>
                      Retry
                    </Button>
                  </div>
                </td>
              </tr>
            ) : customers.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-empty">
                    <p>
                      {search.trim()
                        ? `No customers match "${search.trim()}".`
                        : 'No customer records found. Add your first customer to start tracking client histories.'}
                    </p>
                    {!search.trim() && (
                      <Button variant="primary" size="sm" onClick={handleOpenCreate}>
                        <PlusIcon size={14} />
                        <span>New Customer</span>
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              customers.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.name}</strong>
                    {c.notes && (
                      <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                        {c.notes}
                      </div>
                    )}
                  </td>
                  <td>
                    <span>{c.email || 'None listed'}</span>
                  </td>
                  <td>
                    <span>{c.phone || 'None listed'}</span>
                  </td>
                  <td>
                    <span style={{ fontSize: '13px' }}>{c.address || 'None listed'}</span>
                  </td>
                  <td>
                    {c.is_active ? (
                      <Badge variant="operational">Active</Badge>
                    ) : (
                      <Badge variant="not_connected">Inactive</Badge>
                    )}
                  </td>
                  <td>
                    <div className="orq-cell-actions">
                      <button
                        type="button"
                        className="orq-btn-sm"
                        onClick={() => handleOpenEdit(c)}
                      >
                        Edit
                      </button>
                      {c.is_active && (
                        <button
                          type="button"
                          className="orq-btn-sm"
                          onClick={() => handleDeactivate(c)}
                        >
                          Deactivate
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

      {/* Create Customer Modal */}
      {isCreateOpen && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal">
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">Create New Customer</h2>
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
              <div className="orq-form-group">
                <label className="orq-form-label">Customer or Company Name</label>
                <input
                  type="text"
                  required
                  className="orq-form-input"
                  placeholder="e.g. Apex Manufacturing Ltd."
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                />
              </div>

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label className="orq-form-label">Email Address (Optional)</label>
                  <input
                    type="email"
                    className="orq-form-input"
                    placeholder="e.g. buyer@apex.local"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                  />
                </div>
                <div className="orq-form-group">
                  <label className="orq-form-label">Phone Number (Optional)</label>
                  <input
                    type="tel"
                    className="orq-form-input"
                    placeholder="e.g. +1-555-0144"
                    value={formPhone}
                    onChange={(e) => setFormPhone(e.target.value)}
                  />
                </div>
              </div>

              <div className="orq-form-group">
                <label className="orq-form-label">Delivery Address (Optional)</label>
                <textarea
                  className="orq-form-textarea"
                  placeholder="Street, City, Postal Code"
                  value={formAddress}
                  onChange={(e) => setFormAddress(e.target.value)}
                />
              </div>

              <div className="orq-form-group">
                <label className="orq-form-label">Internal Notes (Optional)</label>
                <textarea
                  className="orq-form-textarea"
                  placeholder="Billing terms, contact preferences..."
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                />
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
                  {isSubmitting ? 'Saving Customer...' : 'Create Customer'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Customer Modal */}
      {editingCustomer && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal">
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">Edit Customer: {editingCustomer.name}</h2>
              <button
                type="button"
                className="orq-ops-modal-close"
                onClick={() => setEditingCustomer(null)}
                aria-label="Close"
              >
                <XIcon size={18} />
              </button>
            </div>
            <form onSubmit={handleEditSubmit} className="orq-ops-form">
              {formError && (
                <div className="orq-ops-error-banner">
                  <AlertCircleIcon size={16} />
                  <span>{formError}</span>
                </div>
              )}
              <div className="orq-form-group">
                <label className="orq-form-label">Customer or Company Name</label>
                <input
                  type="text"
                  required
                  className="orq-form-input"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                />
              </div>

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label className="orq-form-label">Email Address</label>
                  <input
                    type="email"
                    className="orq-form-input"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                  />
                </div>
                <div className="orq-form-group">
                  <label className="orq-form-label">Phone Number</label>
                  <input
                    type="tel"
                    className="orq-form-input"
                    value={formPhone}
                    onChange={(e) => setFormPhone(e.target.value)}
                  />
                </div>
              </div>

              <div className="orq-form-group">
                <label className="orq-form-label">Delivery Address</label>
                <textarea
                  className="orq-form-textarea"
                  value={formAddress}
                  onChange={(e) => setFormAddress(e.target.value)}
                />
              </div>

              <div className="orq-form-group">
                <label className="orq-form-label">Internal Notes</label>
                <textarea
                  className="orq-form-textarea"
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                />
              </div>

              <div className="orq-form-actions">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setEditingCustomer(null)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Saving Changes...' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

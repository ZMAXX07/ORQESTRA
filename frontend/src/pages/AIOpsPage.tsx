import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  extractOrderFromText,
  createOrder,
  fetchProducts,
  fetchCustomers,
} from '../services/operations';
import {
  CandidateItemMatch,
  Customer,
  Order,
  OrderIntakeResponse,
  Product,
} from '../types/operations';
import { formatCurrency } from '../utils/currencies';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import {
  AlertCircleIcon,
  CheckIcon,
  XIcon,
} from '../components/icons/Icons';
import './Operations.css';

interface EditableLineItem {
  candidate_name: string;
  raw_text: string;
  variant?: string;
  quantity: number;
  selected_product_id: string;
  match_status: 'matched' | 'ambiguous' | 'unmatched';
  potential_matches: Array<{ id: string; name: string; sku: string; unit_price: string }>;
}

export interface AIOpsPageProps {
  onNavigateToOrders?: () => void;
}

export const AIOpsPage: React.FC<AIOpsPageProps> = ({ onNavigateToOrders }) => {
  const { session, serverAuth } = useAuth();
  const businessId = serverAuth?.active_business?.business_id;
  const activeCurrency = serverAuth?.active_business?.currency || 'USD';
  const token = session?.access_token;

  // Input state
  const [customerMessage, setCustomerMessage] = useState<string>('');
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [extractError, setExtractError] = useState<string | null>(null);

  // Reference data
  const [catalogProducts, setCatalogProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);

  // Extraction result
  const [proposal, setProposal] = useState<OrderIntakeResponse | null>(null);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');
  const [items, setItems] = useState<EditableLineItem[]>([]);
  const [orderNotes, setOrderNotes] = useState<string>('');

  // Draft Creation State
  const [isCreatingDraft, setIsCreatingDraft] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createdOrder, setCreatedOrder] = useState<Order | null>(null);

  useEffect(() => {
    let isMounted = true;
    if (!token || !businessId) return;

    fetchProducts(token, businessId, { page_size: 100 })
      .then((res) => {
        if (isMounted) setCatalogProducts(res.items.filter((p) => p.is_active));
      })
      .catch(() => {});

    fetchCustomers(token, businessId, { page_size: 100 })
      .then((res) => {
        if (isMounted) setCustomers(res.items.filter((c) => c.is_active));
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [token, businessId]);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId) return;

    const trimmed = customerMessage.trim();
    if (trimmed.length < 5) {
      setExtractError('Message must be at least 5 characters long.');
      return;
    }
    if (trimmed.length > 4000) {
      setExtractError('Message cannot exceed 4000 characters.');
      return;
    }

    setIsAnalyzing(true);
    setExtractError(null);
    setCreatedOrder(null);
    setCreateError(null);

    try {
      const response = await extractOrderFromText(token, businessId, trimmed);
      setProposal(response);

      // Initialize customer selection
      setSelectedCustomerId(response.matched_customer_id || '');

      // Initialize notes
      const initialNotes = [
        response.notes,
        response.delivery_instructions ? `Delivery: ${response.delivery_instructions}` : null,
      ]
        .filter(Boolean)
        .join(' | ');
      setOrderNotes(initialNotes);

      // Initialize editable line items
      const initialItems: EditableLineItem[] = response.items.map((cand: CandidateItemMatch) => {
        let selectedId = '';
        if (cand.matched_product) {
          selectedId = cand.matched_product.id;
        } else if (cand.potential_matches && cand.potential_matches.length === 1) {
          selectedId = cand.potential_matches[0].id;
        }

        return {
          candidate_name: cand.candidate_product_name,
          raw_text: cand.raw_text,
          variant: cand.variant,
          quantity: cand.requested_quantity > 0 ? cand.requested_quantity : 1,
          selected_product_id: selectedId,
          match_status: cand.match_status,
          potential_matches: cand.potential_matches || [],
        };
      });
      setItems(initialItems);
    } catch (err: any) {
      setExtractError(err.message || 'Failed to analyze customer message.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleProductChange = (index: number, newProductId: string) => {
    setItems((prev) => {
      const next = [...prev];
      next[index] = {
        ...next[index],
        selected_product_id: newProductId,
        match_status: newProductId ? 'matched' : 'unmatched',
      };
      return next;
    });
  };

  const handleQuantityChange = (index: number, qty: number) => {
    setItems((prev) => {
      const next = [...prev];
      next[index] = {
        ...next[index],
        quantity: Math.max(1, qty),
      };
      return next;
    });
  };

  const handleRemoveItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
  };

  // Calculations
  const calculatedSubtotal = items.reduce((sum, item) => {
    const prod = catalogProducts.find((p) => p.id === item.selected_product_id);
    if (!prod) return sum;
    return sum + Number(prod.unit_price) * item.quantity;
  }, 0);

  const calculatedTax = 0;
  const calculatedTotal = calculatedSubtotal;

  const hasUnmatchedItems = items.some((i) => !i.selected_product_id || i.match_status === 'unmatched');
  const canSubmitDraft = items.length > 0 && !hasUnmatchedItems;

  const handleCreateDraft = async () => {
    if (!token || !businessId || !canSubmitDraft) return;

    setIsCreatingDraft(true);
    setCreateError(null);

    try {
      const orderData = {
        customer_id: selectedCustomerId || undefined,
        notes: orderNotes.trim() ? `${orderNotes.trim()} [Extracted from message]` : '[Extracted from message]',
        items: items.map((i) => ({
          product_id: i.selected_product_id,
          quantity: i.quantity,
        })),
      };

      const order = await createOrder(token, businessId, orderData);
      setCreatedOrder(order);
      setProposal(null);
      setCustomerMessage('');
      setItems([]);
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create draft order.');
    } finally {
      setIsCreatingDraft(false);
    }
  };

  return (
    <div className="orq-ops-container" data-testid="ai-ops-page">
      <div className="orq-ops-header">
        <div>
          <h1 className="orq-ops-title">AI Order Extraction & Intake</h1>
          <p className="orq-ops-subtitle">
            Parse customer messages, review deterministic catalog matches, and verify draft orders with stock safety.
          </p>
        </div>
        {onNavigateToOrders && (
          <div className="orq-ops-header-actions">
            <Button variant="secondary" onClick={onNavigateToOrders} id="nav-to-manual-orders-btn">
              Switch to Manual Order Entry
            </Button>
          </div>
        )}
      </div>

      {createdOrder && (
        <div className="orq-ops-alert orq-ops-alert-success" data-testid="draft-created-banner">
          <CheckIcon size={18} />
          <div style={{ flex: 1 }}>
            <strong>Draft Order Created Successfully: {createdOrder.order_number}</strong>
            <p style={{ margin: '4px 0 0 0', fontSize: 'var(--font-size-xs)' }}>
              Order is saved in draft status with subtotal {formatCurrency(createdOrder.subtotal, activeCurrency, { useGrouping: false })}.
              Stock has not been deducted. You may review and approve it inside Order Processing.
            </p>
          </div>
          {onNavigateToOrders && (
            <Button variant="secondary" size="sm" onClick={onNavigateToOrders}>
              View in Orders
            </Button>
          )}
        </div>
      )}

      {/* Input Message Form */}
      <Card>
        <CardHeader>
          <CardTitle>Customer Order Message</CardTitle>
        </CardHeader>
        <CardBody>
          <form className="orq-ai-ops-form" onSubmit={handleAnalyze}>
            <div className="orq-ops-form-group">
              <label htmlFor="customer-order-text" className="orq-ops-label">
                Paste Raw Customer Message
              </label>
              <textarea
                id="customer-order-text"
                data-testid="ai-intake-textarea"
                className="orq-ai-textarea"
                rows={4}
                placeholder="e.g. Please send 5 notebooks and 2 blue pens for delivery tomorrow. This is Ravi from ABC Traders."
                value={customerMessage}
                onChange={(e) => setCustomerMessage(e.target.value)}
                disabled={isAnalyzing}
              />
              <div className="orq-ai-meta-row">
                <span className="orq-ai-helper-text">
                  Untrusted text is constrained by schema validation. Prices and totals are derived strictly from your database catalog.
                </span>
                <span
                  className={`orq-ai-char-counter ${customerMessage.length > 4000 ? 'is-limit' : ''}`}
                >
                  {customerMessage.length} / 4000 characters
                </span>
              </div>
            </div>

            {extractError && (
              <div className="orq-ops-alert orq-ops-alert-danger" data-testid="ai-extraction-error" style={{ marginBottom: 'var(--space-4)' }}>
                <AlertCircleIcon size={18} />
                <div style={{ flex: 1 }}>
                  <span>{extractError}</span>
                  {extractError.includes('AI provider is not configured') && (
                    <div style={{ marginTop: 'var(--space-2)' }}>
                      <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', margin: 0 }}>
                        The AI_API_KEY environment variable is not configured on the server. You can still manage and create orders using the manual order entry workflow.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="orq-ai-actions-row">
              {onNavigateToOrders && (
                <Button type="button" variant="secondary" onClick={onNavigateToOrders}>
                  Manual Entry Fallback
                </Button>
              )}
              <Button
                type="submit"
                variant="primary"
                id="ai-analyze-btn"
                data-testid="ai-analyze-button"
                disabled={isAnalyzing || customerMessage.trim().length < 5 || customerMessage.length > 4000}
              >
                {isAnalyzing ? 'Analyzing Message...' : 'Analyze Order Request'}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      {/* Human Review & Confirmation Panel */}
      {proposal && (
        <Card data-testid="ai-proposal-review">
          <CardHeader>
            <CardTitle>Candidate Proposal & Human Review</CardTitle>
          </CardHeader>
          <CardBody>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {/* Original message reference */}
            <div style={{ padding: 'var(--space-3)', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>
                Original Message Snippet
              </span>
              <p style={{ margin: 'var(--space-1) 0 0 0', fontStyle: 'italic', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-primary)' }}>
                "{proposal.raw_message}"
              </p>
            </div>

            {/* Customer Mapping */}
            <div className="orq-ops-form-row">
              <div className="orq-ops-form-group" style={{ flex: 1 }}>
                <label className="orq-ops-label">Extracted Customer Name</label>
                <div style={{ padding: 'var(--space-2)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-primary)' }}>
                  {proposal.extracted_customer_name || 'None detected in message'}
                </div>
              </div>
              <div className="orq-ops-form-group" style={{ flex: 2 }}>
                <label htmlFor="select-matched-customer" className="orq-ops-label">
                  Assigned Customer Directory Record
                </label>
                <select
                  id="select-matched-customer"
                  className="orq-ops-input"
                  value={selectedCustomerId}
                  onChange={(e) => setSelectedCustomerId(e.target.value)}
                >
                  <option value="">No Customer Linked (Guest / Unregistered)</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.email ? `(${c.email})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Extracted Notes / Instructions */}
            <div className="orq-ops-form-group">
              <label htmlFor="order-review-notes" className="orq-ops-label">
                Order Notes & Instructions
              </label>
              <input
                id="order-review-notes"
                type="text"
                className="orq-ops-input"
                value={orderNotes}
                onChange={(e) => setOrderNotes(e.target.value)}
                placeholder="Notes or delivery instructions"
              />
            </div>

            {/* Line Items Table */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)', flexWrap: 'wrap', gap: '4px' }}>
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 'var(--font-weight-semibold)', margin: 0 }}>
                  Candidate Line Items
                </h3>
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                  Verify catalog matches and quantities before confirming.
                </span>
              </div>

              <div className="orq-ops-table-container">
                <table className="orq-ops-table" data-testid="proposal-items-table">
                  <thead>
                    <tr>
                      <th>Candidate Snippet</th>
                      <th>Catalog Product Match</th>
                      <th style={{ width: '100px' }}>Quantity</th>
                      <th style={{ width: '120px' }}>Authoritative Price</th>
                      <th style={{ width: '120px' }}>Line Total</th>
                      <th style={{ width: '60px' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, idx) => {
                      const matchedProd = catalogProducts.find((p) => p.id === item.selected_product_id);
                      const unitPrice = matchedProd ? Number(matchedProd.unit_price) : 0;
                      const lineTotal = unitPrice * item.quantity;

                      return (
                        <tr key={idx} data-testid={`item-row-${idx}`}>
                          <td>
                            <div style={{ fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-primary)' }}>
                              {item.candidate_name}
                            </div>
                            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                              "{item.raw_text}" {item.variant ? `(Variant: ${item.variant})` : ''}
                            </div>
                          </td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                              <select
                                className="orq-ops-input"
                                value={item.selected_product_id}
                                onChange={(e) => handleProductChange(idx, e.target.value)}
                                data-testid={`product-select-${idx}`}
                              >
                                <option value="">Select Catalog Product...</option>
                                {catalogProducts.map((p) => (
                                  <option key={p.id} value={p.id}>
                                    {p.name} ({p.sku}) - {formatCurrency(p.unit_price, activeCurrency, { useGrouping: false })} (Stock: {p.quantity_on_hand})
                                  </option>
                                ))}
                              </select>
                              <div>
                                {item.match_status === 'matched' && (
                                  <Badge variant="operational">Matched</Badge>
                                )}
                                {item.match_status === 'ambiguous' && (
                                  <Badge variant="degraded">Ambiguous Match</Badge>
                                )}
                                {item.match_status === 'unmatched' && (
                                  <Badge variant="not_connected">Unmatched</Badge>
                                )}
                              </div>
                            </div>
                          </td>
                          <td>
                            <input
                              type="number"
                              min={1}
                              className="orq-ops-input"
                              value={item.quantity}
                              onChange={(e) => handleQuantityChange(idx, parseInt(e.target.value, 10) || 1)}
                              data-testid={`quantity-input-${idx}`}
                            />
                          </td>
                          <td>
                            {matchedProd ? (
                              <span>{formatCurrency(matchedProd.unit_price, activeCurrency, { useGrouping: false })}</span>
                            ) : (
                              <span style={{ color: 'var(--color-text-muted)' }}>N/A</span>
                            )}
                          </td>
                          <td style={{ fontWeight: 'var(--font-weight-semibold)' }}>
                            {formatCurrency(lineTotal, activeCurrency, { useGrouping: false })}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="orq-ops-action-btn danger"
                              onClick={() => handleRemoveItem(idx)}
                              title="Remove item"
                            >
                              <XIcon size={14} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Calculations Breakdown */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-3)' }}>
              <div style={{ minWidth: '260px', display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-sm)' }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>Subtotal:</span>
                  <span style={{ fontWeight: 'var(--font-weight-medium)' }}>
                    {formatCurrency(calculatedSubtotal, activeCurrency, { useGrouping: false })}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-sm)' }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>Tax (Standard):</span>
                  <span style={{ fontWeight: 'var(--font-weight-medium)' }}>
                    {formatCurrency(calculatedTax, activeCurrency, { useGrouping: false })}
                  </span>
                </div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 'var(--font-size-base)',
                    fontWeight: 'var(--font-weight-bold)',
                    borderTop: '1px solid var(--color-border-subtle)',
                    paddingTop: 'var(--space-2)',
                  }}
                >
                  <span>Total Amount:</span>
                  <span data-testid="proposal-total-amount">
                    {formatCurrency(calculatedTotal, activeCurrency, { useGrouping: false })}
                  </span>
                </div>
              </div>
            </div>

            {hasUnmatchedItems && (
              <div className="orq-ops-alert orq-ops-alert-warning" data-testid="unmatched-items-warning">
                <AlertCircleIcon size={18} />
                <span>
                  One or more items are ambiguous or unmatched. Please resolve all items to active catalog products before confirming the draft order.
                </span>
              </div>
            )}

            {createError && (
              <div className="orq-ops-alert orq-ops-alert-danger" data-testid="create-draft-error">
                <AlertCircleIcon size={18} />
                <span>{createError}</span>
              </div>
            )}

            {/* Confirmation actions */}
            <div style={{ borderTop: '1px solid var(--color-border-subtle)', paddingTop: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                  Creating a draft order does not deduct stock. Stock deduction occurs only after explicit review and approval in Order Processing.
                </span>
                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                  <Button variant="secondary" onClick={() => setProposal(null)}>
                    Discard Proposal
                  </Button>
                  <Button
                    variant="primary"
                    id="confirm-create-draft-btn"
                    data-testid="confirm-create-draft-button"
                    disabled={!canSubmitDraft || isCreatingDraft}
                    onClick={handleCreateDraft}
                  >
                    {isCreatingDraft ? 'Creating Draft...' : 'Confirm & Create Draft Order'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>
    )}
    </div>
  );
};

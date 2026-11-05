import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRealtimeTable } from '../hooks/useRealtimeTable';
import {
  fetchProducts,
  createProduct,
  updateProduct,
  deactivateProduct,
} from '../services/operations';
import { Product, ProductCreateInput } from '../types/operations';
import { formatCurrency, getCurrencySymbol } from '../utils/currencies';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Pagination } from '../components/common/Pagination';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import {
  PlusIcon,
  SearchIcon,
  XIcon,
  AlertCircleIcon,
  CheckIcon,
  PackageIcon,
} from '../components/icons/Icons';
import './Operations.css';

export const ProductsPage: React.FC = () => {
  const { session, serverAuth, isLoading: isAuthLoading } = useAuth();
  const businessId = serverAuth?.active_business?.business_id;
  const activeCurrency = serverAuth?.active_business?.currency || 'USD';
  const currencySymbol = getCurrencySymbol(activeCurrency);
  const token = session?.access_token;
  const userRole = serverAuth?.active_business?.role;
  const canManage = userRole === 'owner' || userRole === 'admin';

  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Form states
  const [formSku, setFormSku] = useState('');
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formUnitPrice, setFormUnitPrice] = useState('0.00');
  const [formCostPrice, setFormCostPrice] = useState('0.00');
  const [formStock, setFormStock] = useState('0');
  const [formThreshold, setFormThreshold] = useState('5');
  const [formError, setFormError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    if (!token || !businessId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchProducts(token, businessId, {
        search: search.trim() || undefined,
        page,
        page_size: 20,
      });
      setProducts(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load products');
    } finally {
      setIsLoading(false);
    }
  }, [token, businessId, search, page]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // Realtime live updates reconciliation
  useRealtimeTable<Product>({
    table: 'products',
    onEvent: () => {
      loadProducts();
    },
    onReconcile: () => {
      loadProducts();
    },
  });

  const handleOpenCreate = () => {
    setFormSku('');
    setFormName('');
    setFormDesc('');
    setFormUnitPrice('0.00');
    setFormCostPrice('0.00');
    setFormStock('0');
    setFormThreshold('5');
    setFormError(null);
    setIsCreateOpen(true);
  };

  const handleOpenEdit = (product: Product) => {
    setEditingProduct(product);
    setFormName(product.name);
    setFormDesc(product.description || '');
    setFormUnitPrice(product.unit_price);
    setFormCostPrice(product.cost_price || '0.00');
    setFormError(null);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId) return;

    if (!formSku.trim() || !formName.trim()) {
      setFormError('SKU and Product Name are required');
      return;
    }

    const price = parseFloat(formUnitPrice);
    if (isNaN(price) || price < 0) {
      setFormError('Unit price must be a valid non-negative amount');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      const payload: ProductCreateInput = {
        sku: formSku.trim(),
        name: formName.trim(),
        description: formDesc.trim() || undefined,
        unit_price: price.toFixed(2),
        cost_price: parseFloat(formCostPrice) ? parseFloat(formCostPrice).toFixed(2) : undefined,
        initial_stock: parseInt(formStock, 10) || 0,
        reorder_threshold: parseInt(formThreshold, 10) || 5,
      };

      await createProduct(token, businessId, payload);
      setIsCreateOpen(false);
      setSuccessMsg(`Product "${payload.name}" created successfully.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadProducts();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create product');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId || !editingProduct) return;

    if (!formName.trim()) {
      setFormError('Product Name is required');
      return;
    }

    const price = parseFloat(formUnitPrice);
    if (isNaN(price) || price < 0) {
      setFormError('Unit price must be a valid non-negative amount');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      await updateProduct(token, businessId, editingProduct.id, {
        name: formName.trim(),
        description: formDesc.trim() || undefined,
        unit_price: price.toFixed(2),
        cost_price: parseFloat(formCostPrice) ? parseFloat(formCostPrice).toFixed(2) : undefined,
      });

      setEditingProduct(null);
      setSuccessMsg(`Product "${formName}" updated successfully.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadProducts();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to update product');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeactivate = async (product: Product) => {
    if (!token || !businessId) return;
    const confirmed = window.confirm(
      `Are you sure you want to deactivate product "${product.name}"? Active catalog searches will omit it.`
    );
    if (!confirmed) return;

    try {
      await deactivateProduct(token, businessId, product.id);
      setSuccessMsg(`Product "${product.name}" deactivated.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await loadProducts();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to deactivate product');
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
            Sign in as an operator with confirmed business membership to manage products.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="orq-ops-container">
      <div className="orq-ops-header">
        <div>
          <h1 className="orq-ops-title">Product Catalog</h1>
          <p className="orq-ops-subtitle">
            Manage product titles, SKUs, sales pricing, and catalog availability.
          </p>
        </div>
        <div className="orq-ops-header-actions">
          {canManage && (
            <Button variant="primary" onClick={handleOpenCreate}>
              <PlusIcon size={16} />
              <span>New Product</span>
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
            placeholder="Search by name or SKU..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="orq-ops-filters">
          <span className="orq-cell-mono">{total} total products</span>
          <button
            type="button"
            className="orq-btn-sm"
            onClick={() => loadProducts()}
            disabled={isLoading}
            title="Refresh product catalog"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="orq-ops-table-wrapper">
        <table className="orq-ops-table" aria-label="Product catalog table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Product Name</th>
              <th>Unit Price</th>
              <th>Stock</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-loading">
                    <LoadingSpinner size="sm" label="Loading catalog records..." />
                  </div>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-error">
                    <AlertCircleIcon size={20} />
                    <p>{error}</p>
                    <Button variant="secondary" size="sm" onClick={() => loadProducts()}>
                      Retry
                    </Button>
                  </div>
                </td>
              </tr>
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <div className="orq-ops-table-empty">
                    <p>
                      {search.trim()
                        ? `No products match "${search.trim()}". Try adjusting your search query.`
                        : 'No products found. Add your first item using "New Product" to build your inventory.'}
                    </p>
                    {canManage && !search.trim() && (
                      <Button variant="primary" size="sm" onClick={handleOpenCreate}>
                        <PlusIcon size={14} />
                        <span>New Product</span>
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              products.map((p) => (
                <tr key={p.id}>
                  <td>
                    <span className="orq-cell-mono">{p.sku}</span>
                  </td>
                  <td>
                    <strong>{p.name}</strong>
                    {p.description && (
                      <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                        {p.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className="orq-cell-price">
                      {formatCurrency(p.unit_price, activeCurrency, { useGrouping: false })}
                    </span>
                  </td>
                  <td>
                    <span>{p.quantity_on_hand}</span>{' '}
                    {p.is_low_stock && (
                      <Badge variant="degraded" style={{ marginLeft: '4px' }}>
                        Low Stock
                      </Badge>
                    )}
                  </td>
                  <td>
                    {p.is_active ? (
                      <Badge variant="operational">Active</Badge>
                    ) : (
                      <Badge variant="not_connected">Inactive</Badge>
                    )}
                  </td>
                  <td>
                    <div className="orq-cell-actions">
                      {canManage && (
                        <>
                          <button
                            type="button"
                            className="orq-btn-sm"
                            onClick={() => handleOpenEdit(p)}
                          >
                            Edit
                          </button>
                          {p.is_active && (
                            <button
                              type="button"
                              className="orq-btn-sm"
                              onClick={() => handleDeactivate(p)}
                            >
                              Deactivate
                            </button>
                          )}
                        </>
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

      {/* Create Product Modal */}
      {isCreateOpen && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal">
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">Create New Product</h2>
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
                  <label htmlFor="product-sku-input" className="orq-form-label">SKU (Unique)</label>
                  <input
                    id="product-sku-input"
                    type="text"
                    required
                    className="orq-form-input"
                    placeholder="e.g. WIDGET-100"
                    value={formSku}
                    onChange={(e) => setFormSku(e.target.value)}
                  />
                </div>
                <div className="orq-form-group">
                  <label htmlFor="product-name-input" className="orq-form-label">Product Name</label>
                  <input
                    id="product-name-input"
                    type="text"
                    required
                    className="orq-form-input"
                    placeholder="e.g. Standard Widget"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                  />
                </div>
              </div>

              <div className="orq-form-group">
                <label htmlFor="product-desc-input" className="orq-form-label">Description (Optional)</label>
                <textarea
                  id="product-desc-input"
                  className="orq-form-textarea"
                  placeholder="Detailed specifications or notes"
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                />
              </div>

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label htmlFor="product-unit-price-input" className="orq-form-label">Unit Price ({currencySymbol})</label>
                  <input
                    id="product-unit-price-input"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    className="orq-form-input"
                    value={formUnitPrice}
                    onChange={(e) => setFormUnitPrice(e.target.value)}
                  />
                </div>
                <div className="orq-form-group">
                  <label htmlFor="product-cost-price-input" className="orq-form-label">Cost Price ({currencySymbol})</label>
                  <input
                    id="product-cost-price-input"
                    type="number"
                    step="0.01"
                    min="0"
                    className="orq-form-input"
                    value={formCostPrice}
                    onChange={(e) => setFormCostPrice(e.target.value)}
                  />
                </div>
              </div>

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label htmlFor="product-stock-input" className="orq-form-label">Initial Stock Quantity</label>
                  <input
                    id="product-stock-input"
                    type="number"
                    min="0"
                    className="orq-form-input"
                    value={formStock}
                    onChange={(e) => setFormStock(e.target.value)}
                  />
                </div>
                <div className="orq-form-group">
                  <label htmlFor="product-threshold-input" className="orq-form-label">Reorder Threshold</label>
                  <input
                    id="product-threshold-input"
                    type="number"
                    min="0"
                    className="orq-form-input"
                    value={formThreshold}
                    onChange={(e) => setFormThreshold(e.target.value)}
                  />
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
                  {isSubmitting ? 'Creating Product...' : 'Create Product'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Product Modal */}
      {editingProduct && (
        <div className="orq-ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="orq-ops-modal">
            <div className="orq-ops-modal-header">
              <h2 className="orq-ops-modal-title">Edit Product: {editingProduct.sku}</h2>
              <button
                type="button"
                className="orq-ops-modal-close"
                onClick={() => setEditingProduct(null)}
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
                <label className="orq-form-label">Product Name</label>
                <input
                  type="text"
                  required
                  className="orq-form-input"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                />
              </div>

              <div className="orq-form-group">
                <label className="orq-form-label">Description</label>
                <textarea
                  className="orq-form-textarea"
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                />
              </div>

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label className="orq-form-label">Unit Price ({currencySymbol})</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    className="orq-form-input"
                    value={formUnitPrice}
                    onChange={(e) => setFormUnitPrice(e.target.value)}
                  />
                </div>
                <div className="orq-form-group">
                  <label className="orq-form-label">Cost Price ({currencySymbol})</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className="orq-form-input"
                    value={formCostPrice}
                    onChange={(e) => setFormCostPrice(e.target.value)}
                  />
                </div>
              </div>

              <div className="orq-form-actions">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setEditingProduct(null)}
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

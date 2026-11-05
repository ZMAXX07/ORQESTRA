import {
  Customer,
  CustomerCreateInput,
  CustomerListResponse,
  CustomerUpdateInput,
  InventoryListResponse,
  Order,
  OrderCreateInput,
  OrderListResponse,
  OrderUpdateInput,
  Product,
  ProductCreateInput,
  ProductListResponse,
  ProductUpdateInput,
  StockAdjustmentInput,
  StockMovementListResponse,
  Invoice,
  InvoiceListResponse,
  OrderIntakeResponse,
} from '../types/operations';
import { ApiErrorResponse } from '../types/api';
import { ApiServiceError, getApiBaseUrl } from './api';

async function request<T>(
  endpoint: string,
  token: string,
  businessId: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${getApiBaseUrl()}${endpoint}`;
  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${token}`);
  headers.set('X-Business-ID', businessId);
  headers.set('Accept', 'application/json');

  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const controller = new AbortController();
  const timeoutMs = 15000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `Server returned HTTP ${response.status} (${response.statusText})`;
      let errorCode = `HTTP_${response.status}`;
      let errorDetails: unknown = undefined;

      try {
        const errorData = (await response.json()) as ApiErrorResponse;
        if (errorData?.error?.message) {
          errorMessage = errorData.error.message;
          errorCode = errorData.error.code || errorCode;
          errorDetails = errorData.error.details;
        }
      } catch {
        // Fallback
      }

      throw new ApiServiceError(errorMessage, errorCode, errorDetails);
    }

    return (await response.json()) as T;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof ApiServiceError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiServiceError(
        'Request timed out. Please check your connection and retry.',
        'REQUEST_TIMEOUT'
      );
    }
    const rawMsg = err instanceof Error ? err.message : 'Network request failed';
    const friendlyMsg =
      rawMsg === 'Failed to fetch'
        ? 'Unable to connect to the backend server. Verify the server is running and reachable.'
        : rawMsg;
    throw new ApiServiceError(friendlyMsg, 'NETWORK_ERROR');
  }
}

// -----------------------------------------------------------------------------
// Products
// -----------------------------------------------------------------------------

export async function fetchProducts(
  token: string,
  businessId: string,
  params: { search?: string; is_active?: boolean; page?: number; page_size?: number } = {}
): Promise<ProductListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.is_active !== undefined) query.set('is_active', String(params.is_active));
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));

  return request<ProductListResponse>(
    `/api/v1/products?${query.toString()}`,
    token,
    businessId,
    { method: 'GET' }
  );
}

export async function createProduct(
  token: string,
  businessId: string,
  data: ProductCreateInput
): Promise<Product> {
  return request<Product>('/api/v1/products', token, businessId, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateProduct(
  token: string,
  businessId: string,
  productId: string,
  data: ProductUpdateInput
): Promise<Product> {
  return request<Product>(`/api/v1/products/${productId}`, token, businessId, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deactivateProduct(
  token: string,
  businessId: string,
  productId: string
): Promise<Product> {
  return request<Product>(`/api/v1/products/${productId}/deactivate`, token, businessId, {
    method: 'PATCH',
  });
}

// -----------------------------------------------------------------------------
// Inventory
// -----------------------------------------------------------------------------

export async function fetchInventory(
  token: string,
  businessId: string,
  params: { search?: string; low_stock_only?: boolean; page?: number; page_size?: number } = {}
): Promise<InventoryListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.low_stock_only) query.set('low_stock_only', 'true');
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));

  return request<InventoryListResponse>(
    `/api/v1/inventory?${query.toString()}`,
    token,
    businessId,
    { method: 'GET' }
  );
}

export async function adjustStock(
  token: string,
  businessId: string,
  data: StockAdjustmentInput
): Promise<{ inventory_id: string; product_id: string; new_quantity: number; movement_id: string }> {
  return request('/api/v1/inventory/adjust', token, businessId, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function fetchStockMovements(
  token: string,
  businessId: string,
  params: { product_id?: string; page?: number; page_size?: number } = {}
): Promise<StockMovementListResponse> {
  const query = new URLSearchParams();
  if (params.product_id) query.set('product_id', params.product_id);
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));

  return request<StockMovementListResponse>(
    `/api/v1/inventory/history?${query.toString()}`,
    token,
    businessId,
    { method: 'GET' }
  );
}

// -----------------------------------------------------------------------------
// Customers
// -----------------------------------------------------------------------------

export async function fetchCustomers(
  token: string,
  businessId: string,
  params: { search?: string; is_active?: boolean; page?: number; page_size?: number } = {}
): Promise<CustomerListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.is_active !== undefined) query.set('is_active', String(params.is_active));
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));

  return request<CustomerListResponse>(
    `/api/v1/customers?${query.toString()}`,
    token,
    businessId,
    { method: 'GET' }
  );
}

export async function createCustomer(
  token: string,
  businessId: string,
  data: CustomerCreateInput
): Promise<Customer> {
  return request<Customer>('/api/v1/customers', token, businessId, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateCustomer(
  token: string,
  businessId: string,
  customerId: string,
  data: CustomerUpdateInput
): Promise<Customer> {
  return request<Customer>(`/api/v1/customers/${customerId}`, token, businessId, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deactivateCustomer(
  token: string,
  businessId: string,
  customerId: string
): Promise<Customer> {
  return request<Customer>(`/api/v1/customers/${customerId}/deactivate`, token, businessId, {
    method: 'PATCH',
  });
}

// -----------------------------------------------------------------------------
// Orders
// -----------------------------------------------------------------------------

export async function fetchOrders(
  token: string,
  businessId: string,
  params: { status?: string; customer_id?: string; page?: number; page_size?: number } = {}
): Promise<OrderListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.customer_id) query.set('customer_id', params.customer_id);
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));

  return request<OrderListResponse>(
    `/api/v1/orders?${query.toString()}`,
    token,
    businessId,
    { method: 'GET' }
  );
}

export async function fetchOrder(
  token: string,
  businessId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/api/v1/orders/${orderId}`, token, businessId, { method: 'GET' });
}

export async function createOrder(
  token: string,
  businessId: string,
  data: OrderCreateInput
): Promise<Order> {
  return request<Order>('/api/v1/orders', token, businessId, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateOrder(
  token: string,
  businessId: string,
  orderId: string,
  data: OrderUpdateInput
): Promise<Order> {
  return request<Order>(`/api/v1/orders/${orderId}`, token, businessId, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function submitOrder(
  token: string,
  businessId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/api/v1/orders/${orderId}/submit`, token, businessId, {
    method: 'POST',
  });
}

export async function approveOrder(
  token: string,
  businessId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/api/v1/orders/${orderId}/approve`, token, businessId, {
    method: 'POST',
  });
}

export async function rejectOrder(
  token: string,
  businessId: string,
  orderId: string,
  reason?: string
): Promise<Order> {
  return request<Order>(`/api/v1/orders/${orderId}/reject`, token, businessId, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function cancelOrder(
  token: string,
  businessId: string,
  orderId: string,
  reason?: string
): Promise<Order> {
  return request<Order>(`/api/v1/orders/${orderId}/cancel`, token, businessId, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

// -----------------------------------------------------------------------------
// Phase 5 Invoices & AI Intake
// -----------------------------------------------------------------------------

export async function extractOrderFromText(
  token: string,
  businessId: string,
  message: string
): Promise<OrderIntakeResponse> {
  return request<OrderIntakeResponse>('/api/v1/orders/ai-intake', token, businessId, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

export async function fetchInvoices(
  token: string,
  businessId: string,
  params: { page?: number; page_size?: number } = {}
): Promise<InvoiceListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));

  return request<InvoiceListResponse>(
    `/api/v1/invoices?${query.toString()}`,
    token,
    businessId,
    { method: 'GET' }
  );
}

export async function fetchInvoice(
  token: string,
  businessId: string,
  invoiceId: string
): Promise<Invoice> {
  return request<Invoice>(`/api/v1/invoices/${invoiceId}`, token, businessId, {
    method: 'GET',
  });
}

export async function allocateInvoiceForOrder(
  token: string,
  businessId: string,
  orderId: string,
  dueDate?: string
): Promise<Invoice> {
  return request<Invoice>(`/api/v1/invoices/orders/${orderId}/allocate`, token, businessId, {
    method: 'POST',
    body: dueDate ? JSON.stringify({ due_date: dueDate }) : undefined,
  });
}

export async function downloadInvoicePdf(
  token: string,
  businessId: string,
  invoiceId: string
): Promise<Blob> {
  const url = `${getApiBaseUrl()}/api/v1/invoices/${invoiceId}/pdf`;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Business-ID': businessId,
    },
  });

  if (!response.ok) {
    let errorData: ApiErrorResponse | undefined;
    try {
      errorData = (await response.json()) as ApiErrorResponse;
    } catch {
      // ignore
    }
    throw new ApiServiceError(
      errorData?.error?.message || `Failed to download invoice PDF (${response.status})`,
      String(response.status),
      errorData
    );
  }

  return response.blob();
}


/**
 * Typed domain interfaces for Phase 3 Core Business Operations.
 */

export interface Product {
  id: string;
  business_id: string;
  sku: string;
  name: string;
  description?: string;
  unit_price: string;
  cost_price?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  quantity_on_hand: number;
  reorder_threshold: number;
  is_low_stock: boolean;
}

export interface ProductCreateInput {
  sku: string;
  name: string;
  description?: string;
  unit_price: string;
  cost_price?: string;
  initial_stock?: number;
  reorder_threshold?: number;
}

export interface ProductUpdateInput {
  name?: string;
  description?: string;
  unit_price?: string;
  cost_price?: string;
  is_active?: boolean;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
}

export interface InventoryItem {
  id: string;
  business_id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  unit_price: string;
  quantity_on_hand: number;
  reorder_threshold: number;
  is_low_stock: boolean;
  updated_at: string;
}

export interface InventoryListResponse {
  items: InventoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_low_stock: number;
}

export interface StockAdjustmentInput {
  product_id: string;
  quantity_change: number;
  movement_type: 'adjustment' | 'restock' | 'return';
  notes: string;
}

export interface StockMovement {
  id: string;
  business_id: string;
  product_id: string;
  product_name?: string;
  product_sku?: string;
  quantity_change: number;
  movement_type: string;
  reference_id?: string;
  notes?: string;
  created_by?: string;
  created_at: string;
}

export interface StockMovementListResponse {
  items: StockMovement[];
  total: number;
  page: number;
  page_size: number;
}

export interface Customer {
  id: string;
  business_id: string;
  name: string;
  email?: string;
  phone?: string;
  address?: string;
  notes?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreateInput {
  name: string;
  email?: string;
  phone?: string;
  address?: string;
  notes?: string;
}

export interface CustomerUpdateInput {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
  notes?: string;
  is_active?: boolean;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
}

export type OrderStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'fulfilled'
  | 'cancelled';

export interface OrderItem {
  id: string;
  order_id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: string;
  total_price: string;
}

export interface OrderItemInput {
  product_id: string;
  quantity: number;
  unit_price?: string;
}

export interface Order {
  id: string;
  business_id: string;
  customer_id?: string;
  customer_name?: string;
  order_number: string;
  status: OrderStatus;
  subtotal: string;
  tax: string;
  total_amount: string;
  notes?: string;
  created_by?: string;
  approved_by?: string;
  approved_at?: string;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
}

export interface OrderCreateInput {
  customer_id?: string;
  notes?: string;
  items: OrderItemInput[];
}

export interface OrderUpdateInput {
  customer_id?: string;
  notes?: string;
  items?: OrderItemInput[];
}

export interface OrderListResponse {
  items: Order[];
  total: number;
  page: number;
  page_size: number;
}

// -----------------------------------------------------------------------------
// Phase 5 Invoices & AI Order Intake
// -----------------------------------------------------------------------------

export type InvoiceStatus = 'draft' | 'issued' | 'paid' | 'void' | 'cancelled';

export interface InvoiceCustomerSnapshot {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
}

export interface InvoiceLineItemSnapshot {
  product_name?: string;
  product_sku?: string;
  quantity?: number;
  unit_price?: string;
  total_price?: string;
}

export interface Invoice {
  id: string;
  business_id: string;
  order_id: string;
  customer_id?: string;
  invoice_number: string;
  status: InvoiceStatus;
  amount_due: string;
  due_date?: string;
  pdf_storage_path?: string;
  customer_snapshot?: InvoiceCustomerSnapshot;
  line_items_snapshot?: InvoiceLineItemSnapshot[];
  created_at: string;
  updated_at: string;
}

export interface InvoiceListResponse {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface CandidateProductMatch {
  id: string;
  sku: string;
  name: string;
  unit_price: string;
  quantity_on_hand: number;
}

export type CandidateMatchStatus = 'matched' | 'ambiguous' | 'unmatched';

export interface CandidateItemMatch {
  candidate_product_name: string;
  raw_text: string;
  variant?: string;
  requested_quantity: number;
  match_status: CandidateMatchStatus;
  matched_product?: CandidateProductMatch;
  potential_matches: CandidateProductMatch[];
  unit_price?: string;
  line_total?: string;
}

export interface OrderIntakeResponse {
  raw_message: string;
  extracted_customer_name?: string;
  matched_customer_id?: string;
  matched_customer_name?: string;
  delivery_instructions?: string;
  notes?: string;
  items: CandidateItemMatch[];
  subtotal: string;
  tax: string;
  total_amount: string;
  validation_errors: string[];
  can_create_draft: boolean;
}


-- ==============================================================================
-- ORQESTRA DATABASE MIGRATION: Core Schema Foundation
-- Migration: 20261022000001_core_schema.sql
-- Description: Creates core business tables, enums, constraints, and indexes.
-- Hardened: Composite foreign keys enforce cross-table business tenancy isolation.
-- ==============================================================================

-- 1. Custom Types and Enums
DO $$ BEGIN
    CREATE TYPE app_role AS ENUM ('owner', 'admin', 'staff');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE order_status AS ENUM ('draft', 'pending_approval', 'approved', 'fulfilled', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE invoice_status AS ENUM ('draft', 'issued', 'paid', 'void', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE stock_movement_type AS ENUM ('initial', 'restock', 'order_fulfillment', 'adjustment', 'return');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Utility Trigger Function: Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc', now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------------------------
-- Table 1: businesses
-- Purpose: Root multi-tenant entity representing an independent business.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE TRIGGER trg_businesses_updated_at
    BEFORE UPDATE ON businesses
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------------------------
-- Table 2: business_members
-- Purpose: Associates Supabase auth users with businesses and assigns role.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS business_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL, -- Corresponds to auth.users.id in Supabase
    role app_role NOT NULL DEFAULT 'staff',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_business_member UNIQUE (business_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_business_members_user ON business_members(user_id);
CREATE INDEX IF NOT EXISTS idx_business_members_business ON business_members(business_id);

CREATE TRIGGER trg_business_members_updated_at
    BEFORE UPDATE ON business_members
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------------------------
-- Table 3: products
-- Purpose: Product catalog scoped to a specific business.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    sku VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    cost_price NUMERIC(12, 2) CHECK (cost_price >= 0),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_products_business_sku UNIQUE (business_id, sku),
    CONSTRAINT uq_products_business_id UNIQUE (business_id, id)
);

CREATE INDEX IF NOT EXISTS idx_products_business ON products(business_id);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(business_id, sku);

CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------------------------
-- Table 4: inventory
-- Purpose: Real-time stock levels for products within a business.
-- Hardened: Foreign key ensures product belongs to the exact same business.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    reorder_threshold INT NOT NULL DEFAULT 5 CHECK (reorder_threshold >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_inventory_business_product UNIQUE (business_id, product_id),
    CONSTRAINT fk_inventory_business_product FOREIGN KEY (business_id, product_id)
        REFERENCES products(business_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_inventory_business ON inventory(business_id);
CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id);

CREATE TRIGGER trg_inventory_updated_at
    BEFORE UPDATE ON inventory
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------------------------
-- Table 5: customers
-- Purpose: Customer directory scoped to each business.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_customers_business_id UNIQUE (business_id, id)
);

CREATE INDEX IF NOT EXISTS idx_customers_business ON customers(business_id);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(business_id, email);

CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------------------------
-- Table 6: orders
-- Purpose: Customer orders with deterministic amounts and approval status.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    customer_id UUID,
    order_number VARCHAR(50) NOT NULL,
    status order_status NOT NULL DEFAULT 'draft',
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal >= 0),
    tax NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (tax >= 0),
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (total_amount >= 0),
    notes TEXT,
    created_by UUID, -- References auth.users.id
    approved_by UUID, -- References auth.users.id
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_orders_business_order_number UNIQUE (business_id, order_number),
    CONSTRAINT uq_orders_business_id UNIQUE (business_id, id),
    CONSTRAINT fk_orders_business_customer FOREIGN KEY (business_id, customer_id)
        REFERENCES customers(business_id, id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_business ON orders(business_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(business_id, status);

CREATE TRIGGER trg_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------------------------
-- Table 7: order_items
-- Purpose: Line items belonging to orders with quantity and pricing.
-- Hardened: Composite foreign keys guarantee both order and product belong to business.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    order_id UUID NOT NULL,
    product_id UUID NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    total_price NUMERIC(12, 2) NOT NULL CHECK (total_price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_order_items_business_order FOREIGN KEY (business_id, order_id)
        REFERENCES orders(business_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_order_items_business_product FOREIGN KEY (business_id, product_id)
        REFERENCES products(business_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_business ON order_items(business_id);

-- ------------------------------------------------------------------------------
-- Table 8: invoices
-- Purpose: Invoices generated from orders with deterministic payment totals.
-- Hardened: Composite foreign keys prevent cross-tenant billing attachments.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    order_id UUID,
    customer_id UUID NOT NULL,
    invoice_number VARCHAR(50) NOT NULL,
    status invoice_status NOT NULL DEFAULT 'draft',
    amount_due NUMERIC(12, 2) NOT NULL CHECK (amount_due >= 0),
    due_date DATE NOT NULL,
    pdf_storage_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_invoices_business_invoice_number UNIQUE (business_id, invoice_number),
    CONSTRAINT fk_invoices_business_customer FOREIGN KEY (business_id, customer_id)
        REFERENCES customers(business_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_business_order FOREIGN KEY (business_id, order_id)
        REFERENCES orders(business_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_invoices_business ON invoices(business_id);
CREATE INDEX IF NOT EXISTS idx_invoices_order ON invoices(order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);

CREATE TRIGGER trg_invoices_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------------------------
-- Table 9: stock_movements
-- Purpose: Auditable ledger of all stock quantity adjustments.
-- Hardened: Composite foreign key ensures movement references business-owned product.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL,
    quantity_change INT NOT NULL,
    movement_type stock_movement_type NOT NULL,
    reference_id UUID,
    notes TEXT,
    created_by UUID, -- References auth.users.id
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_stock_movements_business_product FOREIGN KEY (business_id, product_id)
        REFERENCES products(business_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_business ON stock_movements(business_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id);

-- ------------------------------------------------------------------------------
-- Table 10: audit_logs
-- Purpose: Immutable audit log recording consequential business events.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    user_id UUID, -- References auth.users.id
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_business ON audit_logs(business_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

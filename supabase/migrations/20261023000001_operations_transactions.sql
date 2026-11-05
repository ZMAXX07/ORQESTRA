-- ==============================================================================
-- ORQESTRA DATABASE MIGRATION: Phase 3 Operations & Atomic Transactions
-- Migration: 20261023000001_operations_transactions.sql
-- Description: Adds 'rejected' to order_status enum, adds customer active status,
--              establishes performance indexes, and provides atomic PostgreSQL
--              functions for concurrency-safe stock deduction and order approval.
-- ==============================================================================

-- 1. Extend order_status enum with 'rejected'
ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'rejected';

-- 2. Add is_active column to customers
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;

-- 3. Business-scoped filtering indexes
CREATE INDEX IF NOT EXISTS idx_customers_business_active ON customers(business_id, is_active);
CREATE INDEX IF NOT EXISTS idx_products_business_active ON products(business_id, is_active);
CREATE INDEX IF NOT EXISTS idx_orders_business_created_at ON orders(business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_business_reorder ON inventory(business_id, quantity_on_hand, reorder_threshold);

-- ------------------------------------------------------------------------------
-- 4. Atomic Manual Stock Adjustment Function
-- Ensures stock changes cannot create negative quantities and logs movements.
-- Security: Independently verifies caller identity, business membership, and admin role.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.adjust_stock_atomic(
    p_business_id UUID,
    p_product_id UUID,
    p_quantity_change INT,
    p_movement_type stock_movement_type,
    p_notes TEXT,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    inventory_id UUID,
    product_id UUID,
    new_quantity INT,
    movement_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_caller_role TEXT;
    v_auth_uid UUID;
    v_actor_id UUID;
    v_inv_id UUID;
    v_current_qty INT;
    v_new_qty INT;
    v_movement_id UUID;
BEGIN
    -- 1. Input parameter validation
    IF p_business_id IS NULL THEN
        RAISE EXCEPTION 'Business ID is required';
    END IF;
    IF p_product_id IS NULL THEN
        RAISE EXCEPTION 'Product ID is required';
    END IF;
    IF p_quantity_change IS NULL OR p_quantity_change = 0 THEN
        RAISE EXCEPTION 'Quantity change must be non-zero';
    END IF;
    IF p_notes IS NULL OR length(trim(p_notes)) < 3 THEN
        RAISE EXCEPTION 'A mandatory audit reason (minimum 3 characters) is required';
    END IF;
    IF p_movement_type IS NULL THEN
        RAISE EXCEPTION 'Movement type is required';
    END IF;

    -- 2. Authenticated caller and actor resolution
    v_caller_role := coalesce(current_setting('request.jwt.claim.role', true), auth.role()::text, '');
    v_auth_uid := public.get_auth_user_id();

    IF v_caller_role = 'service_role' THEN
        -- Trusted server-side execution: require p_user_id
        IF p_user_id IS NULL THEN
            RAISE EXCEPTION 'Actor ID (p_user_id) is required for service_role invocation';
        END IF;
        v_actor_id := p_user_id;
    ELSE
        -- Direct authenticated RPC execution: must be authenticated
        IF v_auth_uid IS NULL THEN
            RAISE EXCEPTION 'Unauthenticated caller cannot execute stock adjustments';
        END IF;
        IF p_user_id IS NOT NULL AND p_user_id != v_auth_uid THEN
            RAISE EXCEPTION 'Actor identity mismatch: caller % cannot act as user %', v_auth_uid, p_user_id;
        END IF;
        v_actor_id := v_auth_uid;
    END IF;

    -- 3. Authorization check: actor must have active admin or owner role in target business
    IF NOT public.has_business_role(p_business_id, v_actor_id, 'admin') THEN
        RAISE EXCEPTION 'Access denied: user % does not have active admin or owner role in business %', v_actor_id, p_business_id;
    END IF;

    -- 4. Verify product belongs to business
    IF NOT EXISTS (
        SELECT 1 FROM products
        WHERE id = p_product_id AND business_id = p_business_id
    ) THEN
        RAISE EXCEPTION 'Product % does not belong to business %', p_product_id, p_business_id;
    END IF;

    -- 5. Lock inventory row for update
    SELECT id, quantity_on_hand
    INTO v_inv_id, v_current_qty
    FROM inventory
    WHERE business_id = p_business_id AND product_id = p_product_id
    FOR UPDATE;

    IF v_inv_id IS NULL THEN
        RAISE EXCEPTION 'Inventory record not found for product % in business %', p_product_id, p_business_id;
    END IF;

    -- 6. Calculate and validate new quantity
    v_new_qty := v_current_qty + p_quantity_change;
    IF v_new_qty < 0 THEN
        RAISE EXCEPTION 'Stock adjustment rejected: would result in negative quantity (%) from current (%)', v_new_qty, v_current_qty;
    END IF;

    -- 7. Update inventory
    UPDATE inventory
    SET quantity_on_hand = v_new_qty, updated_at = timezone('utc', now())
    WHERE id = v_inv_id;

    -- 8. Insert immutable stock movement record
    INSERT INTO stock_movements (
        business_id,
        product_id,
        quantity_change,
        movement_type,
        notes,
        created_by,
        created_at
    )
    VALUES (
        p_business_id,
        p_product_id,
        p_quantity_change,
        p_movement_type,
        trim(p_notes),
        v_actor_id,
        timezone('utc', now())
    )
    RETURNING id INTO v_movement_id;

    -- 9. Record consequential audit log
    INSERT INTO audit_logs (
        business_id,
        user_id,
        action,
        entity_type,
        entity_id,
        old_values,
        new_values,
        created_at
    )
    VALUES (
        p_business_id,
        v_actor_id,
        'stock.adjusted',
        'inventory',
        v_inv_id,
        jsonb_build_object('quantity_on_hand', v_current_qty),
        jsonb_build_object('quantity_on_hand', v_new_qty, 'quantity_change', p_quantity_change, 'movement_id', v_movement_id),
        timezone('utc', now())
    );

    RETURN QUERY SELECT v_inv_id, p_product_id, v_new_qty, v_movement_id;
END;
$$;

-- ------------------------------------------------------------------------------
-- 5. Atomic Order Approval & Stock Reservation/Deduction Function
-- Concurrency control: Locks order and inventory rows FOR UPDATE.
-- Ensures zero overselling, prevents double-approval, and rolls back on failure.
-- Security: Independently verifies caller identity, business membership, and admin role.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.approve_order_atomic(
    p_order_id UUID,
    p_user_id UUID DEFAULT NULL,
    p_business_id UUID DEFAULT NULL
)
RETURNS TABLE (
    order_id UUID,
    order_status order_status,
    total_items_deducted INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_caller_role TEXT;
    v_auth_uid UUID;
    v_actor_id UUID;
    v_order_status order_status;
    v_order_business_id UUID;
    v_item RECORD;
    v_current_stock INT;
    v_items_count INT := 0;
BEGIN
    -- 1. Input parameter validation
    IF p_order_id IS NULL THEN
        RAISE EXCEPTION 'Order ID is required';
    END IF;

    -- 2. Authenticated caller and actor resolution
    v_caller_role := coalesce(current_setting('request.jwt.claim.role', true), auth.role()::text, '');
    v_auth_uid := public.get_auth_user_id();

    IF v_caller_role = 'service_role' THEN
        -- Trusted server-side execution: require p_user_id
        IF p_user_id IS NULL THEN
            RAISE EXCEPTION 'Actor ID (p_user_id) is required for service_role invocation';
        END IF;
        v_actor_id := p_user_id;
    ELSE
        -- Direct authenticated RPC execution: must be authenticated
        IF v_auth_uid IS NULL THEN
            RAISE EXCEPTION 'Unauthenticated caller cannot approve orders';
        END IF;
        IF p_user_id IS NOT NULL AND p_user_id != v_auth_uid THEN
            RAISE EXCEPTION 'Actor identity mismatch: caller % cannot act as user %', v_auth_uid, p_user_id;
        END IF;
        v_actor_id := v_auth_uid;
    END IF;

    -- 3. Lock order row FOR UPDATE and determine owning business
    SELECT status, business_id
    INTO v_order_status, v_order_business_id
    FROM orders
    WHERE id = p_order_id
    FOR UPDATE;

    IF v_order_status IS NULL THEN
        RAISE EXCEPTION 'Order % not found', p_order_id;
    END IF;

    -- If caller supplied p_business_id, verify it matches the order's business_id
    IF p_business_id IS NOT NULL AND p_business_id != v_order_business_id THEN
        RAISE EXCEPTION 'Business ID mismatch: order % belongs to % but % was specified',
            p_order_id, v_order_business_id, p_business_id;
    END IF;

    -- 4. Authorization check: actor must have active admin or owner role in order's business
    IF NOT public.has_business_role(v_order_business_id, v_actor_id, 'admin') THEN
        RAISE EXCEPTION 'Access denied: user % does not have active admin or owner role in business %',
            v_actor_id, v_order_business_id;
    END IF;

    -- 5. Order state machine validation
    IF v_order_status != 'pending_approval' THEN
        RAISE EXCEPTION 'Order % cannot be approved: status must be pending_approval, current status is %',
            p_order_id, v_order_status;
    END IF;

    -- 6. Verify cross-business item integrity
    IF EXISTS (
        SELECT 1 FROM order_items
        WHERE order_items.order_id = p_order_id AND business_id != v_order_business_id
    ) THEN
        RAISE EXCEPTION 'Integrity violation: order % contains line items belonging to another business', p_order_id;
    END IF;

    -- 7. Validate all order items have sufficient stock by locking each inventory row FOR UPDATE
    FOR v_item IN
        SELECT oi.product_id, oi.quantity, p.name AS product_name
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id AND p.business_id = v_order_business_id
        WHERE oi.order_id = p_order_id AND oi.business_id = v_order_business_id
        ORDER BY oi.product_id -- Sorted to prevent deadlocks
    LOOP
        v_items_count := v_items_count + 1;

        SELECT quantity_on_hand
        INTO v_current_stock
        FROM inventory
        WHERE business_id = v_order_business_id AND product_id = v_item.product_id
        FOR UPDATE;

        IF v_current_stock IS NULL THEN
            RAISE EXCEPTION 'Inventory record missing for product % ("%")', v_item.product_id, v_item.product_name;
        END IF;

        IF v_current_stock < v_item.quantity THEN
            RAISE EXCEPTION 'Insufficient stock for product "%" (ID %): requested %, available %',
                v_item.product_name, v_item.product_id, v_item.quantity, v_current_stock;
        END IF;
    END LOOP;

    IF v_items_count = 0 THEN
        RAISE EXCEPTION 'Order % cannot be approved: order contains no line items', p_order_id;
    END IF;

    -- 8. All items confirmed: Deduct inventory and insert stock movement records
    FOR v_item IN
        SELECT oi.product_id, oi.quantity
        FROM order_items oi
        WHERE oi.order_id = p_order_id AND oi.business_id = v_order_business_id
        ORDER BY oi.product_id
    LOOP
        UPDATE inventory
        SET quantity_on_hand = quantity_on_hand - v_item.quantity,
            updated_at = timezone('utc', now())
        WHERE business_id = v_order_business_id AND product_id = v_item.product_id;

        INSERT INTO stock_movements (
            business_id,
            product_id,
            quantity_change,
            movement_type,
            reference_id,
            notes,
            created_by,
            created_at
        )
        VALUES (
            v_order_business_id,
            v_item.product_id,
            -v_item.quantity,
            'order_fulfillment',
            p_order_id,
            'Deducted on order approval',
            v_actor_id,
            timezone('utc', now())
        );
    END LOOP;

    -- 9. Update order to approved status
    UPDATE orders
    SET status = 'approved',
        approved_by = v_actor_id,
        approved_at = timezone('utc', now()),
        updated_at = timezone('utc', now())
    WHERE id = p_order_id AND business_id = v_order_business_id;

    -- 10. Record consequential audit log
    INSERT INTO audit_logs (
        business_id,
        user_id,
        action,
        entity_type,
        entity_id,
        old_values,
        new_values,
        created_at
    )
    VALUES (
        v_order_business_id,
        v_actor_id,
        'order.approved',
        'orders',
        p_order_id,
        jsonb_build_object('status', v_order_status),
        jsonb_build_object('status', 'approved', 'approved_by', v_actor_id, 'items_deducted', v_items_count),
        timezone('utc', now())
    );

    RETURN QUERY SELECT p_order_id, 'approved'::order_status, v_items_count;
END;
$$;

-- ------------------------------------------------------------------------------
-- 6. Atomic Order Cancellation Function
-- Reverses stock if previously approved, or simply cancels draft/pending orders.
-- Security: Independently verifies caller identity, business membership, and admin role.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.cancel_order_atomic(
    p_order_id UUID,
    p_user_id UUID DEFAULT NULL,
    p_business_id UUID DEFAULT NULL,
    p_reason TEXT DEFAULT NULL
)
RETURNS TABLE (
    order_id UUID,
    order_status order_status,
    stock_restored BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_caller_role TEXT;
    v_auth_uid UUID;
    v_actor_id UUID;
    v_order_status order_status;
    v_order_business_id UUID;
    v_item RECORD;
    v_restored BOOLEAN := FALSE;
BEGIN
    -- 1. Input parameter validation
    IF p_order_id IS NULL THEN
        RAISE EXCEPTION 'Order ID is required';
    END IF;

    -- 2. Authenticated caller and actor resolution
    v_caller_role := coalesce(current_setting('request.jwt.claim.role', true), auth.role()::text, '');
    v_auth_uid := public.get_auth_user_id();

    IF v_caller_role = 'service_role' THEN
        -- Trusted server-side execution: require p_user_id
        IF p_user_id IS NULL THEN
            RAISE EXCEPTION 'Actor ID (p_user_id) is required for service_role invocation';
        END IF;
        v_actor_id := p_user_id;
    ELSE
        -- Direct authenticated RPC execution: must be authenticated
        IF v_auth_uid IS NULL THEN
            RAISE EXCEPTION 'Unauthenticated caller cannot cancel orders';
        END IF;
        IF p_user_id IS NOT NULL AND p_user_id != v_auth_uid THEN
            RAISE EXCEPTION 'Actor identity mismatch: caller % cannot act as user %', v_auth_uid, p_user_id;
        END IF;
        v_actor_id := v_auth_uid;
    END IF;

    -- 3. Lock order row FOR UPDATE and determine owning business
    SELECT status, business_id
    INTO v_order_status, v_order_business_id
    FROM orders
    WHERE id = p_order_id
    FOR UPDATE;

    IF v_order_status IS NULL THEN
        RAISE EXCEPTION 'Order % not found', p_order_id;
    END IF;

    -- If caller supplied p_business_id, verify it matches
    IF p_business_id IS NOT NULL AND p_business_id != v_order_business_id THEN
        RAISE EXCEPTION 'Business ID mismatch: order % belongs to % but % was specified',
            p_order_id, v_order_business_id, p_business_id;
    END IF;

    -- 4. Authorization check: actor must have active admin or owner role in order's business
    IF NOT public.has_business_role(v_order_business_id, v_actor_id, 'admin') THEN
        RAISE EXCEPTION 'Access denied: user % does not have active admin or owner role in business %',
            v_actor_id, v_order_business_id;
    END IF;

    -- 5. Order status check
    IF v_order_status IN ('cancelled', 'fulfilled', 'rejected') THEN
        RAISE EXCEPTION 'Order % cannot be cancelled: current status is %', p_order_id, v_order_status;
    END IF;

    -- 6. If previously approved, restore inventory
    IF v_order_status = 'approved' THEN
        FOR v_item IN
            SELECT oi.product_id, oi.quantity
            FROM order_items oi
            WHERE oi.order_id = p_order_id AND oi.business_id = v_order_business_id
            ORDER BY oi.product_id
        LOOP
            UPDATE inventory
            SET quantity_on_hand = quantity_on_hand + v_item.quantity,
                updated_at = timezone('utc', now())
            WHERE business_id = v_order_business_id AND product_id = v_item.product_id;

            INSERT INTO stock_movements (
                business_id,
                product_id,
                quantity_change,
                movement_type,
                reference_id,
                notes,
                created_by,
                created_at
            )
            VALUES (
                v_order_business_id,
                v_item.product_id,
                v_item.quantity,
                'return',
                p_order_id,
                coalesce(trim(p_reason), 'Restored on order cancellation'),
                v_actor_id,
                timezone('utc', now())
            );
        END LOOP;
        v_restored := TRUE;
    END IF;

    -- 7. Update order to cancelled
    UPDATE orders
    SET status = 'cancelled',
        updated_at = timezone('utc', now())
    WHERE id = p_order_id AND business_id = v_order_business_id;

    -- 8. Record audit log
    INSERT INTO audit_logs (
        business_id,
        user_id,
        action,
        entity_type,
        entity_id,
        old_values,
        new_values,
        created_at
    )
    VALUES (
        v_order_business_id,
        v_actor_id,
        'order.cancelled',
        'orders',
        p_order_id,
        jsonb_build_object('status', v_order_status),
        jsonb_build_object('status', 'cancelled', 'stock_restored', v_restored, 'reason', p_reason),
        timezone('utc', now())
    );

    RETURN QUERY SELECT p_order_id, 'cancelled'::order_status, v_restored;
END;
$$;

-- Function Execution Privileges Lockdown
REVOKE EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.approve_order_atomic(UUID, UUID, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.approve_order_atomic(UUID, UUID, UUID) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.cancel_order_atomic(UUID, UUID, UUID, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.cancel_order_atomic(UUID, UUID, UUID, TEXT) TO authenticated, service_role;

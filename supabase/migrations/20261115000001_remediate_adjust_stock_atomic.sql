-- ==============================================================================
-- Migration: 20261115000001_remediate_adjust_stock_atomic.sql
-- Description: Remediates PL/pgSQL 42702 ambiguous column reference in adjust_stock_atomic
-- Defect: RETURNS TABLE declares (product_id UUID) which shadowed inventory.product_id
-- Fix: Fully qualify table columns (inventory.product_id, inventory.business_id)
-- Safety: Preserves function signature, return table, SECURITY DEFINER, and permissions.
-- ==============================================================================

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
SET search_path = public, pg_temp
AS $$
#variable_conflict error
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

    -- 4. Verify product belongs to business (fully qualified)
    IF NOT EXISTS (
        SELECT 1 FROM public.products
        WHERE products.id = p_product_id AND products.business_id = p_business_id
    ) THEN
        RAISE EXCEPTION 'Product % does not belong to business %', p_product_id, p_business_id;
    END IF;

    -- 5. Lock inventory row for update (explicit table qualification eliminates ambiguity)
    SELECT inventory.id, inventory.quantity_on_hand
    INTO v_inv_id, v_current_qty
    FROM public.inventory
    WHERE inventory.business_id = p_business_id AND inventory.product_id = p_product_id
    FOR UPDATE;

    IF v_inv_id IS NULL THEN
        RAISE EXCEPTION 'Inventory record not found for product % in business %', p_product_id, p_business_id;
    END IF;

    -- 6. Calculate and validate new quantity
    v_new_qty := v_current_qty + p_quantity_change;
    IF v_new_qty < 0 THEN
        RAISE EXCEPTION 'Stock adjustment rejected: would result in negative quantity (%) from current (%)', v_new_qty, v_current_qty;
    END IF;

    -- 7. Update inventory (explicitly qualified)
    UPDATE public.inventory
    SET quantity_on_hand = v_new_qty, updated_at = timezone('utc', now())
    WHERE inventory.id = v_inv_id;

    -- 8. Insert immutable stock movement record
    INSERT INTO public.stock_movements (
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
    RETURNING stock_movements.id INTO v_movement_id;

    -- 9. Record consequential audit log
    INSERT INTO public.audit_logs (
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

-- Permissions lockdown
REVOKE EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) FROM anon, PUBLIC;
GRANT EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) TO authenticated, service_role;


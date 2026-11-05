-- ==============================================================================
-- ORQESTRA DATABASE ARCHITECTURE: MIGRATION 20261023000004
-- Phase 5.1: Historical Invoice Immutability Snapshots and Uniqueness Constraints
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- PRE-MIGRATION SAFETY VERIFICATION:
-- Before applying this migration in a database with historical invoices,
-- verify no duplicate invoices already exist for an order:
--   SELECT business_id, order_id, count(*), array_agg(invoice_number)
--   FROM public.invoices
--   WHERE order_id IS NOT NULL
--   GROUP BY business_id, order_id
--   HAVING count(*) > 1;
-- If duplicates exist, investigate and resolve them before creating the unique index.
-- ------------------------------------------------------------------------------

-- 1. Ensure at most one invoice can ever be linked to an order per business
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_business_order_unique
    ON public.invoices(business_id, order_id)
    WHERE order_id IS NOT NULL;

-- 2. Add immutable historical snapshot columns to public.invoices
-- These preserve legal and financial audit integrity by capturing line items,
-- unit rates, product names, SKUs, and billing contact details at issue time.
ALTER TABLE public.invoices
    ADD COLUMN IF NOT EXISTS line_items_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS customer_snapshot JSONB;

-- ------------------------------------------------------------------------------
-- Function: allocate_invoice_atomic (Hardened Version)
-- Purpose: Atomically sequence, allocate, snapshot, and persist an invoice.
-- Concurrency & Lock Ordering:
--   1. Locks public.businesses row FIRST to serialize numbering and eliminate deadlocks.
--   2. Locks public.orders row FOR UPDATE to prevent concurrent status mutation.
-- Snapshots: Captures immutable line_items_snapshot and customer_snapshot.
-- Idempotency: Returns existing invoice if one was already issued for the order.
-- Security: SECURITY DEFINER with pinned search_path, anti-spoofing identity checks,
--           admin role verification, and immutable audit logging.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.allocate_invoice_atomic(
    p_business_id UUID,
    p_order_id UUID,
    p_user_id UUID,
    p_due_date DATE DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_caller_role TEXT;
    v_auth_uid UUID;
    v_actor_id UUID;
    v_biz_id UUID;
    v_order RECORD;
    v_existing_invoice RECORD;
    v_customer_snapshot JSONB;
    v_items_snapshot JSONB;
    v_now TIMESTAMPTZ := timezone('utc', now());
    v_due_date DATE;
    v_prefix TEXT;
    v_seq INT;
    v_invoice_number TEXT;
    v_new_invoice_id UUID;
    v_result JSONB;
BEGIN
    -- 1. Caller authentication resolution
    v_caller_role := coalesce(
        current_setting('request.jwt.claim.role', true),
        auth.role()::text,
        ''
    );

    IF v_caller_role = 'service_role' THEN
        IF p_user_id IS NULL THEN
            RAISE EXCEPTION 'Actor ID must be supplied when executing as service_role'
                USING ERRCODE = '42501';
        END IF;
        v_actor_id := p_user_id;
    ELSIF v_caller_role = 'authenticated' THEN
        v_auth_uid := public.get_auth_user_id();
        IF v_auth_uid IS NULL THEN
            RAISE EXCEPTION 'Unauthenticated caller cannot allocate invoices'
                USING ERRCODE = '42501';
        END IF;
        IF p_user_id IS NOT NULL AND p_user_id <> v_auth_uid THEN
            RAISE EXCEPTION 'Actor identity mismatch: caller % cannot act as user %',
                v_auth_uid, p_user_id
                USING ERRCODE = '42501';
        END IF;
        v_actor_id := v_auth_uid;
    ELSE
        RAISE EXCEPTION 'Unauthorized caller role % for invoice allocation', v_caller_role
            USING ERRCODE = '42501';
    END IF;

    -- 2. Enforce active admin or owner role in target business
    IF NOT public.has_business_role(p_business_id, v_actor_id, 'admin') THEN
        RAISE EXCEPTION 'Access denied: user % is not an active admin or owner in business %',
            v_actor_id, p_business_id
            USING ERRCODE = '42501';
    END IF;

    -- 3. Lock parent business row FIRST (Consistent Lock Ordering across all tenant mutations)
    SELECT id INTO v_biz_id
    FROM public.businesses
    WHERE id = p_business_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Business % does not exist', p_business_id
            USING ERRCODE = 'P0002';
    END IF;

    -- 4. Lock order row and validate status and tenancy
    SELECT * INTO v_order
    FROM public.orders
    WHERE id = p_order_id AND business_id = p_business_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Order % does not exist in business %', p_order_id, p_business_id
            USING ERRCODE = 'P0002';
    END IF;

    IF v_order.status NOT IN ('approved', 'fulfilled') THEN
        RAISE EXCEPTION 'Invoices can only be issued for approved or fulfilled orders (current status: %)',
            v_order.status
            USING ERRCODE = '22023';
    END IF;

    IF v_order.customer_id IS NULL THEN
        RAISE EXCEPTION 'Order % has no associated customer; customer is required for invoice issuance',
            p_order_id
            USING ERRCODE = '22023';
    END IF;

    -- 5. Check for existing invoice for this order (Idempotency)
    SELECT * INTO v_existing_invoice
    FROM public.invoices
    WHERE business_id = p_business_id AND order_id = p_order_id;

    IF FOUND THEN
        SELECT jsonb_build_object(
            'id', v_existing_invoice.id,
            'business_id', v_existing_invoice.business_id,
            'order_id', v_existing_invoice.order_id,
            'customer_id', v_existing_invoice.customer_id,
            'invoice_number', v_existing_invoice.invoice_number,
            'status', v_existing_invoice.status,
            'amount_due', v_existing_invoice.amount_due,
            'due_date', v_existing_invoice.due_date,
            'pdf_storage_path', v_existing_invoice.pdf_storage_path,
            'line_items_snapshot', v_existing_invoice.line_items_snapshot,
            'customer_snapshot', v_existing_invoice.customer_snapshot,
            'created_at', v_existing_invoice.created_at,
            'updated_at', v_existing_invoice.updated_at,
            'is_existing', true
        ) INTO v_result;
        RETURN v_result;
    END IF;

    -- 6. Capture immutable customer details snapshot
    SELECT jsonb_build_object(
        'id', c.id,
        'name', c.name,
        'email', c.email,
        'phone', c.phone,
        'address', c.address
    ) INTO v_customer_snapshot
    FROM public.customers c
    WHERE c.id = v_order.customer_id AND c.business_id = p_business_id;

    v_customer_snapshot := coalesce(
        v_customer_snapshot,
        jsonb_build_object('id', v_order.customer_id, 'name', 'Valued Customer')
    );

    -- 7. Capture immutable line items snapshot
    SELECT coalesce(jsonb_agg(
        jsonb_build_object(
            'product_id', oi.product_id,
            'product_name', coalesce(p.name, 'Item'),
            'product_sku', coalesce(p.sku, ''),
            'quantity', oi.quantity,
            'unit_price', oi.unit_price,
            'line_total', oi.total_price
        ) ORDER BY oi.product_id
    ), '[]'::jsonb) INTO v_items_snapshot
    FROM public.order_items oi
    LEFT JOIN public.products p ON p.id = oi.product_id AND p.business_id = p_business_id
    WHERE oi.order_id = p_order_id AND oi.business_id = p_business_id;

    -- 8. Allocate sequential invoice number: INV-YYYYMM-XXXX
    v_prefix := 'INV-' || to_char(v_now, 'YYYYMM') || '-';
    
    SELECT coalesce(max(
        substring(invoice_number from length(v_prefix) + 1)::INT
    ), 0) + 1 INTO v_seq
    FROM public.invoices
    WHERE business_id = p_business_id
      AND invoice_number LIKE v_prefix || '%';

    v_invoice_number := v_prefix || lpad(v_seq::text, 4, '0');
    v_due_date := coalesce(p_due_date, (v_now::date + interval '30 days')::date);
    v_new_invoice_id := gen_random_uuid();

    -- 9. Persist invoice record with snapshots
    INSERT INTO public.invoices (
        id,
        business_id,
        order_id,
        customer_id,
        invoice_number,
        status,
        amount_due,
        due_date,
        line_items_snapshot,
        customer_snapshot,
        created_at,
        updated_at
    ) VALUES (
        v_new_invoice_id,
        p_business_id,
        p_order_id,
        v_order.customer_id,
        v_invoice_number,
        'issued',
        v_order.total_amount,
        v_due_date,
        v_items_snapshot,
        v_customer_snapshot,
        v_now,
        v_now
    );

    -- 10. Write immutable audit log
    INSERT INTO public.audit_logs (
        id,
        business_id,
        user_id,
        action,
        entity_type,
        entity_id,
        new_values,
        created_at
    ) VALUES (
        gen_random_uuid(),
        p_business_id,
        v_actor_id,
        'invoice.issued',
        'invoice',
        v_new_invoice_id,
        jsonb_build_object(
            'invoice_number', v_invoice_number,
            'order_id', p_order_id,
            'amount_due', v_order.total_amount,
            'due_date', v_due_date
        ),
        v_now
    );

    -- 11. Return structured invoice result with snapshot data
    SELECT jsonb_build_object(
        'id', v_new_invoice_id,
        'business_id', p_business_id,
        'order_id', p_order_id,
        'customer_id', v_order.customer_id,
        'invoice_number', v_invoice_number,
        'status', 'issued',
        'amount_due', v_order.total_amount,
        'due_date', v_due_date,
        'pdf_storage_path', NULL,
        'line_items_snapshot', v_items_snapshot,
        'customer_snapshot', v_customer_snapshot,
        'created_at', v_now,
        'updated_at', v_now,
        'is_existing', false
    ) INTO v_result;

    RETURN v_result;
END;
$$;

-- 4. Restrict execution permissions to authenticated and service_role
REVOKE EXECUTE ON FUNCTION public.allocate_invoice_atomic(UUID, UUID, UUID, DATE) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.allocate_invoice_atomic(UUID, UUID, UUID, DATE) TO authenticated, service_role;

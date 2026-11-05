-- ==============================================================================
-- ORQESTRA DATABASE ARCHITECTURE: MIGRATION 20261023000003
-- Phase 5: Transaction-Safe Invoice Allocation, Numbering, and Realtime Publication
-- ==============================================================================

-- 1. Ensure invoices table has REPLICA IDENTITY FULL for Realtime updates
ALTER TABLE public.invoices REPLICA IDENTITY FULL;

-- 2. Add invoices to supabase_realtime publication idempotently
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables 
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'invoices'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.invoices;
  END IF;
END $$;

-- 3. Composite performance indexes for business-scoped invoice queries
CREATE INDEX IF NOT EXISTS idx_invoices_business_created 
    ON public.invoices(business_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_invoices_business_status 
    ON public.invoices(business_id, status);

-- ------------------------------------------------------------------------------
-- Function: allocate_invoice_atomic
-- Purpose: Atomically allocate, sequence, and persist an invoice for an approved order.
-- Concurrency: Locks business row to serialize invoice numbering per tenant,
--              preventing duplicate invoice numbers under concurrent allocations.
-- Idempotency: Returns existing invoice if one was already issued for the order.
-- Security: SECURITY DEFINER with pinned search_path, independent caller auth,
--           anti-spoofing validation, role checks, and immutable audit logging.
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
    v_order RECORD;
    v_existing_invoice RECORD;
    v_biz_id UUID;
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

    -- 3. Lock order row and validate status and tenancy
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

    -- 4. Check for existing invoice for this order (Idempotency)
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
            'created_at', v_existing_invoice.created_at,
            'updated_at', v_existing_invoice.updated_at,
            'is_existing', true
        ) INTO v_result;
        RETURN v_result;
    END IF;

    -- 5. Lock business row to serialize sequence numbering per business
    SELECT id INTO v_biz_id
    FROM public.businesses
    WHERE id = p_business_id
    FOR UPDATE;

    -- 6. Allocate sequential invoice number: INV-YYYYMM-XXXX
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

    -- 7. Persist invoice record
    INSERT INTO public.invoices (
        id,
        business_id,
        order_id,
        customer_id,
        invoice_number,
        status,
        amount_due,
        due_date,
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
        v_now,
        v_now
    );

    -- 8. Write immutable audit log
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

    -- 9. Return structured invoice result
    SELECT jsonb_build_object(
        'id', v_new_invoice_id,
        'business_id', p_business_id,
        'order_id', p_order_id,
        'customer_id', v_order.customer_id,
        'invoice_number', v_invoice_number,
        'status', 'issued',
        'amount_due', v_order.total_amount,
        'due_date', v_due_date,
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

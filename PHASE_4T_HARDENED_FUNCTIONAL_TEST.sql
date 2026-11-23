-- ==============================================================================
-- ORQESTRA PHASE 4T: HARDENED AUTHENTICATED FUNCTIONAL TEST SUITE
-- File: PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql
-- Execution Environment: Supabase SQL Editor or Direct PostgreSQL Connection
-- Guarantees:
-- 1. Full execution under authentic RLS + SET LOCAL ROLE authenticated.
-- 2. Structured JSON emission of exact generated fixture UUIDs.
-- 3. Complete ROLLBACK (Zero Data Committed).
-- ==============================================================================

BEGIN;

-- Genuine PostgreSQL transaction-scoped role switch
SET LOCAL ROLE authenticated;

DO $$
DECLARE
    -- Ephemeral UUIDs (100% isolated synthetic entities)
    v_biz_a UUID := gen_random_uuid();
    v_biz_b UUID := gen_random_uuid();
    v_admin_a UUID := gen_random_uuid();
    v_staff_a UUID := gen_random_uuid();
    v_admin_b UUID := gen_random_uuid();
    v_prod_a UUID := gen_random_uuid();
    v_prod_b UUID := gen_random_uuid();
    v_inv_a UUID;
    v_inv_b UUID;
    
    -- Returned & Created Entity IDs
    v_res_inv UUID;
    v_res_prod UUID;
    v_res_qty INT;
    v_mvt_1 UUID;
    v_mvt_2 UUID;
    v_audit_1 UUID;
    v_audit_2 UUID;
    v_check_qty INT;
    
    -- Assertion counters
    v_count_mvt_before INT;
    v_count_mvt_after INT;
    v_count_audit_before INT;
    v_count_audit_after INT;
    
    -- Stacked diagnostics variables
    v_sqlstate TEXT;
    v_sqlerrm TEXT;
    v_caught BOOLEAN;
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE ' ORQESTRA PHASE 4T: HARDENED FUNCTIONAL TEST SUITE';
    RAISE NOTICE '=====================================================';

    -- -----------------------------------------------------------------
    -- 0. Environment & Context Pre-flight Checks
    -- -----------------------------------------------------------------
    IF current_user != 'authenticated' THEN
        RAISE EXCEPTION 'SETUP FAILED: current_user is not authenticated (got %)', current_user;
    END IF;

    -- -----------------------------------------------------------------
    -- 1. Setup Ephemeral Business A (Admin A)
    -- -----------------------------------------------------------------
    -- Configure JWT context for Admin A
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::text, true);

    IF public.get_auth_user_id() != v_admin_a THEN
        RAISE EXCEPTION 'SETUP FAILED: get_auth_user_id() does not resolve to v_admin_a';
    END IF;

    -- Inserting into businesses triggers handle_new_business() which
    -- automatically inserts (v_biz_a, v_admin_a, 'owner', true) into business_members
    INSERT INTO public.businesses (id, name, slug)
    VALUES (v_biz_a, 'Ephemeral Test Biz A', 'test-biz-a-' || substr(v_biz_a::text, 1, 8));

    -- Verify handle_new_business() auto-registered v_admin_a as owner
    IF NOT EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_a AND user_id = v_admin_a AND role = 'owner' AND is_active = true
    ) THEN
        RAISE EXCEPTION 'SETUP FAILED: handle_new_business() did not auto-enroll Admin A as owner in Business A';
    END IF;

    -- Admin A invites staff member v_staff_a
    INSERT INTO public.business_members (business_id, user_id, role, is_active)
    VALUES (v_biz_a, v_staff_a, 'staff', true);

    -- Setup Product and Inventory for Business A (baseline = 20)
    INSERT INTO public.products (id, business_id, sku, name, unit_price)
    VALUES (v_prod_a, v_biz_a, 'SKU-A-001', 'Widget A', 25.00);

    INSERT INTO public.inventory (business_id, product_id, quantity_on_hand)
    VALUES (v_biz_a, v_prod_a, 20)
    RETURNING id INTO v_inv_a;

    -- -----------------------------------------------------------------
    -- 2. Setup Ephemeral Business B (Admin B)
    -- -----------------------------------------------------------------
    -- Switch JWT context to Admin B
    PERFORM set_config('request.jwt.claim.sub', v_admin_b::text, true);

    IF public.get_auth_user_id() != v_admin_b THEN
        RAISE EXCEPTION 'SETUP FAILED: get_auth_user_id() does not resolve to v_admin_b';
    END IF;

    -- Inserting into businesses triggers handle_new_business() which
    -- automatically inserts (v_biz_b, v_admin_b, 'owner', true) into business_members
    INSERT INTO public.businesses (id, name, slug)
    VALUES (v_biz_b, 'Ephemeral Test Biz B', 'test-biz-b-' || substr(v_biz_b::text, 1, 8));

    -- Verify handle_new_business() auto-registered v_admin_b as owner
    IF NOT EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_b AND user_id = v_admin_b AND role = 'owner' AND is_active = true
    ) THEN
        RAISE EXCEPTION 'SETUP FAILED: handle_new_business() did not auto-enroll Admin B as owner in Business B';
    END IF;

    -- Setup Product and Inventory for Business B (baseline = 10)
    INSERT INTO public.products (id, business_id, sku, name, unit_price)
    VALUES (v_prod_b, v_biz_b, 'SKU-B-001', 'Widget B', 50.00);

    INSERT INTO public.inventory (business_id, product_id, quantity_on_hand)
    VALUES (v_biz_b, v_prod_b, 10)
    RETURNING id INTO v_inv_b;

    -- -----------------------------------------------------------------
    -- 3. Verify Business B Identity Isolation Assertions
    -- -----------------------------------------------------------------
    -- RLS Visibility Architecture Note:
    -- Under the 'business_members_select_colleagues' policy:
    --   USING (user_id = auth.uid() OR has_business_role(business_id, auth.uid(), 'staff'))
    -- A user can see:
    -- 1. Any record where user_id = auth.uid() (their own memberships across all businesses).
    -- 2. ALL members of a business in which the user has an active role of 'staff' or higher.
    -- Therefore, when executing under Admin B context (owner of Business B), Admin B has full
    -- visibility into all Business B members. Asserting absence of Admin A and Staff A here is
    -- authoritative for Business B. Conversely, under Admin A context, Admin A can only see
    -- Business A members and their own records. Global absence across all tenants is independently
    -- verified post-rollback by the administrative test runner.
    -- Under Admin B context:
    IF NOT EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_b AND user_id = v_admin_b AND role = 'owner' AND is_active = true
    ) THEN
        RAISE EXCEPTION 'ISOLATION ASSERTION FAILED: Admin B is not active owner of Business B';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_b AND user_id = v_admin_a
    ) THEN
        RAISE EXCEPTION 'ISOLATION ASSERTION FAILED: Admin A unexpectedly has membership in Business B';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_b AND user_id = v_staff_a
    ) THEN
        RAISE EXCEPTION 'ISOLATION ASSERTION FAILED: Staff A unexpectedly has membership in Business B';
    END IF;

    -- Restore JWT context to Admin A
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::text, true);

    -- Under Admin A context:
    IF NOT EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_a AND user_id = v_admin_a AND role = 'owner' AND is_active = true
    ) THEN
        RAISE EXCEPTION 'ISOLATION ASSERTION FAILED: Admin A is not active owner of Business A';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_a AND user_id = v_staff_a AND role = 'staff' AND is_active = true
    ) THEN
        RAISE EXCEPTION 'ISOLATION ASSERTION FAILED: Staff A is not active staff member of Business A';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_a AND user_id = v_admin_b
    ) THEN
        RAISE EXCEPTION 'ISOLATION ASSERTION FAILED: Admin B unexpectedly has membership in Business A';
    END IF;

    RAISE NOTICE 'Setup complete: Full tenancy isolation verified across Business A and Business B.';

    -- =================================================================
    -- TEST 1: Authorized Stock Increase (+10 -> 30)
    -- =================================================================
    SELECT inventory_id, product_id, new_quantity, movement_id
    INTO v_res_inv, v_res_prod, v_res_qty, v_mvt_1
    FROM public.adjust_stock_atomic(
        v_biz_a,
        v_prod_a,
        10,
        'restock'::stock_movement_type,
        'Valid restock shipment',
        v_admin_a
    );

    IF v_res_qty != 30 OR v_res_inv != v_inv_a OR v_res_prod != v_prod_a OR v_mvt_1 IS NULL THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Invalid return values from adjust_stock_atomic';
    END IF;

    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 30 THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Inventory quantity_on_hand is not 30 (got %)', v_check_qty;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.stock_movements
        WHERE id = v_mvt_1
          AND business_id = v_biz_a
          AND product_id = v_prod_a
          AND quantity_change = 10
          AND movement_type = 'restock'
          AND created_by = v_admin_a
    ) THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Expected stock_movement record missing or invalid';
    END IF;

    SELECT id INTO v_audit_1
    FROM public.audit_logs
    WHERE business_id = v_biz_a
      AND user_id = v_admin_a
      AND action = 'stock.adjusted'
      AND entity_type = 'inventory'
      AND entity_id = v_inv_a
      AND (new_values ->> 'movement_id')::UUID = v_mvt_1
      AND (new_values ->> 'quantity_on_hand')::INT = 30
      AND (new_values ->> 'quantity_change')::INT = 10
      AND (old_values ->> 'quantity_on_hand')::INT = 20
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_audit_1 IS NULL THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Expected audit_log record missing or invalid';
    END IF;

    RAISE NOTICE 'TEST 1 PASSED: Authorized restock (+10 -> 30) verified across inventory, movements, and audit_logs';

    -- =================================================================
    -- TEST 2: Authorized Stock Deduction (-5 -> 25)
    -- =================================================================
    SELECT inventory_id, product_id, new_quantity, movement_id
    INTO v_res_inv, v_res_prod, v_res_qty, v_mvt_2
    FROM public.adjust_stock_atomic(
        v_biz_a,
        v_prod_a,
        -5,
        'adjustment'::stock_movement_type,
        'Damaged stock write-off',
        v_admin_a
    );

    IF v_res_qty != 25 OR v_res_inv != v_inv_a OR v_res_prod != v_prod_a OR v_mvt_2 IS NULL THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Invalid return values from deduction';
    END IF;

    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 25 THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Inventory quantity_on_hand is not 25 (got %)', v_check_qty;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.stock_movements
        WHERE id = v_mvt_2
          AND business_id = v_biz_a
          AND product_id = v_prod_a
          AND quantity_change = -5
          AND movement_type = 'adjustment'
          AND created_by = v_admin_a
    ) THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Expected deduction stock_movement record missing';
    END IF;

    SELECT id INTO v_audit_2
    FROM public.audit_logs
    WHERE business_id = v_biz_a
      AND user_id = v_admin_a
      AND action = 'stock.adjusted'
      AND entity_type = 'inventory'
      AND entity_id = v_inv_a
      AND (new_values ->> 'movement_id')::UUID = v_mvt_2
      AND (new_values ->> 'quantity_on_hand')::INT = 25
      AND (new_values ->> 'quantity_change')::INT = -5
      AND (old_values ->> 'quantity_on_hand')::INT = 30
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_audit_2 IS NULL THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Expected deduction audit_log record missing or invalid';
    END IF;

    RAISE NOTICE 'TEST 2 PASSED: Authorized deduction (-5 -> 25) verified across inventory, movements, and audit_logs';

    -- =================================================================
    -- TEST 3: Zero Quantity Rejection & State Invariance
    -- =================================================================
    SELECT count(*) INTO v_count_mvt_before FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_before FROM public.audit_logs WHERE business_id = v_biz_a;
    v_caught := false;

    BEGIN
        PERFORM public.adjust_stock_atomic(
            v_biz_a,
            v_prod_a,
            0,
            'adjustment'::stock_movement_type,
            'Zero qty test',
            v_admin_a
        );
        RAISE EXCEPTION 'TEST 3 FAILED: Zero quantity was not rejected';
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS
            v_sqlstate = RETURNED_SQLSTATE,
            v_sqlerrm = MESSAGE_TEXT;

        IF v_sqlstate = 'P0001' AND v_sqlerrm LIKE '%Quantity change must be non-zero%' THEN
            v_caught := true;
        ELSE
            RAISE EXCEPTION 'TEST 3 FAILED with unexpected error: SQLSTATE=%, MSG=%', v_sqlstate, v_sqlerrm;
        END IF;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION 'TEST 3 FAILED: Exception block not reached';
    END IF;

    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 25 THEN
        RAISE EXCEPTION 'TEST 3 FAILED: Inventory mutated despite failure (expected 25, got %)', v_check_qty;
    END IF;

    SELECT count(*) INTO v_count_mvt_after FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_after FROM public.audit_logs WHERE business_id = v_biz_a;
    IF v_count_mvt_after != v_count_mvt_before OR v_count_audit_after != v_count_audit_before THEN
        RAISE EXCEPTION 'TEST 3 FAILED: Phantom ledger entries created during failed zero-quantity call';
    END IF;

    RAISE NOTICE 'TEST 3 PASSED: Zero quantity rejected with SQLSTATE P0001; zero state mutation';

    -- =================================================================
    -- TEST 4: Insufficient Stock Overdraft Rejection (25 - 30 = -5)
    -- =================================================================
    SELECT count(*) INTO v_count_mvt_before FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_before FROM public.audit_logs WHERE business_id = v_biz_a;
    v_caught := false;

    BEGIN
        PERFORM public.adjust_stock_atomic(
            v_biz_a,
            v_prod_a,
            -30,
            'adjustment'::stock_movement_type,
            'Overdraft test',
            v_admin_a
        );
        RAISE EXCEPTION 'TEST 4 FAILED: Overdraft was not rejected';
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS
            v_sqlstate = RETURNED_SQLSTATE,
            v_sqlerrm = MESSAGE_TEXT;

        IF v_sqlstate = 'P0001' AND v_sqlerrm LIKE '%would result in negative quantity (-5) from current (25)%' THEN
            v_caught := true;
        ELSE
            RAISE EXCEPTION 'TEST 4 FAILED with unexpected error: SQLSTATE=%, MSG=%', v_sqlstate, v_sqlerrm;
        END IF;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Exception block not reached';
    END IF;

    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 25 THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Inventory mutated despite failure (expected 25, got %)', v_check_qty;
    END IF;

    SELECT count(*) INTO v_count_mvt_after FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_after FROM public.audit_logs WHERE business_id = v_biz_a;
    IF v_count_mvt_after != v_count_mvt_before OR v_count_audit_after != v_count_audit_before THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Phantom ledger entries created during failed overdraft call';
    END IF;

    RAISE NOTICE 'TEST 4 PASSED: Overdraft rejected with SQLSTATE P0001; inventory unchanged at 25';

    -- =================================================================
    -- TEST 5: Actor Identity Spoofing Rejection
    -- (Caller v_admin_a passes p_user_id = v_staff_a)
    -- =================================================================
    SELECT count(*) INTO v_count_mvt_before FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_before FROM public.audit_logs WHERE business_id = v_biz_a;
    v_caught := false;

    BEGIN
        PERFORM public.adjust_stock_atomic(
            v_biz_a,
            v_prod_a,
            5,
            'restock'::stock_movement_type,
            'Spoof attempt',
            v_staff_a -- Attempting to act as staff_a while JWT claim sub is admin_a
        );
        RAISE EXCEPTION 'TEST 5 FAILED: Identity spoofing was not rejected';
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS
            v_sqlstate = RETURNED_SQLSTATE,
            v_sqlerrm = MESSAGE_TEXT;

        IF v_sqlstate = 'P0001' AND v_sqlerrm LIKE '%Actor identity mismatch%' THEN
            v_caught := true;
        ELSE
            RAISE EXCEPTION 'TEST 5 FAILED with unexpected error: SQLSTATE=%, MSG=%', v_sqlstate, v_sqlerrm;
        END IF;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION 'TEST 5 FAILED: Exception block not reached';
    END IF;

    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 25 THEN
        RAISE EXCEPTION 'TEST 5 FAILED: Inventory mutated on spoofing attempt';
    END IF;

    SELECT count(*) INTO v_count_mvt_after FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_after FROM public.audit_logs WHERE business_id = v_biz_a;
    IF v_count_mvt_after != v_count_mvt_before OR v_count_audit_after != v_count_audit_before THEN
        RAISE EXCEPTION 'TEST 5 FAILED: Phantom ledger entries created on spoofing attempt';
    END IF;

    RAISE NOTICE 'TEST 5 PASSED: Actor identity mismatch caught with SQLSTATE P0001';

    -- =================================================================
    -- TEST 6: RBAC Privilege Enforcement (Staff Role Rejected)
    -- =================================================================
    -- Switch JWT context to v_staff_a
    PERFORM set_config('request.jwt.claim.sub', v_staff_a::text, true);

    SELECT count(*) INTO v_count_mvt_before FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_before FROM public.audit_logs WHERE business_id = v_biz_a;
    v_caught := false;

    BEGIN
        PERFORM public.adjust_stock_atomic(
            v_biz_a,
            v_prod_a,
            5,
            'restock'::stock_movement_type,
            'Staff adjustment attempt',
            v_staff_a
        );
        RAISE EXCEPTION 'TEST 6 FAILED: Staff role adjustment was not rejected';
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS
            v_sqlstate = RETURNED_SQLSTATE,
            v_sqlerrm = MESSAGE_TEXT;

        IF v_sqlstate = 'P0001' AND v_sqlerrm LIKE '%does not have active admin or owner role%' THEN
            v_caught := true;
        ELSE
            RAISE EXCEPTION 'TEST 6 FAILED with unexpected error: SQLSTATE=%, MSG=%', v_sqlstate, v_sqlerrm;
        END IF;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION 'TEST 6 FAILED: Exception block not reached';
    END IF;

    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 25 THEN
        RAISE EXCEPTION 'TEST 6 FAILED: Inventory mutated on staff attempt';
    END IF;

    SELECT count(*) INTO v_count_mvt_after FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_after FROM public.audit_logs WHERE business_id = v_biz_a;
    IF v_count_mvt_after != v_count_mvt_before OR v_count_audit_after != v_count_audit_before THEN
        RAISE EXCEPTION 'TEST 6 FAILED: Phantom ledger entries created on staff attempt';
    END IF;

    RAISE NOTICE 'TEST 6 PASSED: Staff role unauthorized execution rejected with SQLSTATE P0001';

    -- Switch JWT context back to v_admin_a
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::text, true);

    -- =================================================================
    -- TEST 7: Cross-Tenant Product Access Rejection
    -- (v_admin_a targets Biz A, but passes Prod B which belongs to Biz B)
    -- =================================================================
    SELECT count(*) INTO v_count_mvt_before FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_before FROM public.audit_logs WHERE business_id = v_biz_a;
    v_caught := false;

    BEGIN
        PERFORM public.adjust_stock_atomic(
            v_biz_a,
            v_prod_b, -- Belongs to Biz B
            5,
            'restock'::stock_movement_type,
            'Cross product attack',
            v_admin_a
        );
        RAISE EXCEPTION 'TEST 7 FAILED: Cross-tenant product was not rejected';
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS
            v_sqlstate = RETURNED_SQLSTATE,
            v_sqlerrm = MESSAGE_TEXT;

        IF v_sqlstate = 'P0001' AND v_sqlerrm LIKE '%does not belong to business%' THEN
            v_caught := true;
        ELSE
            RAISE EXCEPTION 'TEST 7 FAILED with unexpected error: SQLSTATE=%, MSG=%', v_sqlstate, v_sqlerrm;
        END IF;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION 'TEST 7 FAILED: Exception block not reached';
    END IF;

    -- Verify Biz A inventory remains 25
    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 25 THEN
        RAISE EXCEPTION 'TEST 7 FAILED: Biz A inventory mutated';
    END IF;

    -- Verify Biz B inventory remains 10 (switch context to Admin B)
    PERFORM set_config('request.jwt.claim.sub', v_admin_b::text, true);
    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_b;
    IF v_check_qty != 10 THEN
        RAISE EXCEPTION 'TEST 7 FAILED: Biz B inventory mutated';
    END IF;

    -- Verify Biz B received zero phantom stock movements or audit logs
    IF (SELECT count(*) FROM public.stock_movements WHERE business_id = v_biz_b) != 0 THEN
        RAISE EXCEPTION 'TEST 7 FAILED: Phantom stock movement created for Biz B on cross-tenant product call';
    END IF;

    IF (SELECT count(*) FROM public.audit_logs WHERE business_id = v_biz_b) != 0 THEN
        RAISE EXCEPTION 'TEST 7 FAILED: Phantom audit log created for Biz B on cross-tenant product call';
    END IF;

    -- Restore JWT context to Admin A
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::text, true);

    SELECT count(*) INTO v_count_mvt_after FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_after FROM public.audit_logs WHERE business_id = v_biz_a;
    IF v_count_mvt_after != v_count_mvt_before OR v_count_audit_after != v_count_audit_before THEN
        RAISE EXCEPTION 'TEST 7 FAILED: Phantom ledger entries created for Biz A on cross-tenant product call';
    END IF;

    RAISE NOTICE 'TEST 7 PASSED: Cross-tenant product mismatch caught with SQLSTATE P0001';

    -- =================================================================
    -- TEST 8: Cross-Tenant Unauthorized Business Access Rejection
    -- (v_admin_a targets Biz B where they have zero membership)
    -- =================================================================
    -- Under Admin A context:
    -- Note on RLS visibility: Under business_members_select_colleagues policy:
    --   USING (user_id = auth.uid() OR has_business_role(business_id, auth.uid(), 'staff'))
    -- A user can see any row where user_id = auth.uid(). Therefore, if Admin A
    -- held any membership in Business B, that row would be visible to Admin A here.
    -- Admin A cannot see Admin B's membership in Business B due to RLS filtering.
    -- True global absence of uncommitted test entities across all tenants is independently audited
    -- post-rollback by the administrative test runner.
    IF EXISTS (
        SELECT 1 FROM public.business_members
        WHERE business_id = v_biz_b AND user_id = v_admin_a
    ) THEN
        RAISE EXCEPTION 'TEST 8 SETUP ERROR: Admin A has membership in Business B';
    END IF;

    SELECT count(*) INTO v_count_mvt_before FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_before FROM public.audit_logs WHERE business_id = v_biz_a;

    v_caught := false;

    BEGIN
        PERFORM public.adjust_stock_atomic(
            v_biz_b, -- Biz B (Admin A has zero membership)
            v_prod_b,
            5,
            'restock'::stock_movement_type,
            'Cross biz attack',
            v_admin_a
        );
        RAISE EXCEPTION 'TEST 8 FAILED: Unauthorized business access was not rejected';
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS
            v_sqlstate = RETURNED_SQLSTATE,
            v_sqlerrm = MESSAGE_TEXT;

        IF v_sqlstate = 'P0001' AND v_sqlerrm LIKE '%Access denied: user ' || v_admin_a::text || ' does not have active admin or owner role in business ' || v_biz_b::text || '%' THEN
            v_caught := true;
        ELSE
            RAISE EXCEPTION 'TEST 8 FAILED with unexpected error: SQLSTATE=%, MSG=%', v_sqlstate, v_sqlerrm;
        END IF;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION 'TEST 8 FAILED: Exception block not reached';
    END IF;

    -- Assert Business A state remains unchanged
    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_a;
    IF v_check_qty != 25 THEN
        RAISE EXCEPTION 'TEST 8 FAILED: Biz A inventory mutated';
    END IF;

    SELECT count(*) INTO v_count_mvt_after FROM public.stock_movements WHERE business_id = v_biz_a;
    SELECT count(*) INTO v_count_audit_after FROM public.audit_logs WHERE business_id = v_biz_a;
    IF v_count_mvt_after != v_count_mvt_before OR v_count_audit_after != v_count_audit_before THEN
        RAISE EXCEPTION 'TEST 8 FAILED: Phantom ledger entries created for Biz A';
    END IF;

    -- Assert Business B state remains unchanged (under Admin B context)
    PERFORM set_config('request.jwt.claim.sub', v_admin_b::text, true);

    SELECT quantity_on_hand INTO v_check_qty FROM public.inventory WHERE id = v_inv_b;
    IF v_check_qty != 10 THEN
        RAISE EXCEPTION 'TEST 8 FAILED: Biz B inventory mutated';
    END IF;

    IF (SELECT count(*) FROM public.stock_movements WHERE business_id = v_biz_b) != 0 THEN
        RAISE EXCEPTION 'TEST 8 FAILED: Stock movement created for Biz B';
    END IF;

    IF (SELECT count(*) FROM public.audit_logs WHERE business_id = v_biz_b) != 0 THEN
        RAISE EXCEPTION 'TEST 8 FAILED: Audit log created for Biz B';
    END IF;

    -- Restore to Admin A
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::text, true);

    RAISE NOTICE 'TEST 8 PASSED: Unauthorized business access caught with SQLSTATE P0001; zero state mutation';

    -- -----------------------------------------------------------------
    -- 4. Emit Fixture Manifest for Exact-ID Verification
    -- -----------------------------------------------------------------
    RAISE NOTICE 'MANIFEST_JSON:%', json_build_object(
        'biz_a', v_biz_a,
        'biz_b', v_biz_b,
        'admin_a', v_admin_a,
        'admin_b', v_admin_b,
        'staff_a', v_staff_a,
        'prod_a', v_prod_a,
        'prod_b', v_prod_b,
        'inv_a', v_inv_a,
        'inv_b', v_inv_b,
        'mvt_1', v_mvt_1,
        'mvt_2', v_mvt_2,
        'audit_1', v_audit_1,
        'audit_2', v_audit_2
    )::text;

    RAISE NOTICE '=====================================================';
    RAISE NOTICE ' ALL 8 FUNCTIONAL & SECURITY TESTS PASSED WITH 100%% COMPLIANCE';
    RAISE NOTICE '=====================================================';
END $$;

-- Unconditional transaction abort: completely purges all ephemeral entities
ROLLBACK;

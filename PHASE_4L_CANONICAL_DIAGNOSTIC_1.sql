-- ==============================================================================
-- ORQESTRA STAGING DEPLOYMENT PRE-FLIGHT
-- CANONICAL DIAGNOSTIC 1: Comprehensive Remote Schema & Security Audit
-- File: PHASE_4L_CANONICAL_DIAGNOSTIC_1.sql
-- 
-- PURPOSE:
-- Executes a non-mutating, read-only diagnostic across all catalog objects
-- required for the remediation of adjust_stock_atomic (Migration 20261115000001).
--
-- EXECUTION ENVIRONMENT:
-- Supabase SQL Editor (linked project vwlwbwwrumsmjqeavvxk) or psql.
--
-- SAFETY ASSURANCES:
-- 1. Strictly read-only (SELECT queries only). No DDL or DML modifications.
-- 2. Safe to execute inside an explicit READ ONLY transaction.
-- 3. Employs defensive CTE-based existence checks so missing objects, missing
--    tables, and unexpected overloads produce explicit status rows rather than
--    silent row omissions or runtime crashes.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- SECTION 0: Visibility & Diagnostic Execution Guard
-- Verifies connected role, session user, search path, and basic catalog read access.
-- NOTE: has_table_privilege() confirms basic SELECT permission on system catalogs,
-- serving as an essential sanity check prior to executing subsequent queries. It
-- does not prove absence of catalog filtering, object masking, or row security.
-- ------------------------------------------------------------------------------
SELECT 
    current_database() AS database_name,
    current_user AS connected_user,
    session_user AS current_session_user,
    has_schema_privilege('public', 'USAGE') AS has_public_schema_usage,
    has_table_privilege('pg_proc', 'SELECT') AS can_read_pg_proc,
    has_table_privilege('pg_trigger', 'SELECT') AS can_read_pg_trigger,
    has_table_privilege('pg_constraint', 'SELECT') AS can_read_pg_constraint,
    has_table_privilege('pg_policy', 'SELECT') AS can_read_pg_policy,
    has_table_privilege('pg_class', 'SELECT') AS can_read_pg_class,
    current_setting('search_path') AS active_search_path,
    'CATALOG_READ_SANITY_CHECK_ONLY' AS check_scope_note;

-- ------------------------------------------------------------------------------
-- SECTION 1: Immutable and Lifecycle Triggers
-- Verifies all 10 expected triggers, their attachment tables, attachment schemas,
-- attached functions, function schemas, timing (BEFORE/AFTER), events set,
-- and enabled state. Disabled triggers do NOT receive a successful status.
-- ------------------------------------------------------------------------------
WITH expected_triggers(target_table, target_schema, expected_trigger_name, expected_function, expected_fn_schema, expected_timing, expected_events) AS (
    VALUES 
        ('businesses', 'public', 'trg_businesses_updated_at', 'set_updated_at_timestamp', 'public', 'BEFORE', ARRAY['UPDATE']::text[]),
        ('businesses', 'public', 'trg_on_business_created', 'handle_new_business', 'public', 'AFTER', ARRAY['INSERT']::text[]),
        ('business_members', 'public', 'trg_business_members_updated_at', 'set_updated_at_timestamp', 'public', 'BEFORE', ARRAY['UPDATE']::text[]),
        ('products', 'public', 'trg_products_updated_at', 'set_updated_at_timestamp', 'public', 'BEFORE', ARRAY['UPDATE']::text[]),
        ('inventory', 'public', 'trg_inventory_updated_at', 'set_updated_at_timestamp', 'public', 'BEFORE', ARRAY['UPDATE']::text[]),
        ('customers', 'public', 'trg_customers_updated_at', 'set_updated_at_timestamp', 'public', 'BEFORE', ARRAY['UPDATE']::text[]),
        ('orders', 'public', 'trg_orders_updated_at', 'set_updated_at_timestamp', 'public', 'BEFORE', ARRAY['UPDATE']::text[]),
        ('invoices', 'public', 'trg_invoices_updated_at', 'set_updated_at_timestamp', 'public', 'BEFORE', ARRAY['UPDATE']::text[]),
        ('stock_movements', 'public', 'trg_stock_movements_immutable', 'prevent_immutable_modification', 'public', 'BEFORE', ARRAY['DELETE', 'UPDATE']::text[]),
        ('audit_logs', 'public', 'trg_audit_logs_immutable', 'prevent_immutable_modification', 'public', 'BEFORE', ARRAY['DELETE', 'UPDATE']::text[])
)
SELECT 
    et.target_schema,
    et.target_table,
    et.expected_trigger_name,
    et.expected_fn_schema,
    et.expected_function,
    et.expected_timing,
    et.expected_events,
    CASE 
        WHEN c.relname IS NULL THEN 'MISSING TABLE'
        WHEN t.tgname IS NULL THEN 'MISSING TRIGGER'
        WHEN p.proname IS NULL THEN 'TRIGGER ATTACHED TO UNRESOLVED FUNCTION'
        WHEN p_ns.nspname != et.expected_fn_schema THEN 'WRONG FUNCTION SCHEMA: ' || p_ns.nspname
        WHEN p.proname != et.expected_function THEN 'WRONG FUNCTION: ' || p.proname
        WHEN (CASE WHEN (t.tgtype & 2) != 0 THEN 'BEFORE' WHEN (t.tgtype & 64) != 0 THEN 'INSTEAD OF' ELSE 'AFTER' END) != et.expected_timing THEN 'WRONG TIMING: ' || (CASE WHEN (t.tgtype & 2) != 0 THEN 'BEFORE' WHEN (t.tgtype & 64) != 0 THEN 'INSTEAD OF' ELSE 'AFTER' END)
        WHEN ARRAY(
            SELECT e.evt FROM (
                SELECT 'INSERT' AS evt, 4 AS mask
                UNION ALL SELECT 'DELETE', 8
                UNION ALL SELECT 'UPDATE', 16
                UNION ALL SELECT 'TRUNCATE', 32
            ) e WHERE (t.tgtype & e.mask) != 0
            ORDER BY e.evt
        ) != et.expected_events THEN 'WRONG EVENTS'
        WHEN t.tgenabled = 'D' THEN 'TRIGGER DISABLED (INOPERATIVE)'
        WHEN t.tgenabled = 'R' THEN 'TRIGGER REPLICA-ONLY (INOPERATIVE LOCALLY)'
        WHEN t.tgenabled = 'A' THEN 'PRESENT (CORRECT: ALWAYS ENABLED)'
        WHEN t.tgenabled = 'O' THEN 'PRESENT (CORRECT: ENABLED)'
        ELSE 'UNKNOWN STATUS'
    END AS verification_status,
    CASE t.tgenabled 
        WHEN 'O' THEN 'enabled (origin/local)'
        WHEN 'D' THEN 'DISABLED'
        WHEN 'A' THEN 'always enabled'
        WHEN 'R' THEN 'replica only'
        ELSE COALESCE(t.tgenabled::text, 'N/A (MISSING)')
    END AS trigger_enabled_status,
    CASE WHEN (t.tgtype & 2) != 0 THEN 'BEFORE' WHEN (t.tgtype & 64) != 0 THEN 'INSTEAD OF' ELSE 'AFTER' END AS actual_timing,
    ARRAY(
        SELECT e.evt FROM (
            SELECT 'INSERT' AS evt, 4 AS mask
            UNION ALL SELECT 'DELETE', 8
            UNION ALL SELECT 'UPDATE', 16
            UNION ALL SELECT 'TRUNCATE', 32
        ) e WHERE (t.tgtype & e.mask) != 0
        ORDER BY e.evt
    ) AS actual_events,
    COALESCE(p_ns.nspname, 'N/A') AS actual_function_schema,
    COALESCE(p.proname, 'N/A') AS actual_function_name,
    COALESCE(pg_get_triggerdef(t.oid), 'N/A') AS full_trigger_definition
FROM expected_triggers et
LEFT JOIN pg_class c ON c.relname = et.target_table 
    AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = et.target_schema)
LEFT JOIN pg_trigger t ON t.tgrelid = c.oid 
    AND t.tgname = et.expected_trigger_name 
    AND NOT t.tgisinternal
LEFT JOIN pg_proc p ON t.tgfoid = p.oid
LEFT JOIN pg_namespace p_ns ON p.pronamespace = p_ns.oid
ORDER BY et.target_table, et.expected_trigger_name;

-- ------------------------------------------------------------------------------
-- SECTION 2: Partial Unique Index on Invoices
-- Verifies uq_invoices_business_order_unique existence, schema, table, uniqueness,
-- validity, readiness, access method (btree), exact key column order, absence of
-- unexpected INCLUDE columns, and exact partial predicate expression.
-- ------------------------------------------------------------------------------
WITH expected_index AS (
    SELECT 
        'invoices'::text AS table_name,
        'public'::text AS table_schema,
        'uq_invoices_business_order_unique'::text AS index_name,
        'public'::text AS index_schema,
        'btree'::text AS expected_access_method,
        ARRAY['business_id', 'order_id']::text[] AS expected_key_cols,
        '(order_id IS NOT NULL)'::text AS expected_predicate
)
SELECT 
    ei.table_schema,
    ei.table_name,
    ei.index_schema,
    ei.index_name,
    COALESCE(am.amname, 'N/A') AS access_method,
    CASE 
        WHEN c.relname IS NULL THEN 'MISSING TABLE'
        WHEN i.relname IS NULL THEN 'MISSING INDEX'
        WHEN am.amname != ei.expected_access_method THEN 'WRONG ACCESS METHOD: ' || COALESCE(am.amname, 'UNKNOWN')
        WHEN NOT ix.indisunique THEN 'NON-UNIQUE INDEX'
        WHEN NOT ix.indisvalid THEN 'INVALID INDEX'
        WHEN NOT ix.indisready THEN 'NOT READY'
        WHEN ARRAY(
            SELECT a.attname::text 
            FROM unnest(ix.indkey[0:ix.indnkeyatts-1]) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
            ORDER BY k.ord
        ) != ei.expected_key_cols THEN 'WRONG KEY COLUMNS'
        WHEN ix.indnatts != ix.indnkeyatts THEN 'UNEXPECTED INCLUDE COLUMNS'
        WHEN COALESCE(pg_get_expr(ix.indpred, ix.indrelid), '') != ei.expected_predicate THEN 'WRONG PREDICATE'
        ELSE 'PRESENT (VALID UNIQUE PARTIAL INDEX)'
    END AS verification_status,
    COALESCE(ix.indisunique, false) AS is_unique,
    COALESCE(ix.indisvalid, false) AS is_valid,
    COALESCE(ix.indisready, false) AS is_ready,
    COALESCE(ix.indnkeyatts, 0) AS key_column_count,
    COALESCE(ix.indnatts - ix.indnkeyatts, 0) AS include_column_count,
    ARRAY(
        SELECT a.attname::text 
        FROM unnest(ix.indkey[0:ix.indnkeyatts-1]) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
        ORDER BY k.ord
    ) AS key_columns,
    COALESCE(pg_get_expr(ix.indpred, ix.indrelid), 'N/A (NO PREDICATE)') AS partial_predicate,
    COALESCE(pg_get_indexdef(ix.indexrelid), 'N/A') AS full_index_definition
FROM expected_index ei
LEFT JOIN pg_class c ON c.relname = ei.table_name 
    AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = ei.table_schema)
LEFT JOIN pg_class i ON i.relname = ei.index_name 
    AND i.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = ei.index_schema)
LEFT JOIN pg_am am ON i.relam = am.oid
LEFT JOIN pg_index ix ON ix.indrelid = c.oid AND ix.indexrelid = i.oid;

-- ------------------------------------------------------------------------------
-- SECTION 3: Operational Replica Identity Full Settings
-- Verifies REPLICA IDENTITY FULL on all 5 operational tables required for Realtime.
-- Reports missing tables explicitly via CTE.
-- ------------------------------------------------------------------------------
WITH expected_tables(table_name) AS (
    VALUES ('products'), ('inventory'), ('orders'), ('stock_movements'), ('invoices')
)
SELECT 
    et.table_name,
    CASE 
        WHEN c.relname IS NULL THEN 'MISSING TABLE'
        WHEN c.relreplident = 'f' THEN 'COMPLIANT (FULL)'
        ELSE 'NON-COMPLIANT'
    END AS compliance_status,
    CASE c.relreplident
        WHEN 'd' THEN 'default (primary key only - NON-COMPLIANT)'
        WHEN 'n' THEN 'nothing (NON-COMPLIANT)'
        WHEN 'f' THEN 'FULL (REPLICA IDENTITY FULL - Compliant)'
        WHEN 'i' THEN 'custom index (NON-COMPLIANT)'
        ELSE COALESCE(c.relreplident::text, 'N/A (MISSING TABLE)')
    END AS replica_identity_status,
    COALESCE(c.relreplident = 'f', false) AS is_realtime_compliant
FROM expected_tables et
LEFT JOIN pg_class c ON c.relname = et.table_name 
    AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
ORDER BY et.table_name;

-- ------------------------------------------------------------------------------
-- SECTION 4: Exact Deployed adjust_stock_atomic Function Definition & Signature
-- Matches function by strict positional OID/schema-qualified argument types.
-- NEVER uses string-based LIKE filters.
-- Guarantees a returned status row even if 0 matches or >1 overloads exist.
-- Validates both the input argument signature AND the expected return signature.
-- Captures function source, owner, SECURITY DEFINER status, and search_path.
-- ------------------------------------------------------------------------------
WITH matched_funcs AS (
    SELECT 
        p.oid AS func_oid,
        p.proname AS function_name,
        n.nspname AS schema_name,
        pg_get_function_identity_arguments(p.oid) AS argument_signature,
        pg_get_function_result(p.oid) AS return_signature,
        r.rolname AS owner_role,
        p.prosecdef AS is_security_definer,
        p.proconfig AS search_path_configuration,
        p.proacl::text AS raw_access_control_list,
        has_function_privilege('anon', p.oid, 'EXECUTE') AS anon_can_execute,
        has_function_privilege('authenticated', p.oid, 'EXECUTE') AS authenticated_can_execute,
        has_function_privilege('service_role', p.oid, 'EXECUTE') AS service_role_can_execute,
        pg_get_functiondef(p.oid) AS complete_function_source
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    JOIN pg_roles r ON p.proowner = r.oid
    WHERE n.nspname = 'public' 
      AND p.proname = 'adjust_stock_atomic'
      AND ARRAY(
          SELECT arg_ns.nspname || '.' || arg_typ.typname 
          FROM unnest(p.proargtypes::oid[]) WITH ORDINALITY AS u(arg_oid, ord)
          JOIN pg_type arg_typ ON u.arg_oid = arg_typ.oid
          JOIN pg_namespace arg_ns ON arg_typ.typnamespace = arg_ns.oid
          ORDER BY u.ord
      ) = ARRAY['pg_catalog.uuid', 'pg_catalog.uuid', 'pg_catalog.int4', 'public.stock_movement_type', 'pg_catalog.text', 'pg_catalog.uuid']
),
match_summary AS (
    SELECT count(*) AS match_count FROM matched_funcs
)
SELECT 
    'adjust_stock_atomic' AS expected_function,
    'public' AS expected_schema,
    'uuid, uuid, integer, stock_movement_type, text, uuid' AS expected_signature,
    'TABLE(inventory_id uuid, product_id uuid, new_quantity integer, movement_id uuid)' AS expected_return_signature,
    CASE 
        WHEN s.match_count = 0 THEN 'MISSING FUNCTION'
        WHEN s.match_count > 1 THEN 'UNEXPECTED MULTIPLE MATCHES (OVERLOAD HAZARD: ' || s.match_count::text || ' MATCHES)'
        WHEN f.return_signature != 'TABLE(inventory_id uuid, product_id uuid, new_quantity integer, movement_id uuid)' THEN 'WRONG RETURN SIGNATURE: ' || f.return_signature
        ELSE 'PRESENT (EXACT SIGNATURE AND RETURN TYPE MATCH)'
    END AS resolution_status,
    f.func_oid,
    f.function_name,
    f.schema_name,
    f.argument_signature,
    f.return_signature,
    f.owner_role,
    f.is_security_definer,
    f.search_path_configuration,
    f.raw_access_control_list,
    f.anon_can_execute,
    f.authenticated_can_execute,
    f.service_role_can_execute,
    f.complete_function_source
FROM match_summary s
LEFT JOIN matched_funcs f ON true;

-- ------------------------------------------------------------------------------
-- SECTION 5: Composite Foreign Key Integrity and Target Column Mappings
-- Verifies source table/schema, target table/schema, convalidated status, and exact
-- column order for all 4 composite business isolation foreign keys.
-- Handles NULL target relation gracefully. Separates historical data validation
-- (convalidated) from write enforcement (governed by internal pg_trigger states).
-- ------------------------------------------------------------------------------
WITH expected_fks(expected_fk_name, expected_source_schema, expected_source, expected_target_schema, expected_target, expected_src_cols, expected_ref_cols) AS (
    VALUES 
        ('fk_inventory_business_product', 'public', 'inventory', 'public', 'products', ARRAY['business_id', 'product_id']::text[], ARRAY['business_id', 'id']::text[]),
        ('fk_order_items_business_order', 'public', 'order_items', 'public', 'orders', ARRAY['business_id', 'order_id']::text[], ARRAY['business_id', 'id']::text[]),
        ('fk_order_items_business_product', 'public', 'order_items', 'public', 'products', ARRAY['business_id', 'product_id']::text[], ARRAY['business_id', 'id']::text[]),
        ('fk_stock_movements_business_product', 'public', 'stock_movements', 'public', 'products', ARRAY['business_id', 'product_id']::text[], ARRAY['business_id', 'id']::text[])
)
SELECT 
    efk.expected_fk_name,
    efk.expected_source AS source_table,
    efk.expected_target AS target_table,
    COALESCE(target_rel.relname, 'N/A (MISSING)') AS actual_target_table,
    COALESCE(target_ns.nspname, 'N/A (MISSING)') AS actual_target_schema,
    CASE 
        WHEN src_rel.relname IS NULL THEN 'MISSING SOURCE TABLE'
        WHEN c.conname IS NULL THEN 'MISSING CONSTRAINT'
        WHEN target_rel.relname IS NULL THEN 'TARGET TABLE UNRESOLVED (NULL)'
        WHEN target_ns.nspname != efk.expected_target_schema THEN 'WRONG TARGET SCHEMA: ' || target_ns.nspname
        WHEN target_rel.relname != efk.expected_target THEN 'WRONG TARGET TABLE: ' || target_rel.relname
        WHEN NOT c.convalidated THEN 'NOT VALIDATED'
        WHEN ARRAY(
            SELECT a.attname::text 
            FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
            ORDER BY k.ord
        ) != efk.expected_src_cols THEN 'WRONG SOURCE COLUMN MAPPING'
        WHEN ARRAY(
            SELECT a.attname::text 
            FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum
            ORDER BY k.ord
        ) != efk.expected_ref_cols THEN 'WRONG REFERENCED COLUMN MAPPING'
        ELSE 'VALID (CORRECT TARGET AND ORDERED COLUMNS)'
    END AS verification_status,
    COALESCE(c.convalidated, false) AS is_validated,
    CASE 
        WHEN c.conname IS NULL THEN 'N/A (MISSING)'
        WHEN NOT EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgconstraint = c.oid) THEN 'UNENFORCED (NO INTERNAL FK TRIGGERS)'
        WHEN EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgconstraint = c.oid AND t.tgenabled = 'D') THEN 'WRITE ENFORCEMENT SUSPENDED (TRIGGER DISABLED)'
        ELSE 'ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE)'
    END AS write_enforcement_status,
    ARRAY(
        SELECT a.attname::text 
        FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
        ORDER BY k.ord
    ) AS actual_source_columns,
    ARRAY(
        SELECT a.attname::text 
        FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum
        ORDER BY k.ord
    ) AS actual_referenced_columns,
    COALESCE(pg_get_constraintdef(c.oid), 'N/A') AS full_constraint_definition
FROM expected_fks efk
LEFT JOIN pg_class src_rel ON src_rel.relname = efk.expected_source 
    AND src_rel.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = efk.expected_source_schema)
LEFT JOIN pg_constraint c ON c.conrelid = src_rel.oid 
    AND c.conname = efk.expected_fk_name 
    AND c.contype = 'f'
LEFT JOIN pg_class target_rel ON target_rel.oid = c.confrelid
LEFT JOIN pg_namespace target_ns ON target_ns.oid = target_rel.relnamespace
ORDER BY efk.expected_source, efk.expected_fk_name;

-- ------------------------------------------------------------------------------
-- SECTION 6A: Table RLS Status & Enablement
-- Verifies Row Level Security enablement independently from policy existence
-- across all 10 operational tables.
-- ------------------------------------------------------------------------------
WITH expected_tables(table_name) AS (
    VALUES 
        ('businesses'), ('business_members'), ('products'), ('inventory'),
        ('customers'), ('orders'), ('order_items'), ('invoices'),
        ('stock_movements'), ('audit_logs')
)
SELECT 
    et.table_name,
    CASE 
        WHEN c.relname IS NULL THEN 'MISSING TABLE'
        WHEN NOT c.relrowsecurity THEN 'RLS DISABLED (CRITICAL NON-COMPLIANCE)'
        ELSE 'RLS ENABLED'
    END AS rls_status,
    COALESCE(c.relrowsecurity, false) AS rls_enabled,
    COALESCE(c.relforcerowsecurity, false) AS rls_forced,
    (SELECT count(*) FROM pg_policy pol WHERE pol.polrelid = c.oid) AS policy_count
FROM expected_tables et
LEFT JOIN pg_class c ON c.relname = et.table_name 
    AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
ORDER BY et.table_name;

-- ------------------------------------------------------------------------------
-- SECTION 6B: RLS Detailed Policy Inspection
-- Verifies individual policies, commands, permissiveness (PERMISSIVE / RESTRICTIVE),
-- USING / WITH CHECK expressions, and maps ONLY OID 0 to 'PUBLIC'.
-- NOTE: Inspecting policy definitions in the catalog confirms policy presence and
-- rules, but does NOT prove runtime tenant isolation without simulated testing
-- under authenticated caller JWT contexts.
-- ------------------------------------------------------------------------------
WITH expected_tables(table_name) AS (
    VALUES 
        ('businesses'), ('business_members'), ('products'), ('inventory'),
        ('customers'), ('orders'), ('order_items'), ('invoices'),
        ('stock_movements'), ('audit_logs')
)
SELECT 
    et.table_name,
    CASE 
        WHEN c.relname IS NULL THEN 'MISSING TABLE'
        WHEN pol.polname IS NULL THEN 'NO POLICIES DEFINED'
        ELSE 'POLICY PRESENT'
    END AS policy_status,
    COALESCE(pol.polname, 'N/A') AS policy_name,
    CASE pol.polpermissive
        WHEN true THEN 'PERMISSIVE'
        WHEN false THEN 'RESTRICTIVE'
        ELSE 'UNKNOWN'
    END AS policy_permissiveness,
    CASE pol.polcmd
        WHEN 'r' THEN 'SELECT'
        WHEN 'a' THEN 'INSERT'
        WHEN 'w' THEN 'UPDATE'
        WHEN 'd' THEN 'DELETE'
        WHEN '*' THEN 'ALL'
        ELSE 'N/A'
    END AS command,
    ARRAY(
        SELECT 
            CASE 
                WHEN u.role_oid = 0 THEN 'PUBLIC'
                ELSE COALESCE(r.rolname, 'UNKNOWN (OID ' || u.role_oid::text || ')')
            END
        FROM unnest(pol.polroles) AS u(role_oid)
        LEFT JOIN pg_roles r ON u.role_oid = r.oid
    ) AS target_roles,
    COALESCE(pg_get_expr(pol.polqual, pol.polrelid), 'N/A') AS using_expression,
    COALESCE(pg_get_expr(pol.polwithcheck, pol.polrelid), 'N/A') AS with_check_expression
FROM expected_tables et
LEFT JOIN pg_class c ON c.relname = et.table_name 
    AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
LEFT JOIN pg_policy pol ON c.oid = pol.polrelid
ORDER BY et.table_name, pol.polname;

-- ------------------------------------------------------------------------------
-- SECTION 7: Helper Functions and Operational Procedures
-- Matches all 9 helper functions using exact positional schema-qualified argument types.
-- NEVER uses fragile identity arguments text matching.
-- ------------------------------------------------------------------------------
WITH expected_functions(expected_name, expected_arg_types) AS (
    VALUES 
        ('set_updated_at_timestamp', ARRAY[]::text[]),
        ('get_auth_user_id', ARRAY[]::text[]),
        ('get_business_member_role', ARRAY['pg_catalog.uuid', 'pg_catalog.uuid']::text[]),
        ('has_business_role', ARRAY['pg_catalog.uuid', 'pg_catalog.uuid', 'public.app_role']::text[]),
        ('handle_new_business', ARRAY[]::text[]),
        ('prevent_immutable_modification', ARRAY[]::text[]),
        ('approve_order_atomic', ARRAY['pg_catalog.uuid', 'pg_catalog.uuid', 'pg_catalog.uuid']::text[]),
        ('cancel_order_atomic', ARRAY['pg_catalog.uuid', 'pg_catalog.uuid', 'pg_catalog.uuid', 'pg_catalog.text']::text[]),
        ('allocate_invoice_atomic', ARRAY['pg_catalog.uuid', 'pg_catalog.uuid', 'pg_catalog.uuid', 'pg_catalog.date']::text[])
)
SELECT 
    ef.expected_name,
    array_to_string(ef.expected_arg_types, ', ') AS expected_arg_types,
    CASE 
        WHEN p.oid IS NULL THEN 'MISSING FUNCTION'
        ELSE 'PRESENT (EXACT SIGNATURE MATCH)'
    END AS verification_status,
    COALESCE(pg_get_function_identity_arguments(p.oid), 'N/A') AS actual_arguments,
    COALESCE(pg_get_function_result(p.oid), 'N/A') AS return_type,
    COALESCE(r.rolname, 'N/A') AS owner_role,
    COALESCE(p.prosecdef, false) AS is_security_definer,
    COALESCE(array_to_string(p.proconfig, ', '), 'NONE') AS search_path_setting,
    COALESCE(has_function_privilege('authenticated', p.oid, 'EXECUTE'), false) AS authenticated_can_execute,
    COALESCE(has_function_privilege('anon', p.oid, 'EXECUTE'), false) AS anon_can_execute
FROM expected_functions ef
LEFT JOIN pg_proc p ON p.proname = ef.expected_name 
    AND p.pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    AND ARRAY(
        SELECT arg_ns.nspname || '.' || arg_typ.typname 
        FROM unnest(p.proargtypes::oid[]) WITH ORDINALITY AS u(arg_oid, ord)
        JOIN pg_type arg_typ ON u.arg_oid = arg_typ.oid
        JOIN pg_namespace arg_ns ON arg_typ.typnamespace = arg_ns.oid
        ORDER BY u.ord
    ) = ef.expected_arg_types
LEFT JOIN pg_roles r ON p.proowner = r.oid
ORDER BY ef.expected_name;

-- ------------------------------------------------------------------------------
-- SECTION 8: Detailed Function ACL Deconstruction via aclexplode()
-- Targets the exact schema-qualified adjust_stock_atomic function signature.
-- Deconstructs grantor, grantee (with OID 0 mapped to 'PUBLIC'), privilege type,
-- grant options (is_grantable), and explicit vs default ACL source.
-- NOTE: ACL decomposition extracts catalog permissions for DBA review; it does
-- not evaluate automated security correctness predicates. Function attributes
-- (owner, prosecdef, search_path) are audited in Section 4.
-- ------------------------------------------------------------------------------
SELECT 
    p.proname AS function_name,
    pg_get_function_identity_arguments(p.oid) AS identity_arguments,
    r_owner.rolname AS owner_name,
    CASE 
        WHEN a.grantee = 0 THEN 'PUBLIC'
        ELSE COALESCE(r_grantee.rolname, 'UNKNOWN (OID ' || a.grantee::text || ')')
    END AS grantee_role,
    COALESCE(r_grantor.rolname, 'UNKNOWN (OID ' || a.grantor::text || ')') AS grantor_role,
    a.privilege_type,
    a.is_grantable,
    CASE WHEN p.proacl IS NULL THEN 'DEFAULT ACL' ELSE 'EXPLICIT ACL' END AS acl_source
FROM pg_proc p
JOIN pg_roles r_owner ON p.proowner = r_owner.oid
CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a
LEFT JOIN pg_roles r_grantee ON a.grantee = r_grantee.oid
LEFT JOIN pg_roles r_grantor ON a.grantor = r_grantor.oid
WHERE p.pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
  AND p.proname = 'adjust_stock_atomic'
  AND ARRAY(
      SELECT arg_ns.nspname || '.' || arg_typ.typname 
      FROM unnest(p.proargtypes::oid[]) WITH ORDINALITY AS u(arg_oid, ord)
      JOIN pg_type arg_typ ON u.arg_oid = arg_typ.oid
      JOIN pg_namespace arg_ns ON arg_typ.typnamespace = arg_ns.oid
      ORDER BY u.ord
  ) = ARRAY['pg_catalog.uuid', 'pg_catalog.uuid', 'pg_catalog.int4', 'public.stock_movement_type', 'pg_catalog.text', 'pg_catalog.uuid']
ORDER BY grantee_role, a.privilege_type;

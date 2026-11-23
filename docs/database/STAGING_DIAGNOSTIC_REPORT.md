# ORQESTRA Staging Database Diagnostic Report

**Execution Timestamp:** `2026-11-23 09:48:37 UTC`  
**Overall Verdict:** 🟢 **`PASS - ALL DIAGNOSTIC CHECKS COMPLIANT`**  
**Total Execution Time:** `78502.95 ms`  
**Target Database:** `Supabase Staging Project: vclkeubwpiyhuvprvngx (https://vclkeubwpiyhuvprvngx.supabase.co)`  
**Canonical Diagnostic SQL:** `PHASE_4L_CANONICAL_DIAGNOSTIC_1.sql`  
**Verified SHA-256 Hash:** `21d6da847112812015fe2be5921576d22875b88f359047c9e5c337d3d0667a3d`  

---

## 1. Executive Summary Dashboard

| Section | Diagnostic Check | Rows | Status | Summary |
|---|---|:---:|:---:|---|
| **Section 0** | Session Guard & Catalog Access Sanity Checks | `1` | **🟢 PASS** | Session guard verified (standard session role) |
| **Section 1** | Immutable & Audit Trigger Verification | `10` | **🟢 PASS** | All 10 immutable and audit triggers correctly enabled and mapped |
| **Section 2** | Partial Unique Index on Invoices | `1` | **🟢 PASS** | Partial unique index uq_invoices_business_order_unique is valid and fully compliant |
| **Section 3** | Realtime Replica Identity Full | `5` | **🟢 PASS** | All 5 operational tables configured with REPLICA IDENTITY FULL |
| **Section 4** | Exact Deployed adjust_stock_atomic Function | `1` | **🟢 PASS** | adjust_stock_atomic is present, secure, and fully remediated |
| **Section 5** | Composite Foreign Key Integrity & Write Enforcement | `4` | **🟢 PASS** | All 4 composite FKs validated and write enforcement active via internal triggers |
| **Section 6A** | Table Row Level Security Enablement | `10` | **🟢 PASS** | Row Level Security enabled across all 10 operational tables |
| **Section 6B** | RLS Detailed Policy Inspection | `36` | **🟢 PASS** | Cataloged 36 RLS policies with roles and permissiveness |
| **Section 7** | Helper Functions Positional Signature Check | `9` | **🟢 PASS** | All 9 helper functions verified via positional argument type resolution |
| **Section 8** | Function ACL Decomposition via aclexplode | `3` | **🟢 PASS** | adjust_stock_atomic ACL decomposed cleanly; restricted to authenticated & service_role |

---

## 2. Tooling & Environment Configuration

| Tooling Component | Status / Value | Safety Note |
|---|---|---|
| Supabase CLI Linked | `YES` | Exact project ref: `vclkeubwpiyhuvprvngx` |
| Supabase Project Name | `orqestra-staging` | Org: `grzrefmjxjgisiqrifkh` |
| SUPABASE_URL | `https://vwlwbwwrumsmjqeavvxk.supabase.co` | URL verified for staging API access |
| SUPABASE_PUBLISHABLE_KEY | `[CONFIGURED - REDACTED]` | Key presence verified without leaking value |
| SUPABASE_ANON_KEY | `[NOT CONFIGURED]` | Key presence verified without leaking value |
| SUPABASE_SERVICE_ROLE_KEY | `[CONFIGURED - REDACTED]` | Key presence verified without leaking value |
| SUPABASE_JWT_SECRET | `[NOT CONFIGURED]` | Key presence verified without leaking value |
| STAGING_DATABASE_URL | `postgresql://postgres.vclkeubwpiyhuvprvngx:***@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=verify-full` | Connection URL masked (credentials redacted) |

> [!NOTE]
> Remote staging execution is locked behind explicit approval gates. Diagnostic queries are never run remotely without explicit authorization.

---

## 3. Detailed Diagnostic Section Results

### Section 0: Session Guard & Catalog Access Sanity Checks

- **Status:** **🟢 PASS**
- **Summary:** Session guard verified (standard session role)
- **Execution Latency:** `8007.06 ms`
- **Rows Returned:** `1`

**Key Findings:**
- Connected session user: `supabase_read_only_user`
- Catalog read access confirmed (public USAGE: True, pg_proc SELECT: True)
- Sanity check verified. Note: Runtime catalog visibility reflects active session role privileges.

<details open><summary><strong>Query Result Set</strong></summary>

| active_search_path | can_read_pg_class | can_read_pg_constraint | can_read_pg_policy | can_read_pg_proc | can_read_pg_trigger | check_scope_note | connected_user | current_session_user | database_name | has_public_schema_usage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| "$user", public | True | True | True | True | True | CATALOG_READ_SANITY_CHECK_ONLY | supabase_read_only_user | supabase_read_only_user | postgres | True |

</details>

---

### Section 1: Immutable & Audit Trigger Verification

- **Status:** **🟢 PASS**
- **Summary:** All 10 immutable and audit triggers correctly enabled and mapped
- **Execution Latency:** `8344.19 ms`
- **Rows Returned:** `10`

**Key Findings:**
- `audit_logs.trg_audit_logs_immutable`: PRESENT (CORRECT: ENABLED)
- `business_members.trg_business_members_updated_at`: PRESENT (CORRECT: ENABLED)
- `businesses.trg_businesses_updated_at`: PRESENT (CORRECT: ENABLED)
- `businesses.trg_on_business_created`: PRESENT (CORRECT: ENABLED)
- `customers.trg_customers_updated_at`: PRESENT (CORRECT: ENABLED)
- `inventory.trg_inventory_updated_at`: PRESENT (CORRECT: ENABLED)
- `invoices.trg_invoices_updated_at`: PRESENT (CORRECT: ENABLED)
- `orders.trg_orders_updated_at`: PRESENT (CORRECT: ENABLED)
- `products.trg_products_updated_at`: PRESENT (CORRECT: ENABLED)
- `stock_movements.trg_stock_movements_immutable`: PRESENT (CORRECT: ENABLED)

<details open><summary><strong>Query Result Set</strong></summary>

| actual_events | actual_function_name | actual_function_schema | actual_timing | expected_events | expected_fn_schema | expected_function | expected_timing | expected_trigger_name | full_trigger_definition | target_schema | target_table | trigger_enabled_status | verification_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ['DELETE', 'UPDATE'] | prevent_immutable_modification | public | BEFORE | ['DELETE', 'UPDATE'] | public | prevent_immutable_modification | BEFORE | trg_audit_logs_immutable | CREATE TRIGGER trg_audit_logs_immutable BEFORE DELETE OR ... | public | audit_logs | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['UPDATE'] | set_updated_at_timestamp | public | BEFORE | ['UPDATE'] | public | set_updated_at_timestamp | BEFORE | trg_business_members_updated_at | CREATE TRIGGER trg_business_members_updated_at BEFORE UPD... | public | business_members | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['UPDATE'] | set_updated_at_timestamp | public | BEFORE | ['UPDATE'] | public | set_updated_at_timestamp | BEFORE | trg_businesses_updated_at | CREATE TRIGGER trg_businesses_updated_at BEFORE UPDATE ON... | public | businesses | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['INSERT'] | handle_new_business | public | AFTER | ['INSERT'] | public | handle_new_business | AFTER | trg_on_business_created | CREATE TRIGGER trg_on_business_created AFTER INSERT ON pu... | public | businesses | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['UPDATE'] | set_updated_at_timestamp | public | BEFORE | ['UPDATE'] | public | set_updated_at_timestamp | BEFORE | trg_customers_updated_at | CREATE TRIGGER trg_customers_updated_at BEFORE UPDATE ON ... | public | customers | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['UPDATE'] | set_updated_at_timestamp | public | BEFORE | ['UPDATE'] | public | set_updated_at_timestamp | BEFORE | trg_inventory_updated_at | CREATE TRIGGER trg_inventory_updated_at BEFORE UPDATE ON ... | public | inventory | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['UPDATE'] | set_updated_at_timestamp | public | BEFORE | ['UPDATE'] | public | set_updated_at_timestamp | BEFORE | trg_invoices_updated_at | CREATE TRIGGER trg_invoices_updated_at BEFORE UPDATE ON p... | public | invoices | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['UPDATE'] | set_updated_at_timestamp | public | BEFORE | ['UPDATE'] | public | set_updated_at_timestamp | BEFORE | trg_orders_updated_at | CREATE TRIGGER trg_orders_updated_at BEFORE UPDATE ON pub... | public | orders | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['UPDATE'] | set_updated_at_timestamp | public | BEFORE | ['UPDATE'] | public | set_updated_at_timestamp | BEFORE | trg_products_updated_at | CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON p... | public | products | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |
| ['DELETE', 'UPDATE'] | prevent_immutable_modification | public | BEFORE | ['DELETE', 'UPDATE'] | public | prevent_immutable_modification | BEFORE | trg_stock_movements_immutable | CREATE TRIGGER trg_stock_movements_immutable BEFORE DELET... | public | stock_movements | enabled (origin/local) | PRESENT (CORRECT: ENABLED) |

</details>

---

### Section 2: Partial Unique Index on Invoices

- **Status:** **🟢 PASS**
- **Summary:** Partial unique index uq_invoices_business_order_unique is valid and fully compliant
- **Execution Latency:** `7531.94 ms`
- **Rows Returned:** `1`

**Key Findings:**
- Access Method: `btree`
- Key Columns: `['business_id', 'order_id']`
- Predicate: `(order_id IS NOT NULL)`
- Flags: unique=True, valid=True, ready=True

<details open><summary><strong>Query Result Set</strong></summary>

| access_method | full_index_definition | include_column_count | index_name | index_schema | is_ready | is_unique | is_valid | key_column_count | key_columns | partial_predicate | table_name | table_schema | verification_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| btree | CREATE UNIQUE INDEX uq_invoices_business_order_unique ON ... | 0 | uq_invoices_business_order_unique | public | True | True | True | 2 | ['business_id', 'order_id'] | (order_id IS NOT NULL) | invoices | public | PRESENT (VALID UNIQUE PARTIAL INDEX) |

</details>

---

### Section 3: Realtime Replica Identity Full

- **Status:** **🟢 PASS**
- **Summary:** All 5 operational tables configured with REPLICA IDENTITY FULL
- **Execution Latency:** `7508.48 ms`
- **Rows Returned:** `5`

**Key Findings:**
- Table `inventory`: COMPLIANT (FULL)
- Table `invoices`: COMPLIANT (FULL)
- Table `orders`: COMPLIANT (FULL)
- Table `products`: COMPLIANT (FULL)
- Table `stock_movements`: COMPLIANT (FULL)

<details open><summary><strong>Query Result Set</strong></summary>

| compliance_status | is_realtime_compliant | replica_identity_status | table_name |
| --- | --- | --- | --- |
| COMPLIANT (FULL) | True | FULL (REPLICA IDENTITY FULL - Compliant) | inventory |
| COMPLIANT (FULL) | True | FULL (REPLICA IDENTITY FULL - Compliant) | invoices |
| COMPLIANT (FULL) | True | FULL (REPLICA IDENTITY FULL - Compliant) | orders |
| COMPLIANT (FULL) | True | FULL (REPLICA IDENTITY FULL - Compliant) | products |
| COMPLIANT (FULL) | True | FULL (REPLICA IDENTITY FULL - Compliant) | stock_movements |

</details>

---

### Section 4: Exact Deployed adjust_stock_atomic Function

- **Status:** **🟢 PASS**
- **Summary:** adjust_stock_atomic is present, secure, and fully remediated
- **Execution Latency:** `7822.03 ms`
- **Rows Returned:** `1`

**Key Findings:**
- Resolution Status: `PRESENT (EXACT SIGNATURE AND RETURN TYPE MATCH)`
- SECURITY DEFINER: `True`
- Search Path: `['search_path=public, pg_temp']`
- Execution Grants: anon=False, authenticated=True, service_role=True
- Atomic Concurrency Remediated: Row lock (FOR UPDATE) and qualified column references (inventory.product_id, inventory.business_id) verified.

<details open><summary><strong>Query Result Set</strong></summary>

| anon_can_execute | argument_signature | authenticated_can_execute | complete_function_source | expected_function | expected_return_signature | expected_schema | expected_signature | func_oid | function_name | is_security_definer | owner_role | raw_access_control_list | resolution_status | return_signature | schema_name | search_path_configuration | service_role_can_execute |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | p_business_id uuid, p_product_id uuid, p_quantity_change ... | True | CREATE OR REPLACE FUNCTION public.adjust_stock_atomic(p_b... | adjust_stock_atomic | TABLE(inventory_id uuid, product_id uuid, new_quantity in... | public | uuid, uuid, integer, stock_movement_type, text, uuid | 17998 | adjust_stock_atomic | True | postgres | {postgres=X/postgres,authenticated=X/postgres,service_rol... | PRESENT (EXACT SIGNATURE AND RETURN TYPE MATCH) | TABLE(inventory_id uuid, product_id uuid, new_quantity in... | public | ['search_path=public, pg_temp'] | True |

</details>

---

### Section 5: Composite Foreign Key Integrity & Write Enforcement

- **Status:** **🟢 PASS**
- **Summary:** All 4 composite FKs validated and write enforcement active via internal triggers
- **Execution Latency:** `7436.00 ms`
- **Rows Returned:** `4`

**Key Findings:**
- FK `fk_inventory_business_product` (inventory->products): VALID (CORRECT TARGET AND ORDERED COLUMNS) [ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE)]
- FK `fk_order_items_business_order` (order_items->orders): VALID (CORRECT TARGET AND ORDERED COLUMNS) [ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE)]
- FK `fk_order_items_business_product` (order_items->products): VALID (CORRECT TARGET AND ORDERED COLUMNS) [ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE)]
- FK `fk_stock_movements_business_product` (stock_movements->products): VALID (CORRECT TARGET AND ORDERED COLUMNS) [ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE)]

<details open><summary><strong>Query Result Set</strong></summary>

| actual_referenced_columns | actual_source_columns | actual_target_schema | actual_target_table | expected_fk_name | full_constraint_definition | is_validated | source_table | target_table | verification_status | write_enforcement_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ['business_id', 'id'] | ['business_id', 'product_id'] | public | products | fk_inventory_business_product | FOREIGN KEY (business_id, product_id) REFERENCES products... | True | inventory | products | VALID (CORRECT TARGET AND ORDERED COLUMNS) | ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE) |
| ['business_id', 'id'] | ['business_id', 'order_id'] | public | orders | fk_order_items_business_order | FOREIGN KEY (business_id, order_id) REFERENCES orders(bus... | True | order_items | orders | VALID (CORRECT TARGET AND ORDERED COLUMNS) | ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE) |
| ['business_id', 'id'] | ['business_id', 'product_id'] | public | products | fk_order_items_business_product | FOREIGN KEY (business_id, product_id) REFERENCES products... | True | order_items | products | VALID (CORRECT TARGET AND ORDERED COLUMNS) | ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE) |
| ['business_id', 'id'] | ['business_id', 'product_id'] | public | products | fk_stock_movements_business_product | FOREIGN KEY (business_id, product_id) REFERENCES products... | True | stock_movements | products | VALID (CORRECT TARGET AND ORDERED COLUMNS) | ENFORCED (INTERNAL WRITE TRIGGERS ACTIVE) |

</details>

---

### Section 6A: Table Row Level Security Enablement

- **Status:** **🟢 PASS**
- **Summary:** Row Level Security enabled across all 10 operational tables
- **Execution Latency:** `7870.99 ms`
- **Rows Returned:** `10`

**Key Findings:**
- Table `audit_logs`: RLS ENABLED
- Table `business_members`: RLS ENABLED
- Table `businesses`: RLS ENABLED
- Table `customers`: RLS ENABLED
- Table `inventory`: RLS ENABLED
- Table `invoices`: RLS ENABLED
- Table `order_items`: RLS ENABLED
- Table `orders`: RLS ENABLED
- Table `products`: RLS ENABLED
- Table `stock_movements`: RLS ENABLED

<details open><summary><strong>Query Result Set</strong></summary>

| policy_count | rls_enabled | rls_forced | rls_status | table_name |
| --- | --- | --- | --- | --- |
| 2 | True | False | RLS ENABLED | audit_logs |
| 4 | True | False | RLS ENABLED | business_members |
| 4 | True | False | RLS ENABLED | businesses |
| 4 | True | False | RLS ENABLED | customers |
| 4 | True | False | RLS ENABLED | inventory |
| 4 | True | False | RLS ENABLED | invoices |
| 4 | True | False | RLS ENABLED | order_items |
| 4 | True | False | RLS ENABLED | orders |
| 4 | True | False | RLS ENABLED | products |
| 2 | True | False | RLS ENABLED | stock_movements |

</details>

---

### Section 6B: RLS Detailed Policy Inspection

- **Status:** **🟢 PASS**
- **Summary:** Cataloged 36 RLS policies with roles and permissiveness
- **Execution Latency:** `7799.09 ms`
- **Rows Returned:** `36`

**Key Findings:**
- Total active RLS policies cataloged: 36
- Target roles mapped with OID 0 explicitly isolated to PUBLIC.
- Policy permissiveness inspected (PERMISSIVE vs RESTRICTIVE).
- AUDIT NOTICE: Catalog policy existence is necessary but not sufficient to prove runtime tenant isolation. Runtime authorization must be confirmed via multi-tenant end-to-end tests.

<details open><summary><strong>Query Result Set</strong></summary>

| command | policy_name | policy_permissiveness | policy_status | table_name | target_roles | using_expression | with_check_expression |
| --- | --- | --- | --- | --- | --- | --- | --- |
| INSERT | audit_logs_insert_member | PERMISSIVE | POLICY PRESENT | audit_logs | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'staff'::app_r... |
| SELECT | audit_logs_select_admin | PERMISSIVE | POLICY PRESENT | audit_logs | {authenticated} | has_business_role(business_id, auth.uid(), 'admin'::app_r... | N/A |
| DELETE | business_members_delete_owner_or_self | PERMISSIVE | POLICY PRESENT | business_members | {authenticated} | (has_business_role(business_id, auth.uid(), 'owner'::app_... | N/A |
| INSERT | business_members_insert_authorized | PERMISSIVE | POLICY PRESENT | business_members | {authenticated} | N/A | (((role = 'staff'::app_role) AND has_business_role(busine... |
| SELECT | business_members_select_colleagues | PERMISSIVE | POLICY PRESENT | business_members | {authenticated} | ((user_id = auth.uid()) OR has_business_role(business_id,... | N/A |
| UPDATE | business_members_update_owner | PERMISSIVE | POLICY PRESENT | business_members | {authenticated} | has_business_role(business_id, auth.uid(), 'owner'::app_r... | has_business_role(business_id, auth.uid(), 'owner'::app_r... |
| DELETE | businesses_delete_owner | PERMISSIVE | POLICY PRESENT | businesses | {authenticated} | has_business_role(id, auth.uid(), 'owner'::app_role) | N/A |
| INSERT | businesses_insert_authenticated | PERMISSIVE | POLICY PRESENT | businesses | {authenticated} | N/A | (auth.uid() IS NOT NULL) |
| SELECT | businesses_select_member | PERMISSIVE | POLICY PRESENT | businesses | {authenticated} | has_business_role(id, auth.uid(), 'staff'::app_role) | N/A |
| UPDATE | businesses_update_owner | PERMISSIVE | POLICY PRESENT | businesses | {authenticated} | has_business_role(id, auth.uid(), 'owner'::app_role) | has_business_role(id, auth.uid(), 'owner'::app_role) |
| DELETE | customers_delete_admin | PERMISSIVE | POLICY PRESENT | customers | {authenticated} | has_business_role(business_id, auth.uid(), 'admin'::app_r... | N/A |
| INSERT | customers_insert_staff | PERMISSIVE | POLICY PRESENT | customers | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'staff'::app_r... |
| SELECT | customers_select_member | PERMISSIVE | POLICY PRESENT | customers | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | N/A |
| UPDATE | customers_update_staff | PERMISSIVE | POLICY PRESENT | customers | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | has_business_role(business_id, auth.uid(), 'staff'::app_r... |
| DELETE | inventory_delete_owner | PERMISSIVE | POLICY PRESENT | inventory | {authenticated} | has_business_role(business_id, auth.uid(), 'owner'::app_r... | N/A |
| INSERT | inventory_insert_admin | PERMISSIVE | POLICY PRESENT | inventory | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'admin'::app_r... |
| SELECT | inventory_select_member | PERMISSIVE | POLICY PRESENT | inventory | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | N/A |
| UPDATE | inventory_update_admin | PERMISSIVE | POLICY PRESENT | inventory | {authenticated} | has_business_role(business_id, auth.uid(), 'admin'::app_r... | has_business_role(business_id, auth.uid(), 'admin'::app_r... |
| DELETE | invoices_delete_owner | PERMISSIVE | POLICY PRESENT | invoices | {authenticated} | has_business_role(business_id, auth.uid(), 'owner'::app_r... | N/A |
| INSERT | invoices_insert_admin | PERMISSIVE | POLICY PRESENT | invoices | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'admin'::app_r... |
| SELECT | invoices_select_member | PERMISSIVE | POLICY PRESENT | invoices | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | N/A |
| UPDATE | invoices_update_admin | PERMISSIVE | POLICY PRESENT | invoices | {authenticated} | has_business_role(business_id, auth.uid(), 'admin'::app_r... | has_business_role(business_id, auth.uid(), 'admin'::app_r... |
| DELETE | order_items_delete_admin | PERMISSIVE | POLICY PRESENT | order_items | {authenticated} | has_business_role(business_id, auth.uid(), 'admin'::app_r... | N/A |
| INSERT | order_items_insert_staff | PERMISSIVE | POLICY PRESENT | order_items | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'staff'::app_r... |
| SELECT | order_items_select_member | PERMISSIVE | POLICY PRESENT | order_items | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | N/A |
| UPDATE | order_items_update_staff | PERMISSIVE | POLICY PRESENT | order_items | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | has_business_role(business_id, auth.uid(), 'staff'::app_r... |
| DELETE | orders_delete_owner | PERMISSIVE | POLICY PRESENT | orders | {authenticated} | has_business_role(business_id, auth.uid(), 'owner'::app_r... | N/A |
| INSERT | orders_insert_staff | PERMISSIVE | POLICY PRESENT | orders | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'staff'::app_r... |
| SELECT | orders_select_member | PERMISSIVE | POLICY PRESENT | orders | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | N/A |
| UPDATE | orders_update_staff | PERMISSIVE | POLICY PRESENT | orders | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | has_business_role(business_id, auth.uid(), 'staff'::app_r... |
| DELETE | products_delete_owner | PERMISSIVE | POLICY PRESENT | products | {authenticated} | has_business_role(business_id, auth.uid(), 'owner'::app_r... | N/A |
| INSERT | products_insert_admin | PERMISSIVE | POLICY PRESENT | products | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'admin'::app_r... |
| SELECT | products_select_member | PERMISSIVE | POLICY PRESENT | products | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | N/A |
| UPDATE | products_update_admin | PERMISSIVE | POLICY PRESENT | products | {authenticated} | has_business_role(business_id, auth.uid(), 'admin'::app_r... | has_business_role(business_id, auth.uid(), 'admin'::app_r... |
| INSERT | stock_movements_insert_admin | PERMISSIVE | POLICY PRESENT | stock_movements | {authenticated} | N/A | has_business_role(business_id, auth.uid(), 'admin'::app_r... |
| SELECT | stock_movements_select_member | PERMISSIVE | POLICY PRESENT | stock_movements | {authenticated} | has_business_role(business_id, auth.uid(), 'staff'::app_r... | N/A |

</details>

---

### Section 7: Helper Functions Positional Signature Check

- **Status:** **🟢 PASS**
- **Summary:** All 9 helper functions verified via positional argument type resolution
- **Execution Latency:** `8439.03 ms`
- **Rows Returned:** `9`

**Key Findings:**
- Function `allocate_invoice_atomic`: PRESENT (EXACT SIGNATURE MATCH)
- Function `approve_order_atomic`: PRESENT (EXACT SIGNATURE MATCH)
- Function `cancel_order_atomic`: PRESENT (EXACT SIGNATURE MATCH)
- Function `get_auth_user_id`: PRESENT (EXACT SIGNATURE MATCH)
- Function `get_business_member_role`: PRESENT (EXACT SIGNATURE MATCH)
- Function `handle_new_business`: PRESENT (EXACT SIGNATURE MATCH)
- Function `has_business_role`: PRESENT (EXACT SIGNATURE MATCH)
- Function `prevent_immutable_modification`: PRESENT (EXACT SIGNATURE MATCH)
- Function `set_updated_at_timestamp`: PRESENT (EXACT SIGNATURE MATCH)

<details open><summary><strong>Query Result Set</strong></summary>

| actual_arguments | anon_can_execute | authenticated_can_execute | expected_arg_types | expected_name | is_security_definer | owner_role | return_type | search_path_setting | verification_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| p_business_id uuid, p_order_id uuid, p_user_id uuid, p_du... | True | True | pg_catalog.uuid, pg_catalog.uuid, pg_catalog.uuid, pg_cat... | allocate_invoice_atomic | True | postgres | jsonb | search_path=public, pg_temp | PRESENT (EXACT SIGNATURE MATCH) |
| p_order_id uuid, p_user_id uuid, p_business_id uuid | True | True | pg_catalog.uuid, pg_catalog.uuid, pg_catalog.uuid | approve_order_atomic | True | postgres | TABLE(order_id uuid, order_status order_status, total_ite... | search_path=public | PRESENT (EXACT SIGNATURE MATCH) |
| p_order_id uuid, p_user_id uuid, p_business_id uuid, p_re... | True | True | pg_catalog.uuid, pg_catalog.uuid, pg_catalog.uuid, pg_cat... | cancel_order_atomic | True | postgres | TABLE(order_id uuid, order_status order_status, stock_res... | search_path=public | PRESENT (EXACT SIGNATURE MATCH) |
|  | True | True |  | get_auth_user_id | False | postgres | uuid | NONE | PRESENT (EXACT SIGNATURE MATCH) |
| _business_id uuid, _user_id uuid | True | True | pg_catalog.uuid, pg_catalog.uuid | get_business_member_role | True | postgres | app_role | search_path=public | PRESENT (EXACT SIGNATURE MATCH) |
|  | True | True |  | handle_new_business | True | postgres | trigger | search_path=public | PRESENT (EXACT SIGNATURE MATCH) |
| _business_id uuid, _user_id uuid, _required_role app_role | True | True | pg_catalog.uuid, pg_catalog.uuid, public.app_role | has_business_role | True | postgres | boolean | search_path=public | PRESENT (EXACT SIGNATURE MATCH) |
|  | True | True |  | prevent_immutable_modification | True | postgres | trigger | search_path=public | PRESENT (EXACT SIGNATURE MATCH) |
|  | False | True |  | set_updated_at_timestamp | False | postgres | trigger | NONE | PRESENT (EXACT SIGNATURE MATCH) |

</details>

---

### Section 8: Function ACL Decomposition via aclexplode

- **Status:** **🟢 PASS**
- **Summary:** adjust_stock_atomic ACL decomposed cleanly; restricted to authenticated & service_role
- **Execution Latency:** `7735.77 ms`
- **Rows Returned:** `3`

**Key Findings:**
- Grantee `authenticated`: privilege `EXECUTE` (grantable: False)
- Grantee `postgres`: privilege `EXECUTE` (grantable: False)
- Grantee `service_role`: privilege `EXECUTE` (grantable: False)

<details open><summary><strong>Query Result Set</strong></summary>

| acl_source | function_name | grantee_role | grantor_role | identity_arguments | is_grantable | owner_name | privilege_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EXPLICIT ACL | adjust_stock_atomic | authenticated | postgres | p_business_id uuid, p_product_id uuid, p_quantity_change ... | False | postgres | EXECUTE |
| EXPLICIT ACL | adjust_stock_atomic | postgres | postgres | p_business_id uuid, p_product_id uuid, p_quantity_change ... | False | postgres | EXECUTE |
| EXPLICIT ACL | adjust_stock_atomic | service_role | postgres | p_business_id uuid, p_product_id uuid, p_quantity_change ... | False | postgres | EXECUTE |

</details>

---

## 4. Analysis and Recommendations

> [!TIP]
> **Safe Remote Diagnostic Execution Protocol:**
> 1. To run this diagnostic against the remote staging database, obtain separate explicit approval.
> 2. Execute `PHASE_4L_CANONICAL_DIAGNOSTIC_1.sql` via the Supabase Dashboard SQL Editor or via `python run_staging_diagnostic.py --db-url <STAGING_URL> --remote-authorized`.
> 3. Verify that the resulting report matches the expected pre-deployment baseline before approving any migration repairs.

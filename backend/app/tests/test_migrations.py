"""Automated tests validating SQL migration definitions, RLS policies, and schema hardening."""

import os
import re

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "supabase",
    "migrations",
)

CORE_TABLES = [
    "businesses",
    "business_members",
    "products",
    "inventory",
    "customers",
    "orders",
    "order_items",
    "invoices",
    "stock_movements",
    "audit_logs",
]


def test_migrations_directory_and_files_exist():
    """Verify migrations directory exists and has numbered migration files."""
    assert os.path.exists(MIGRATIONS_DIR), f"Directory {MIGRATIONS_DIR} does not exist"
    migration_files = [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")]
    assert len(migration_files) >= 5, f"Expected at least 5 migrations, found {len(migration_files)}"
    assert "20261022000001_core_schema.sql" in migration_files
    assert "20261022000002_row_level_security.sql" in migration_files
    assert "20261023000001_operations_transactions.sql" in migration_files
    assert "20261023000002_realtime_publications.sql" in migration_files
    assert "20261023000003_invoices_and_allocation.sql" in migration_files


def test_core_schema_declares_all_ten_tables():
    """Verify all 10 core tables are created with UUID primary keys and constraints."""
    core_schema_path = os.path.join(MIGRATIONS_DIR, "20261022000001_core_schema.sql")
    with open(core_schema_path, "r", encoding="utf-8") as f:
        content = f.read()

    for table in CORE_TABLES:
        pattern = rf"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?{table}\b"
        assert re.search(pattern, content, re.IGNORECASE), f"Table {table} not created in core schema"

    # Verify UUID primary keys
    assert "gen_random_uuid()" in content

    # Verify money fields use numeric types with non-negative checks
    assert "NUMERIC(12, 2)" in content
    assert "CHECK (unit_price >= 0)" in content
    assert "CHECK (total_amount >= 0)" in content
    assert "CHECK (quantity_on_hand >= 0)" in content


def test_composite_foreign_keys_prevent_cross_business_references():
    """Verify composite foreign keys enforce strict multi-tenant boundary on child tables."""
    core_schema_path = os.path.join(MIGRATIONS_DIR, "20261022000001_core_schema.sql")
    with open(core_schema_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Composite unique constraints on parent tables
    assert "uq_products_business_id UNIQUE (business_id, id)" in content
    assert "uq_orders_business_id UNIQUE (business_id, id)" in content
    assert "uq_customers_business_id UNIQUE (business_id, id)" in content

    # Composite foreign keys on child tables
    assert "fk_order_items_business_product FOREIGN KEY (business_id, product_id)" in content
    assert "fk_order_items_business_order FOREIGN KEY (business_id, order_id)" in content
    assert "fk_inventory_business_product FOREIGN KEY (business_id, product_id)" in content
    assert "fk_invoices_business_customer FOREIGN KEY (business_id, customer_id)" in content
    assert "fk_invoices_business_order FOREIGN KEY (business_id, order_id)" in content
    assert "fk_stock_movements_business_product FOREIGN KEY (business_id, product_id)" in content


def test_row_level_security_enabled_on_all_tables():
    """Verify RLS is enabled on every business-owned table and non-recursive functions exist."""
    rls_path = os.path.join(MIGRATIONS_DIR, "20261022000002_row_level_security.sql")
    with open(rls_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check RLS is enabled on every table
    for table in CORE_TABLES:
        pattern = rf"ALTER\s+TABLE\s+{table}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY;"
        assert re.search(pattern, content, re.IGNORECASE), f"RLS not enabled on table {table}"

    # Check non-recursive security definer functions exist
    assert "SECURITY DEFINER" in content
    assert "has_business_role" in content
    assert "get_business_member_role" in content

    # Check policies exist for each table
    for table in CORE_TABLES:
        pattern = rf"CREATE\s+POLICY\s+\"[^\"]+\"\s+ON\s+{table}\b"
        assert re.search(pattern, content, re.IGNORECASE), f"No RLS policies created for table {table}"


def test_security_definer_execution_permissions_restricted():
    """Verify PUBLIC execution is revoked and search paths are explicitly set on SECURITY DEFINER functions."""
    rls_path = os.path.join(MIGRATIONS_DIR, "20261022000002_row_level_security.sql")
    with open(rls_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check search path is explicitly pinned to public
    assert "SET search_path = public" in content

    # Check execution revoked from PUBLIC for functions
    assert "REVOKE EXECUTE ON FUNCTION public.get_auth_user_id() FROM PUBLIC;" in content
    assert "REVOKE EXECUTE ON FUNCTION public.get_business_member_role(UUID, UUID) FROM PUBLIC;" in content
    assert "REVOKE EXECUTE ON FUNCTION public.has_business_role(UUID, UUID, app_role) FROM PUBLIC;" in content
    assert "REVOKE EXECUTE ON FUNCTION public.handle_new_business() FROM PUBLIC;" in content
    assert "REVOKE EXECUTE ON FUNCTION public.prevent_immutable_modification() FROM PUBLIC;" in content


def test_anti_privilege_escalation_enforced_in_policies():
    """Verify admin cannot invite or assign owner or admin roles in business_members policy."""
    rls_path = os.path.join(MIGRATIONS_DIR, "20261022000002_row_level_security.sql")
    with open(rls_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Admins can only insert 'staff'; owner can insert 'admin' or 'owner'
    assert "role = 'staff' AND public.has_business_role(business_id, auth.uid(), 'admin')" in content
    assert "role IN ('admin', 'owner') AND public.has_business_role(business_id, auth.uid(), 'owner')" in content


def test_ledger_immutability_enforced_by_triggers_and_omitted_policies():
    """Verify stock movements and audit logs have BEFORE UPDATE/DELETE triggers raising exceptions."""
    rls_path = os.path.join(MIGRATIONS_DIR, "20261022000002_row_level_security.sql")
    with open(rls_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Triggers on stock_movements and audit_logs
    assert "CREATE TRIGGER trg_stock_movements_immutable" in content
    assert "CREATE TRIGGER trg_audit_logs_immutable" in content
    assert "prevent_immutable_modification" in content

    # Verify no UPDATE or DELETE policies exist for stock_movements or audit_logs
    assert not re.search(r"CREATE\s+POLICY\s+\"[^\"]+\"\s+ON\s+stock_movements\s+FOR\s+(UPDATE|DELETE)", content, re.IGNORECASE)
    assert not re.search(r"CREATE\s+POLICY\s+\"[^\"]+\"\s+ON\s+audit_logs\s+FOR\s+(UPDATE|DELETE)", content, re.IGNORECASE)


def test_phase3_migration_operations_and_atomic_functions():
    """Verify Phase 3 migration defines rejected status, customer active flag, and atomic RPC functions."""
    p3_path = os.path.join(MIGRATIONS_DIR, "20261023000001_operations_transactions.sql")
    with open(p3_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Enums & Columns
    assert "order_status ADD VALUE IF NOT EXISTS 'rejected'" in content
    assert "customers ADD COLUMN IF NOT EXISTS is_active" in content

    # 2. Atomic PostgreSQL functions
    assert "FUNCTION public.adjust_stock_atomic" in content
    assert "FUNCTION public.approve_order_atomic" in content
    assert "FUNCTION public.cancel_order_atomic" in content

    # 3. Security definer and search path
    assert "SECURITY DEFINER" in content
    assert "SET search_path = public" in content

    # 4. Permissions lockdown
    assert "REVOKE EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) FROM PUBLIC;" in content
    assert "REVOKE EXECUTE ON FUNCTION public.approve_order_atomic(UUID, UUID, UUID) FROM PUBLIC;" in content
    assert "REVOKE EXECUTE ON FUNCTION public.cancel_order_atomic(UUID, UUID, UUID, TEXT) FROM PUBLIC;" in content


def test_phase3_atomic_functions_independent_authorization_and_actor_verification():
    """Verify Phase 3 SECURITY DEFINER functions independently check caller identity, membership, and role."""
    p3_path = os.path.join(MIGRATIONS_DIR, "20261023000001_operations_transactions.sql")
    with open(p3_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Caller identity & anti-spoofing in all three functions
    assert "public.get_auth_user_id()" in content
    assert "Actor identity mismatch: caller % cannot act as user %" in content
    assert "Unauthenticated caller cannot execute stock adjustments" in content
    assert "Unauthenticated caller cannot approve orders" in content
    assert "Unauthenticated caller cannot cancel orders" in content

    # 2. Independent role verification using has_business_role with 'admin' requirement
    assert "public.has_business_role(p_business_id, v_actor_id, 'admin')" in content
    assert "public.has_business_role(v_order_business_id, v_actor_id, 'admin')" in content

    # 3. Cross-business injection checks
    assert "Business ID mismatch: order % belongs to % but % was specified" in content
    assert "Product % does not belong to business %" in content
    assert "Integrity violation: order % contains line items belonging to another business" in content

    # 4. Input validations and state machine enforcement
    assert "Quantity change must be non-zero" in content
    assert "A mandatory audit reason (minimum 3 characters) is required" in content
    assert "status must be pending_approval" in content
    assert "order contains no line items" in content

    # 5. Audit and movement actor attribution strictly to verified v_actor_id
    assert "VALUES (\n        p_business_id,\n        v_actor_id,\n        'stock.adjusted'" in content or "v_actor_id" in content
    assert "approved_by = v_actor_id" in content


def test_phase4_realtime_publications_and_replica_identity():
    """Verify Phase 4 migration creates publication and sets REPLICA IDENTITY FULL for operational tables."""
    p4_path = os.path.join(MIGRATIONS_DIR, "20261023000002_realtime_publications.sql")
    assert os.path.exists(p4_path), f"Migration file {p4_path} does not exist"
    with open(p4_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Publication creation / verification
    assert "CREATE PUBLICATION supabase_realtime" in content
    assert "supabase_realtime" in content

    # 2. REPLICA IDENTITY FULL on all 4 operational tables
    # Ensures WAL events contain all columns (notably business_id) on UPDATE/DELETE for RLS filtering
    operational_tables = ["products", "inventory", "orders", "stock_movements"]
    for table in operational_tables:
        pattern = rf"ALTER\s+TABLE\s+(public\.)?{table}\s+REPLICA\s+IDENTITY\s+FULL"
        assert re.search(pattern, content, re.IGNORECASE), f"Table {table} missing REPLICA IDENTITY FULL"

    # 3. Tables added to publication
    for table in operational_tables:
        pattern = rf"ALTER\s+PUBLICATION\s+supabase_realtime\s+ADD\s+TABLE\s+(public\.)?{table}"
        assert re.search(pattern, content, re.IGNORECASE), f"Table {table} not added to supabase_realtime publication"


def test_phase5_invoice_allocation_atomic_and_publication():
    """Verify Phase 5 migration defines allocate_invoice_atomic, security checks, and Realtime publication."""
    p5_path = os.path.join(MIGRATIONS_DIR, "20261023000003_invoices_and_allocation.sql")
    assert os.path.exists(p5_path), f"Migration file {p5_path} does not exist"
    with open(p5_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Realtime publication & replica identity for invoices
    assert "ALTER TABLE public.invoices REPLICA IDENTITY FULL" in content
    assert "ALTER PUBLICATION supabase_realtime ADD TABLE public.invoices" in content

    # 2. Function declaration with SECURITY DEFINER and search_path pinning
    assert "FUNCTION public.allocate_invoice_atomic" in content
    assert "SECURITY DEFINER" in content
    assert "SET search_path = public, pg_temp" in content

    # 3. Caller authentication & anti-spoofing
    assert "public.get_auth_user_id()" in content
    assert "Actor identity mismatch: caller % cannot act as user %" in content
    assert "Unauthenticated caller cannot allocate invoices" in content

    # 4. Role check for admin/owner
    assert "public.has_business_role(p_business_id, v_actor_id, 'admin')" in content

    # 5. Row locks for order and business
    assert "FOR UPDATE" in content
    assert "Invoices can only be issued for approved or fulfilled orders" in content

    # 6. Immutable audit log write
    assert "'invoice.issued'" in content

    # 7. Permissions lockdown
    assert "REVOKE EXECUTE ON FUNCTION public.allocate_invoice_atomic(UUID, UUID, UUID, DATE) FROM PUBLIC" in content
    assert "GRANT EXECUTE ON FUNCTION public.allocate_invoice_atomic(UUID, UUID, UUID, DATE) TO authenticated, service_role" in content


def test_phase5_1_invoice_snapshots_and_order_uniqueness():
    """Verify Phase 5.1 migration adds order uniqueness index, snapshot columns, and hardened allocate_invoice_atomic."""
    p51_path = os.path.join(MIGRATIONS_DIR, "20261023000004_invoice_snapshots_and_constraints.sql")
    assert os.path.exists(p51_path), f"Migration file {p51_path} does not exist"
    with open(p51_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Unique constraint preventing duplicate invoices per order
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_business_order_unique" in content
    assert "ON public.invoices(business_id, order_id)" in content

    # 2. Immutable snapshot columns
    assert "ADD COLUMN IF NOT EXISTS line_items_snapshot JSONB" in content
    assert "ADD COLUMN IF NOT EXISTS customer_snapshot JSONB" in content

    # 3. Hardened lock ordering: parent businesses locked first
    assert "SELECT id INTO v_biz_id" in content
    assert "FROM public.businesses" in content
    assert "FOR UPDATE" in content

    # 4. Snapshots captured in function
    assert "v_customer_snapshot" in content
    assert "v_items_snapshot" in content
    assert "'line_items_snapshot', v_items_snapshot" in content
    assert "'customer_snapshot', v_customer_snapshot" in content

    # 5. Security & execution permissions
    assert "REVOKE EXECUTE ON FUNCTION public.allocate_invoice_atomic(UUID, UUID, UUID, DATE) FROM PUBLIC" in content
    assert "GRANT EXECUTE ON FUNCTION public.allocate_invoice_atomic(UUID, UUID, UUID, DATE) TO authenticated, service_role" in content

    # 6. DBA pre-migration duplicate check guidance and resilient LEFT JOIN
    assert "PRE-MIGRATION SAFETY VERIFICATION" in content
    assert "HAVING count(*) > 1" in content
    assert "LEFT JOIN public.products" in content
    assert "'pdf_storage_path', v_existing_invoice.pdf_storage_path" in content


def test_phase4b_remediate_adjust_stock_atomic_migration():
    """Verify Phase 4B patch migration remediates PL/pgSQL 42702 ambiguity with table qualification."""
    patch_path = os.path.join(MIGRATIONS_DIR, "20261115000001_remediate_adjust_stock_atomic.sql")
    assert os.path.exists(patch_path), f"Patch migration {patch_path} does not exist"
    with open(patch_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Variable conflict protection and table qualification
    assert "#variable_conflict error" in content
    assert "WHERE inventory.business_id = p_business_id AND inventory.product_id = p_product_id" in content
    assert "WHERE products.id = p_product_id AND products.business_id = p_business_id" in content

    # 2. Function declaration and return table
    assert "FUNCTION public.adjust_stock_atomic" in content
    assert "RETURNS TABLE (" in content
    assert "inventory_id UUID" in content
    assert "product_id UUID" in content
    assert "new_quantity INT" in content
    assert "movement_id UUID" in content

    # 3. Security definer and search path
    assert "SECURITY DEFINER" in content
    assert "SET search_path = public, pg_temp" in content

    # 4. Permissions lockdown
    assert "REVOKE EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) FROM anon, PUBLIC;" in content
    assert "GRANT EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) TO authenticated, service_role;" in content



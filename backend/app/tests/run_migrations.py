"""Chronological migration runner for Orqestra disposable local PostgreSQL staging.

Applies all 8 SQL migrations in sequence against the verified disposable database:
1. 20261022000001_core_schema.sql
2. 20261022000002_row_level_security.sql
3. 20261023000001_operations_transactions.sql
4. 20261023000002_realtime_publications.sql
5. 20261023000003_invoices_and_allocation.sql
6. 20261023000004_invoice_snapshots_and_constraints.sql
7. 20261115000001_remediate_adjust_stock_atomic.sql
8. 20261122000001_harden_trigger_function_acls.sql

Features:
- Validates host, database name, and clean state prior to execution.
- Ensures standard Supabase test roles (anon, authenticated, service_role) and auth schema exist.
- Applies each migration within a transactional block.
- Halts immediately upon any failure and reports exact diagnostics without exposing credentials.
- Verifies post-migration schema integrity.
"""

import os
import pathlib
import sys
import time

# Ensure workspace root is in sys.path
workspace_root = str(pathlib.Path(__file__).resolve().parent.parent.parent.parent)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import psycopg
from backend.app.tests import manage_staging_db, test_postgres_staging

MIGRATIONS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent
    / "supabase"
    / "migrations"
)

MIGRATION_SEQUENCE = [
    "20261022000001_core_schema.sql",
    "20261022000002_row_level_security.sql",
    "20261023000001_operations_transactions.sql",
    "20261023000002_realtime_publications.sql",
    "20261023000003_invoices_and_allocation.sql",
    "20261023000004_invoice_snapshots_and_constraints.sql",
    "20261115000001_remediate_adjust_stock_atomic.sql",
    "20261122000001_harden_trigger_function_acls.sql",
]

SUPABASE_AUTH_PREAMBLE = """
-- Supabase Local Testing Environment Prelude
-- Establishes standard Supabase Auth roles and helper functions in disposable PostgreSQL
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
    ELSE
        ALTER ROLE service_role BYPASSRLS;
    END IF;
END $$;

CREATE SCHEMA IF NOT EXISTS auth;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role, postgres;

CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::UUID;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION auth.role() RETURNS TEXT AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.role', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'),
        nullif(nullif(current_setting('role', true), ''), 'none'),
        current_user
    );
$$ LANGUAGE sql STABLE;

GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA auth TO anon, authenticated, service_role, postgres;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;
-- Broad public default routine grant omitted: all routine ACLs must be established strictly by migrations.
"""


def preflight(url: str):
    """Executes mandatory preflight safety checks."""
    test_postgres_staging.validate_safe_test_database(url)
    with psycopg.connect(url, connect_timeout=int(manage_staging_db.DEFAULT_CONNECT_TIMEOUT)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port();")
            db, addr, port = cur.fetchone()
            if db != "orqestra_staging_test":
                raise ValueError(f"Preflight error: Unexpected database '{db}'")
            if str(addr) != "127.0.0.1":
                raise ValueError(f"Preflight error: Unexpected host '{addr}'")
            if port != 5433:
                raise ValueError(f"Preflight error: Unexpected port '{port}'")

            test_postgres_staging.verify_disposable_database_clean(conn)
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
            cnt = cur.fetchone()[0]
            if cnt != 0:
                raise ValueError(f"Preflight error: Database already has {cnt} tables in public schema")

    return {"database": db, "host": str(addr), "port": port}


def apply_migrations():
    """Applies all 7 migrations in topological order."""
    url = manage_staging_db.get_conn_url()
    if not url:
        raise RuntimeError("No staging database connection file found.")

    preflight_info = preflight(url)
    print(f"PREFLIGHT_CONFIRMED: Target {preflight_info['database']} on {preflight_info['host']}:{preflight_info['port']} (0 public tables)")

    results = []

    with psycopg.connect(
        url,
        autocommit=True,
        connect_timeout=int(manage_staging_db.DEFAULT_CONNECT_TIMEOUT),
    ) as conn:
        with conn.cursor() as cur:
            # 1. Apply Supabase Auth preamble if roles/auth schema do not exist
            print("Applying Supabase Auth test environment preamble...")
            cur.execute(SUPABASE_AUTH_PREAMBLE)
            print("Preamble applied successfully.")

            # 2. Apply migrations sequentially
            for m_name in MIGRATION_SEQUENCE:
                m_path = MIGRATIONS_DIR / m_name
                if not m_path.exists():
                    raise FileNotFoundError(f"Migration file not found: {m_path}")

                sql_content = m_path.read_text(encoding="utf-8")
                t0 = time.perf_counter()
                try:
                    cur.execute(sql_content)
                    duration_ms = (time.perf_counter() - t0) * 1000
                    results.append({"migration": m_name, "status": "SUCCESS", "duration_ms": round(duration_ms, 2)})
                    print(f"MIGRATION_OK: {m_name} ({round(duration_ms, 2)} ms)")
                except Exception as e:
                    duration_ms = (time.perf_counter() - t0) * 1000
                    results.append({"migration": m_name, "status": "FAILED", "error": str(e), "duration_ms": round(duration_ms, 2)})
                    print(f"MIGRATION_FAILED: {m_name} - {str(e)}")
                    raise

            # Grant public schema table and sequence permissions to Supabase test roles.
            # Post-migration routine grants are omitted: all routine ACLs must be established strictly by migrations.
            cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;")
            cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;")
            cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;")
            cur.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;")

    return results


def verify_schema():
    """Inspects and verifies the post-migration database schema."""
    url = manage_staging_db.get_conn_url()
    with psycopg.connect(url, connect_timeout=int(manage_staging_db.DEFAULT_CONNECT_TIMEOUT)) as conn:
        with conn.cursor() as cur:
            # 1. Verify tables
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
            tables = [r[0] for r in cur.fetchall()]

            # 2. Verify functions
            cur.execute(
                "SELECT proname FROM pg_proc "
                "WHERE proname IN ('adjust_stock_atomic', 'approve_order_atomic', 'cancel_order_atomic', 'allocate_invoice_atomic', 'has_business_role', 'get_business_member_role') "
                "ORDER BY proname;"
            )
            functions = [r[0] for r in cur.fetchall()]

            # 3. Verify triggers
            cur.execute("SELECT tgname, relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid WHERE NOT tgisinternal ORDER BY tgname;")
            triggers = [{"trigger": r[0], "table": r[1]} for r in cur.fetchall()]

            # 4. Verify unique indexes
            cur.execute(
                "SELECT indexname, tablename FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname IN ('uq_invoices_business_order_unique', 'uq_invoices_business_invoice_number', 'uq_orders_business_order_number') "
                "ORDER BY indexname;"
            )
            indexes = [{"index": r[0], "table": r[1]} for r in cur.fetchall()]

            # 5. Verify RLS enabled on all core tables
            cur.execute("SELECT relname, relrowsecurity FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' ORDER BY relname;")
            rls_status = {r[0]: r[1] for r in cur.fetchall()}

            # 6. Verify publications
            cur.execute("SELECT pubname FROM pg_publication;")
            pubs = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT tablename FROM pg_publication_tables WHERE pubname = 'supabase_realtime';")
            pub_tables = [r[0] for r in cur.fetchall()]

            return {
                "tables": tables,
                "functions": functions,
                "triggers": triggers,
                "indexes": indexes,
                "rls_status": rls_status,
                "publications": pubs,
                "realtime_tables": pub_tables,
            }


if __name__ == "__main__":
    res = apply_migrations()
    print("\n--- SCHEMA VERIFICATION ---")
    schema = verify_schema()
    print(f"Total tables: {len(schema['tables'])} -> {schema['tables']}")
    print(f"Verified functions: {schema['functions']}")
    print(f"Verified indexes: {[i['index'] for i in schema['indexes']]}")
    print(f"Publications: {schema['publications']} (tables: {schema['realtime_tables']})")
    all_rls = all(schema['rls_status'].get(t, False) for t in schema['tables'])
    print(f"RLS enabled on all public tables: {all_rls}")

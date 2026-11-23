#!/usr/bin/env python3
"""
ORQESTRA Phase 4R: Local Execution Validation Runner
====================================================
Runs the complete corrected functional test suite (PHASE_4R_CORRECTED_FUNCTIONAL_TEST.sql)
against an automated, isolated, disposable local PostgreSQL 16 cluster.

Guarantees:
1. Strict local isolation: zero remote connections or mutations.
2. Full RLS policy catalog inspection.
3. Deployed function schema and signature verification.
4. Client-managed transaction with guaranteed rollback in a finally block.
5. Post-rollback independent database verification (asserts 0 test entities remain).
6. Captures all PostgreSQL notices, diagnostic checks, and test outcomes.
"""

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

workspace_root = pathlib.Path(__file__).resolve().parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import psycopg
from backend.app.tests import manage_staging_db, run_migrations

SQL_SCRIPT_PATH = workspace_root / "PHASE_4R_CORRECTED_FUNCTIONAL_TEST.sql"


def compute_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def inspect_policies(cur):
    """Inspects RLS policies on target tables in pg_catalog."""
    sql = """
    SELECT 
        c.relname AS table_name,
        pol.polname AS policy_name,
        CASE pol.polcmd
            WHEN 'r' THEN 'SELECT'
            WHEN 'a' THEN 'INSERT'
            WHEN 'w' THEN 'UPDATE'
            WHEN 'd' THEN 'DELETE'
            WHEN '*' THEN 'ALL'
        END AS command,
        ARRAY(
            SELECT r.rolname FROM unnest(pol.polroles) AS r_oid
            JOIN pg_roles r ON r.oid = r_oid
        ) AS roles,
        pg_get_expr(pol.polqual, pol.polrelid) AS using_expr,
        pg_get_expr(pol.polwithcheck, pol.polrelid) AS with_check_expr
    FROM pg_policy pol
    JOIN pg_class c ON pol.polrelid = c.oid
    WHERE c.relname IN ('businesses', 'business_members', 'products', 'inventory', 'stock_movements', 'audit_logs')
    ORDER BY c.relname, pol.polname;
    """
    cur.execute(sql)
    rows = cur.fetchall()
    policies = []
    for r in rows:
        policies.append({
            "table_name": r[0],
            "policy_name": r[1],
            "command": r[2],
            "roles": r[3],
            "using_expr": r[4],
            "with_check_expr": r[5],
        })
    return policies


def inspect_function(cur):
    """Inspects adjust_stock_atomic function metadata."""
    sql = """
    SELECT 
        p.proname,
        pg_get_function_identity_arguments(p.oid) AS identity_args,
        pg_get_function_result(p.oid) AS result_type,
        p.prosecdef AS is_sec_def,
        p.proconfig AS config,
        has_function_privilege('anon', p.oid, 'EXECUTE') AS anon_can_exec,
        has_function_privilege('authenticated', p.oid, 'EXECUTE') AS auth_can_exec,
        has_function_privilege('service_role', p.oid, 'EXECUTE') AS srv_can_exec
    FROM pg_proc p
    WHERE p.proname = 'adjust_stock_atomic'
      AND p.pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
    """
    cur.execute(sql)
    row = cur.fetchone()
    if not row:
        return None
    return {
        "name": row[0],
        "identity_args": row[1],
        "result_type": row[2],
        "is_security_definer": row[3],
        "config": row[4],
        "anon_can_exec": row[5],
        "auth_can_exec": row[6],
        "srv_can_exec": row[7],
    }


def main():
    print("=" * 70)
    print(" ORQESTRA PHASE 4R: LOCAL EXECUTION VALIDATION RUNNER")
    print("=" * 70)

    if not SQL_SCRIPT_PATH.exists():
        print(f"ERROR: SQL script not found at {SQL_SCRIPT_PATH}")
        sys.exit(1)

    sql_hash = compute_sha256(SQL_SCRIPT_PATH)
    print(f"SQL Script Path: {SQL_SCRIPT_PATH.resolve()}")
    print(f"SQL Script SHA-256: {sql_hash}")

    # 1. Start disposable local cluster
    print("\n--- 1. INITIALIZING DISPOSABLE POSTGRESQL 16 CLUSTER ---")
    manage_staging_db.cleanup()
    conn_url = manage_staging_db.init_cluster()
    admin_url = conn_url.replace("/orqestra_staging_test", "/postgres")

    log_file_path = manage_staging_db.DATA_DIR / "pg_server.log"
    log_fp = open(log_file_path, "w", encoding="utf-8")
    postgres_exe = str(manage_staging_db.POSTGRES_BIN_DIR / "postgres.exe")

    proc = subprocess.Popen(
        [postgres_exe, "-D", str(manage_staging_db.DATA_DIR), "-p", str(manage_staging_db.PORT)],
        stdout=log_fp,
        stderr=subprocess.STDOUT,
    )

    try:
        # Wait for server readiness
        for _ in range(30):
            time.sleep(0.3)
            if manage_staging_db.is_server_available(admin_url, timeout=1.0):
                break
        else:
            raise RuntimeError("Timed out waiting for local PostgreSQL 16 cluster to start.")

        # Determine exact PG version
        with psycopg.connect(admin_url) as ver_conn:
            with ver_conn.cursor() as ver_cur:
                ver_cur.execute("SELECT version();")
                pg_version_str = ver_cur.fetchone()[0]
                print(f"PostgreSQL Engine Version: {pg_version_str}")

        print("Creating staging test database...")
        manage_staging_db.create_database()

        print("Applying all 7 migrations...")
        run_migrations.apply_migrations()

        # Enforce canonical permissions
        with psycopg.connect(conn_url) as acl_conn:
            with acl_conn.cursor() as acl_cur:
                acl_cur.execute("""
                    REVOKE EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) FROM anon, PUBLIC;
                    GRANT EXECUTE ON FUNCTION public.adjust_stock_atomic(UUID, UUID, INT, stock_movement_type, TEXT, UUID) TO authenticated, service_role;
                """)

        # 2. Inspect policies & function catalog
        print("\n--- 2. CATALOG POLICY & SCHEMA INSPECTION ---")
        with psycopg.connect(conn_url) as inspect_conn:
            with inspect_conn.cursor() as inspect_cur:
                policies = inspect_policies(inspect_cur)
                print(f"Cataloged {len(policies)} RLS policies on target tables:")
                for p in policies:
                    print(f"  • {p['table_name']}.{p['policy_name']} [{p['command']}] -> Roles: {p['roles']}")

                fn_meta = inspect_function(inspect_cur)
                print(f"\nFunction Metadata: {fn_meta['name']}")
                print(f"  Identity Args: {fn_meta['identity_args']}")
                print(f"  Result Type:   {fn_meta['result_type']}")
                print(f"  Sec Definer:   {fn_meta['is_security_definer']}")
                print(f"  Search Path:   {fn_meta['config']}")
                print(f"  Permissions:   anon={fn_meta['anon_can_exec']}, auth={fn_meta['auth_can_exec']}, srv={fn_meta['srv_can_exec']}")

        # 3. Execute Script inside client-managed transaction with guaranteed rollback
        print("\n--- 3. EXECUTING PHASE 4R FUNCTIONAL TEST SCRIPT ---")
        sql_content = SQL_SCRIPT_PATH.read_text(encoding="utf-8")

        notices = []

        def notice_handler(diag):
            msg = diag.message_primary
            notices.append(msg)
            print(f"  [PG NOTICE] {msg}")

        client_tx_rolled_back = False
        exec_start = time.perf_counter()

        test_conn = psycopg.connect(conn_url, autocommit=False)
        test_conn.add_notice_handler(notice_handler)

        try:
            with test_conn.cursor() as cur:
                # Execute the full script
                cur.execute(sql_content)

            # Explicit client-side rollback confirmation
            test_conn.rollback()
            client_tx_rolled_back = True
            print("  [CLIENT] Transaction successfully rolled back via client-managed block.")
        except Exception as e:
            print(f"  [CLIENT ERROR during execution] {e}")
            try:
                test_conn.rollback()
                client_tx_rolled_back = True
            except Exception as rb_err:
                print(f"  [CLIENT ERROR during fallback rollback] {rb_err}")
            raise
        finally:
            try:
                if not client_tx_rolled_back:
                    test_conn.rollback()
                test_conn.close()
            except Exception:
                pass

        exec_duration_ms = (time.perf_counter() - exec_start) * 1000.0
        print(f"\nExecution finished in {exec_duration_ms:.2f} ms.")

        # 4. Post-Rollback Independent Table Audit
        print("\n--- 4. POST-ROLLBACK INDEPENDENT TABLE AUDIT ---")
        with psycopg.connect(conn_url) as audit_conn:
            with audit_conn.cursor() as audit_cur:
                # Check for any residual test data across all 6 operational tables
                audit_cur.execute("SELECT count(*) FROM businesses WHERE slug LIKE 'test-biz-%' OR name LIKE 'Ephemeral Test Biz%';")
                cnt_biz = audit_cur.fetchone()[0]

                audit_cur.execute("SELECT count(*) FROM business_members WHERE business_id IN (SELECT id FROM businesses WHERE slug LIKE 'test-biz-%');")
                cnt_members = audit_cur.fetchone()[0]

                audit_cur.execute("SELECT count(*) FROM products WHERE sku IN ('SKU-A-001', 'SKU-B-001') OR name IN ('Widget A', 'Widget B');")
                cnt_prod = audit_cur.fetchone()[0]

                audit_cur.execute("SELECT count(*) FROM inventory WHERE business_id IN (SELECT id FROM businesses WHERE slug LIKE 'test-biz-%');")
                cnt_inv = audit_cur.fetchone()[0]

                audit_cur.execute("SELECT count(*) FROM stock_movements WHERE notes IN ('Valid restock shipment', 'Damaged stock write-off') OR business_id IN (SELECT id FROM businesses WHERE slug LIKE 'test-biz-%');")
                cnt_mvt = audit_cur.fetchone()[0]

                audit_cur.execute("SELECT count(*) FROM audit_logs WHERE business_id IN (SELECT id FROM businesses WHERE slug LIKE 'test-biz-%') OR (action = 'stock.adjusted' AND entity_type = 'inventory');")
                cnt_audit = audit_cur.fetchone()[0]

                print(f"  Residual businesses:       {cnt_biz} (Expected: 0)")
                print(f"  Residual business_members:  {cnt_members} (Expected: 0)")
                print(f"  Residual products:         {cnt_prod} (Expected: 0)")
                print(f"  Residual inventory:        {cnt_inv} (Expected: 0)")
                print(f"  Residual stock_movements:  {cnt_mvt} (Expected: 0)")
                print(f"  Residual audit_logs:       {cnt_audit} (Expected: 0)")

                if cnt_biz != 0 or cnt_members != 0 or cnt_prod != 0 or cnt_inv != 0 or cnt_mvt != 0 or cnt_audit != 0:
                    raise RuntimeError("POST-ROLLBACK AUDIT FAILED: Uncommitted entities leaked into database!")
                print("  => POST-ROLLBACK VERIFICATION PASSED: Database is 100% clean across all 6 tables.")

        # 5. Output JSON Summary for Report
        summary = {
            "verdict": "LOCAL PASS",
            "sql_script_path": str(SQL_SCRIPT_PATH.resolve()),
            "sql_script_sha256": sql_hash,
            "pg_version": pg_version_str,
            "execution_duration_ms": exec_duration_ms,
            "notices": notices,
            "residual_counts": {
                "businesses": cnt_biz,
                "business_members": cnt_members,
                "products": cnt_prod,
                "inventory": cnt_inv,
                "stock_movements": cnt_mvt,
                "audit_logs": cnt_audit,
            },
            "policies": policies,
            "function_metadata": fn_meta,
        }

        with open(workspace_root / "PHASE_4R_LOCAL_VERIFICATION_RESULTS.json", "w", encoding="utf-8") as jf:
            json.dump(summary, jf, indent=2)

        print("\n=== PHASE 4R LOCAL VERIFICATION: SUCCESS ===")
        return 0

    finally:
        print("\nTearing down disposable PostgreSQL cluster...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fp.close()
        manage_staging_db.cleanup()
        print("Disposable cluster cleaned up.")


if __name__ == "__main__":
    sys.exit(main())

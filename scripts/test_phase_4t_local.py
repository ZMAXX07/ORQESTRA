#!/usr/bin/env python3
"""
ORQESTRA Phase 4T-C: Hardened Local Test Runner & Exact-ID Cleanup Audit
=======================================================================
Executes PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql against disposable local PostgreSQL 16.
Validates:
1. Artifact integrity against approved hash manifest (fails on mismatch).
2. Clean migration execution without permission-repair contamination.
3. Pure catalog assertion of function ACL (anon/PUBLIC revoked, auth/service granted,
   SECURITY DEFINER, search_path).
4. Fixture schema and foreign key verification (confirms auth.users FK absence and triggers).
5. Strict manifest validation: exactly 1 notice, valid JSON, 13 distinct UUIDs, no malformed types.
6. Explicit verification of success notices for all 8 scenarios.
7. Guaranteed transaction rollback with robust failure reporting.
8. Independent exact-ID post-rollback absence audit across all 6 operational tables.
"""

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import uuid

workspace_root = pathlib.Path(__file__).resolve().parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import psycopg
from backend.app.tests import manage_staging_db, run_migrations

SQL_SCRIPT_PATH = workspace_root / "PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql"
HASH_MANIFEST_PATH = workspace_root / "PHASE_4T_APPROVED_HASHES.json"
RESULTS_JSON_PATH = workspace_root / "PHASE_4T_LOCAL_VERIFICATION_RESULTS.json"

EXPECTED_SCENARIO_NOTICES = [
    "TEST 1 PASSED: Authorized restock (+10 -> 30) verified across inventory, movements, and audit_logs",
    "TEST 2 PASSED: Authorized deduction (-5 -> 25) verified across inventory, movements, and audit_logs",
    "TEST 3 PASSED: Zero quantity rejected with SQLSTATE P0001; zero state mutation",
    "TEST 4 PASSED: Overdraft rejected with SQLSTATE P0001; inventory unchanged at 25",
    "TEST 5 PASSED: Actor identity mismatch caught with SQLSTATE P0001",
    "TEST 6 PASSED: Staff role unauthorized execution rejected with SQLSTATE P0001",
    "TEST 7 PASSED: Cross-tenant product mismatch caught with SQLSTATE P0001",
    "TEST 8 PASSED: Unauthorized business access caught with SQLSTATE P0001; zero state mutation",
]

REQUIRED_MANIFEST_KEYS = [
    "biz_a", "biz_b", "admin_a", "admin_b", "staff_a",
    "prod_a", "prod_b", "inv_a", "inv_b", "mvt_1", "mvt_2",
    "audit_1", "audit_2"
]

REQUIRED_MANIFEST_ARTIFACTS = [
    "PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql",
    "test_phase_4t_local.py",
    "run_migrations.py",
]

SENSITIVE_ROUTINE_SIGNATURES = {
    "adjust_stock_atomic(p_business_id uuid, p_product_id uuid, p_quantity_change integer, p_movement_type stock_movement_type, p_notes text, p_user_id uuid)",
    "allocate_invoice_atomic(p_business_id uuid, p_order_id uuid, p_user_id uuid, p_due_date date)",
    "approve_order_atomic(p_order_id uuid, p_user_id uuid, p_business_id uuid)",
    "cancel_order_atomic(p_order_id uuid, p_user_id uuid, p_business_id uuid, p_reason text)",
    "get_auth_user_id()",
    "get_business_member_role(_business_id uuid, _user_id uuid)",
    "handle_new_business()",
    "has_business_role(_business_id uuid, _user_id uuid, _required_role app_role)",
    "prevent_immutable_modification()",
    "set_updated_at_timestamp()",
}

EXACT_PUBLIC_EXECUTE_ALLOWLIST = {}


def compute_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def verify_artifact_integrity(sql_path: pathlib.Path, runner_path: pathlib.Path) -> dict[str, str]:
    print("\n--- 0. ARTIFACT INTEGRITY VERIFICATION ---")
    if not HASH_MANIFEST_PATH.exists():
        raise RuntimeError(
            f"HASH MANIFEST MISSING: Approved hash manifest not found at {HASH_MANIFEST_PATH}."
        )

    try:
        manifest_data = json.loads(HASH_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"HASH MANIFEST CORRUPT: Could not parse JSON from {HASH_MANIFEST_PATH}: {e}")

    # Task 3: Fail-closed manifest key validation
    missing_manifest_keys = [k for k in REQUIRED_MANIFEST_ARTIFACTS if k not in manifest_data]
    if missing_manifest_keys:
        raise RuntimeError(
            f"HASH MANIFEST INCOMPLETE: Missing required artifact keys in manifest: {missing_manifest_keys}"
        )

    # Validate 64-character lowercase hex SHA-256 formatting for each required key
    hex_pattern = re.compile(r"^[0-9a-f]{64}$")
    for k in REQUIRED_MANIFEST_ARTIFACTS:
        val = str(manifest_data[k]).strip().lower()
        if not hex_pattern.match(val):
            raise RuntimeError(
                f"HASH MANIFEST INVALID: Key '{k}' contains malformed SHA-256 value '{val}'. Expected 64-char hex."
            )

    sql_hash = compute_sha256(sql_path)
    runner_hash = compute_sha256(runner_path)
    run_mig_path = workspace_root / "backend" / "app" / "tests" / "run_migrations.py"
    run_mig_hash = compute_sha256(run_mig_path)

    expected_sql = manifest_data["PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql"].lower()
    expected_runner = manifest_data["test_phase_4t_local.py"].lower()
    expected_run_mig = manifest_data["run_migrations.py"].lower()

    print(f"  SQL Script:        {sql_path.name}")
    print(f"  SQL Actual Hash:   {sql_hash}")
    print(f"  SQL Expected Hash: {expected_sql}")
    print(f"  Runner:            {runner_path.name}")
    print(f"  Runner Actual Hash:{runner_hash}")
    print(f"  Runner Expected:   {expected_runner}")
    print(f"  run_migrations.py: {run_mig_path.name}")
    print(f"  run_mig Actual:    {run_mig_hash}")
    print(f"  run_mig Expected:  {expected_run_mig}")

    mismatches = []
    if sql_hash != expected_sql:
        mismatches.append(f"SQL Script hash mismatch! Expected: {expected_sql}, Got: {sql_hash}")
    if runner_hash != expected_runner:
        mismatches.append(f"Runner hash mismatch! Expected: {expected_runner}, Got: {runner_hash}")
    if run_mig_hash != expected_run_mig:
        mismatches.append(f"run_migrations.py hash mismatch! Expected: {expected_run_mig}, Got: {run_mig_hash}")

    if mismatches:
        raise RuntimeError(
            "ARTIFACT INTEGRITY CHECK FAILED:\n" + "\n".join(mismatches) +
            "\nExecution aborted. Do not automatically update expected hashes."
        )

    print("  => ARTIFACT INTEGRITY PASS: All approved file hashes verified unconditionally.")
    return {"sql_hash": sql_hash, "runner_hash": runner_hash, "run_migrations_hash": run_mig_hash}


def validate_manifest(manifest_notices: list[str]) -> dict[str, str]:
    if len(manifest_notices) != 1:
        raise RuntimeError(
            f"MANIFEST VALIDATION FAILED: Expected exactly 1 MANIFEST_JSON notice, got {len(manifest_notices)}"
        )

    notice = manifest_notices[0]
    raw_json = notice[len("MANIFEST_JSON:"):].strip()
    try:
        data = json.loads(raw_json)
    except Exception as e:
        raise RuntimeError(f"MANIFEST VALIDATION FAILED: Malformed JSON in manifest notice: {e}")

    if not isinstance(data, dict):
        raise RuntimeError(f"MANIFEST VALIDATION FAILED: Manifest root must be a JSON object, got {type(data)}")

    missing = set(REQUIRED_MANIFEST_KEYS) - set(data.keys())
    if missing:
        raise RuntimeError(f"MANIFEST VALIDATION FAILED: Missing required keys: {sorted(missing)}")

    unexpected = set(data.keys()) - set(REQUIRED_MANIFEST_KEYS)
    if unexpected:
        raise RuntimeError(f"MANIFEST VALIDATION FAILED: Unexpected keys in manifest: {sorted(unexpected)}")

    validated = {}
    for k in REQUIRED_MANIFEST_KEYS:
        v = data[k]
        if not isinstance(v, str) or not v.strip():
            raise RuntimeError(f"MANIFEST VALIDATION FAILED: Key '{k}' must be non-empty string, got {v!r}")
        try:
            u = uuid.UUID(v.strip())
            validated[k] = str(u).lower()
        except ValueError as ve:
            raise RuntimeError(f"MANIFEST VALIDATION FAILED: Key '{k}' contains invalid UUID '{v}': {ve}")

    # Check distinctness: all 13 fixture UUIDs represent separate entities
    unique_uuids = set(validated.values())
    if len(unique_uuids) != len(validated):
        seen = {}
        duplicates = []
        for k, v in validated.items():
            if v in seen:
                duplicates.append(f"'{k}' duplicates '{seen[v]}' ({v})")
            else:
                seen[v] = k
        raise RuntimeError(f"MANIFEST VALIDATION FAILED: Duplicate UUIDs detected: {', '.join(duplicates)}")

    return validated


def verify_scenario_notices(notices: list[str]) -> dict[str, bool]:
    results = {}
    for idx, expected in enumerate(EXPECTED_SCENARIO_NOTICES, 1):
        found = any(expected in n for n in notices)
        results[f"scenario_{idx}"] = found
        if not found:
            raise RuntimeError(f"SCENARIO VERIFICATION FAILED: Expected notice for Scenario {idx} not found: '{expected}'")
    return results


def main():
    print("=" * 70)
    print(" ORQESTRA PHASE 4T-F: FINAL PRIVILEGE HARDENING & LOCAL VERIFICATION")
    print("=" * 70)

    if not SQL_SCRIPT_PATH.exists():
        print(f"ERROR: SQL script not found at {SQL_SCRIPT_PATH}")
        sys.exit(1)

    runner_path = pathlib.Path(__file__).resolve()

    # Task 6: Pin artifact integrity before execution
    hashes = verify_artifact_integrity(SQL_SCRIPT_PATH, runner_path)
    sql_hash = hashes["sql_hash"]
    runner_hash = hashes["runner_hash"]

    # Initialize disposable local cluster
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

        with psycopg.connect(admin_url) as ver_conn:
            with ver_conn.cursor() as ver_cur:
                ver_cur.execute("SELECT version();")
                pg_version_str = ver_cur.fetchone()[0]
                print(f"PostgreSQL Engine Version: {pg_version_str}")

        print("Creating staging test database...")
        manage_staging_db.create_database()

        print("Applying all 8 migrations...")
        run_migrations.apply_migrations()

        # Task 1: Inspect actual function ACL established strictly by migration
        # NO manual REVOKE or GRANT statements allowed.
        print("\n--- 2. VERIFYING FUNCTION ACL & CONFIGURATION FROM MIGRATION ---")
        with psycopg.connect(conn_url) as acl_conn:
            with acl_conn.cursor() as acl_cur:
                acl_cur.execute("""
                    SELECT 
                        p.prosecdef,
                        p.proconfig,
                        has_function_privilege('anon', p.oid, 'EXECUTE') AS anon_can_exec,
                        has_function_privilege('authenticated', p.oid, 'EXECUTE') AS auth_can_exec,
                        has_function_privilege('service_role', p.oid, 'EXECUTE') AS service_can_exec,
                        coalesce(array_to_string(p.proacl, ','), '') AS proacl_str
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public' AND p.proname = 'adjust_stock_atomic';
                """)
                row = acl_cur.fetchone()
                if not row:
                    raise RuntimeError("ACL VERIFICATION FAILED: Function public.adjust_stock_atomic does not exist.")

                is_sec_def, proconfig, anon_exec, auth_exec, service_exec, proacl_str = row
                print(f"  SECURITY DEFINER:    {is_sec_def} (Expected: True)")
                print(f"  proconfig:           {proconfig} (Expected: ['search_path=public, pg_temp'])")
                print(f"  anon can EXECUTE:    {anon_exec} (Expected: False)")
                print(f"  auth can EXECUTE:    {auth_exec} (Expected: True)")
                print(f"  service can EXECUTE: {service_exec} (Expected: True)")
                print(f"  proacl entries:      {proacl_str}")

                if not is_sec_def:
                    raise RuntimeError("ACL VERIFICATION FAILED: Function is not SECURITY DEFINER.")

                expected_search_path = "search_path=public, pg_temp"
                if not proconfig or expected_search_path not in proconfig:
                    raise RuntimeError(
                        f"ACL VERIFICATION FAILED: search_path mismatch. Expected {expected_search_path!r}, got {proconfig!r}"
                    )

                if anon_exec:
                    raise RuntimeError("ACL VERIFICATION FAILED: Role 'anon' has EXECUTE privilege.")

                if not auth_exec:
                    raise RuntimeError("ACL VERIFICATION FAILED: Role 'authenticated' lacks EXECUTE privilege.")

                if not service_exec:
                    raise RuntimeError("ACL VERIFICATION FAILED: Role 'service_role' lacks EXECUTE privilege.")

                # Assert PUBLIC cannot execute
                acl_entries = [entry.strip() for entry in proacl_str.split(",") if entry.strip()]
                for entry in acl_entries:
                    grantee = entry.split("=")[0]
                    privs = entry.split("=")[1].split("/")[0] if "=" in entry else ""
                    if (grantee == "" or grantee.lower() == "public") and "X" in privs:
                        raise RuntimeError(f"ACL VERIFICATION FAILED: PUBLIC has EXECUTE privilege in proacl: {entry}")

                print("  => MIGRATION ACL VERIFICATION PASS: Canonical permissions verified without test repair.")

                # Phase 4T-F: Comprehensive Routine ACL Audit with Canonical aclexplode and Empty Allowlist
                print("\n  Auditing all public routines for anon/PUBLIC EXECUTE privileges...")
                acl_cur.execute("""
                    SELECT 
                        p.oid,
                        p.proname,
                        pg_get_function_identity_arguments(p.oid) AS args,
                        p.oid::regprocedure::text AS full_signature,
                        has_function_privilege('anon', p.oid, 'EXECUTE') AS anon_can_exec,
                        has_function_privilege('authenticated', p.oid, 'EXECUTE') AS auth_can_exec,
                        has_function_privilege('service_role', p.oid, 'EXECUTE') AS service_can_exec,
                        (
                            CASE 
                                WHEN p.proacl IS NULL THEN true
                                ELSE EXISTS (
                                    SELECT 1 FROM aclexplode(p.proacl) acl
                                    WHERE acl.grantee = 0 AND acl.privilege_type = 'EXECUTE'
                                )
                            END
                        ) AS public_has_grant,
                        coalesce(array_to_string(p.proacl, ','), '') AS proacl_str
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                    ORDER BY p.proname;
                """)
                routine_audit = []
                verified_sensitive_signatures = set()

                for r_oid, r_name, r_args, r_full_sig, r_anon, r_auth, r_service, r_public_grant, r_proacl in acl_cur.fetchall():
                    sig = f"{r_name}({r_args})"
                    print(f"    - [{r_oid}] {r_full_sig}: anon={r_anon}, auth={r_auth}, service={r_service}, public_grant={r_public_grant}")

                    # 1. Strict assertions for sensitive business routines
                    if sig in SENSITIVE_ROUTINE_SIGNATURES:
                        if r_anon:
                            raise RuntimeError(f"ACL AUDIT FAILED: Sensitive routine '{sig}' permits anon EXECUTE!")
                        if r_public_grant:
                            raise RuntimeError(f"ACL AUDIT FAILED: Sensitive routine '{sig}' permits PUBLIC EXECUTE in proacl!")
                        if not r_auth:
                            raise RuntimeError(f"ACL AUDIT FAILED: Sensitive routine '{sig}' lacks authenticated EXECUTE!")
                        if not r_service:
                            raise RuntimeError(f"ACL AUDIT FAILED: Sensitive routine '{sig}' lacks service_role EXECUTE!")
                        verified_sensitive_signatures.add(sig)

                    # 2. Fail-closed check: Any routine executable by anon or PUBLIC must be explicitly allowlisted
                    if r_anon or r_public_grant:
                        if sig not in EXACT_PUBLIC_EXECUTE_ALLOWLIST:
                            raise RuntimeError(
                                f"ACL AUDIT FAILED: Unexpected routine '{sig}' ({r_full_sig}) is executable by anon/PUBLIC without allowlist entry!"
                            )
                        allow_entry = EXACT_PUBLIC_EXECUTE_ALLOWLIST[sig]
                        if r_anon and not allow_entry.get("allow_anon", False):
                            raise RuntimeError(f"ACL AUDIT FAILED: Routine '{sig}' permits anon EXECUTE beyond allowlist scope!")
                        if r_public_grant and not allow_entry.get("allow_public", False):
                            raise RuntimeError(f"ACL AUDIT FAILED: Routine '{sig}' permits PUBLIC EXECUTE beyond allowlist scope!")

                    routine_audit.append({
                        "oid": r_oid,
                        "signature": sig,
                        "full_signature": r_full_sig,
                        "name": r_name,
                        "args": r_args,
                        "anon_can_execute": r_anon,
                        "authenticated_can_execute": r_auth,
                        "service_role_can_execute": r_service,
                        "public_has_grant": r_public_grant,
                        "proacl": r_proacl
                    })

                # Assert that all declared sensitive routines were found in the catalog
                missing_sensitive = SENSITIVE_ROUTINE_SIGNATURES - verified_sensitive_signatures
                if missing_sensitive:
                    raise RuntimeError(
                        f"ACL AUDIT FAILED: Declared sensitive routines missing from catalog: {missing_sensitive}"
                    )

                print(f"  => ROUTINE ACL AUDIT PASS: All {len(routine_audit)} public routines verified. 10 sensitive routines strictly restricted; zero allowlist exceptions.")

        # Task 2: Verify fixture foreign-key compatibility & schema structure
        print("\n--- 3. VERIFYING FIXTURE FOREIGN-KEY & TRIGGER COMPATIBILITY ---")
        with psycopg.connect(conn_url) as fk_conn:
            with fk_conn.cursor() as fk_cur:
                # Check all foreign keys in public schema
                fk_cur.execute("""
                    SELECT 
                        tc.table_name, 
                        kcu.column_name, 
                        ccu.table_schema AS foreign_table_schema,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name,
                        tc.constraint_name
                    FROM information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
                    ORDER BY tc.table_name, kcu.column_name;
                """)
                fk_rows = fk_cur.fetchall()
                print("  Discovered Foreign Keys in public schema:")
                for r in fk_rows:
                    print(f"    - {r[0]}.{r[1]} -> {r[2]}.{r[3]}({r[4]}) [{r[5]}]")

                # Verify business_members.user_id has NO foreign key to auth.users
                bm_user_fks = [r for r in fk_rows if r[0] == 'business_members' and r[1] == 'user_id']
                if bm_user_fks:
                    raise RuntimeError(f"FK VERIFICATION FAILED: Unexpected FK on business_members.user_id: {bm_user_fks}")
                print("  - business_members.user_id has NO foreign key to auth.users: Confirmed (Matches Migration 1 DDL design).")

                # Phase 4T-E Task 5: Verify all critical schema triggers explicitly
                fk_cur.execute("""
                    SELECT 
                        trigger_name, 
                        event_object_table, 
                        action_timing, 
                        event_manipulation, 
                        action_statement
                    FROM information_schema.triggers
                    WHERE event_object_schema = 'public'
                    ORDER BY event_object_table, trigger_name;
                """)
                trg_rows = fk_cur.fetchall()
                print("  Discovered Triggers in public schema:")
                for trg in trg_rows:
                    print(f"    - {trg[1]}.{trg[0]} [{trg[2]} {trg[3]}]: {trg[4]}")

                # Assert specific critical triggers
                required_triggers = [
                    ("trg_on_business_created", "businesses", "AFTER", "INSERT", "handle_new_business"),
                    ("trg_businesses_updated_at", "businesses", "BEFORE", "UPDATE", "set_updated_at_timestamp"),
                    ("trg_stock_movements_immutable", "stock_movements", "BEFORE", "UPDATE", "prevent_immutable_modification"),
                    ("trg_audit_logs_immutable", "audit_logs", "BEFORE", "UPDATE", "prevent_immutable_modification"),
                ]
                verified_triggers = []
                for req_name, req_tbl, req_timing, req_event, req_fn in required_triggers:
                    matched = [
                        t for t in trg_rows 
                        if t[0] == req_name 
                        and t[1] == req_tbl 
                        and t[2] == req_timing 
                        and req_event in t[3] 
                        and req_fn in t[4]
                    ]
                    if not matched:
                        raise RuntimeError(
                            f"TRIGGER VERIFICATION FAILED: Expected trigger '{req_name}' on '{req_tbl}' "
                            f"({req_timing} {req_event} -> {req_fn}) not found in catalog!"
                        )
                    verified_triggers.append(req_name)
                    print(f"  - Trigger '{req_name}' on '{req_tbl}' ({req_timing} {req_event} -> {req_fn}): Confirmed.")

        # Tasks 4 & 5: Execute Script inside client-managed transaction with guaranteed rollback
        print("\n--- 4. EXECUTING PHASE 4T HARDENED FUNCTIONAL TEST SCRIPT ---")
        sql_content = SQL_SCRIPT_PATH.read_text(encoding="utf-8")

        notices = []
        manifest_notices = []

        def notice_handler(diag):
            msg = diag.message_primary
            notices.append(msg)
            if msg.startswith("MANIFEST_JSON:"):
                manifest_notices.append(msg)
            else:
                print(f"  [PG NOTICE] {msg}")

        client_tx_rolled_back = False
        exec_start = time.perf_counter()

        # Connect with autocommit=True so BEGIN; ... ROLLBACK; inside SQL controls the transaction boundary directly without psycopg auto-begin warning
        test_conn = psycopg.connect(conn_url, autocommit=True)
        test_conn.add_notice_handler(notice_handler)

        try:
            with test_conn.cursor() as cur:
                cur.execute(sql_content)

            client_tx_rolled_back = True
            print("  [CLIENT] Transaction successfully completed and rolled back via script-managed block.")
        except Exception as exec_err:
            print(f"  [CLIENT ERROR during execution] {exec_err}")
            try:
                # Issue emergency rollback in case script execution failed mid-flight before ROLLBACK
                with test_conn.cursor() as rb_cur:
                    rb_cur.execute("ROLLBACK;")
                client_tx_rolled_back = True
                print("  [CLIENT] Emergency fallback rollback executed after execution error.")
            except Exception as rb_err:
                print(f"  [FATAL ERROR during fallback rollback] {rb_err}")
                raise RuntimeError(f"Rollback failed after execution error: {rb_err}") from exec_err
            raise
        finally:
            try:
                test_conn.close()
            except Exception as close_err:
                print(f"  [WARNING during test_conn close] {close_err}")

        exec_duration_ms = (time.perf_counter() - exec_start) * 1000.0
        print(f"\nExecution finished in {exec_duration_ms:.2f} ms.")

        # Task 4: Verify all 8 scenario success notices
        print("\n--- 5. VERIFYING SCENARIO SUCCESS NOTICES ---")
        scenario_results = verify_scenario_notices(notices)
        for sc, res in scenario_results.items():
            print(f"  {sc.upper()}: {'PASSED' if res else 'MISSING'}")
        print("  => ALL 8 SCENARIO SUCCESS NOTICES CONFIRMED.")

        # Task 3: Harden manifest validation
        print("\n--- 6. VALIDATING EXACT FIXTURE MANIFEST ---")
        validated_manifest = validate_manifest(manifest_notices)
        for k, v in validated_manifest.items():
            print(f"  {k}: {v}")
        print(f"  => MANIFEST VALIDATION PASS: All {len(validated_manifest)} keys present, valid UUIDs, and distinct.")

        # Task 4 & 5: Post-Rollback Independent Table Audit using EXACT UUIDs across 6 tables
        print("\n--- 7. POST-ROLLBACK INDEPENDENT TABLE AUDIT & RLS PRIVILEGE VERIFICATION ---")
        audit_conn = None
        try:
            audit_conn = psycopg.connect(conn_url)
            with audit_conn.cursor() as cur:
                # 0. Task 4: Inspect cleanup connection role and RLS bypass attributes
                cur.execute("""
                    SELECT 
                        current_user,
                        session_user,
                        r.rolsuper,
                        r.rolbypassrls
                    FROM pg_roles r
                    WHERE r.rolname = current_user;
                """)
                audit_role_row = cur.fetchone()
                if not audit_role_row:
                    raise RuntimeError("CLEANUP AUDIT FAILED: Could not inspect audit connection role.")

                audit_user, audit_sess_user, is_super, has_bypassrls = audit_role_row
                print(f"  Audit Connection current_user: {audit_user}")
                print(f"  Audit Connection session_user: {audit_sess_user}")
                print(f"  Audit Role rolsuper:           {is_super}")
                print(f"  Audit Role rolbypassrls:       {has_bypassrls}")

                if audit_user in ('anon', 'authenticated'):
                    raise RuntimeError(f"CLEANUP AUDIT INSECURE: Audit connection runs as application role '{audit_user}'.")

                if not (is_super or has_bypassrls):
                    raise RuntimeError("CLEANUP AUDIT INSECURE: Audit role lacks superuser or BYPASSRLS privileges.")

                # Verify table ownership of all 6 operational tables
                cur.execute("""
                    SELECT tablename, tableowner 
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                      AND tablename IN ('businesses', 'business_members', 'products', 'inventory', 'stock_movements', 'audit_logs')
                    ORDER BY tablename;
                """)
                tbl_owners = cur.fetchall()
                print("  Operational Table Ownership:")
                for tbl, owner in tbl_owners:
                    print(f"    - {tbl}: owned by '{owner}'")
                    if owner != audit_user and not (is_super or has_bypassrls):
                        raise RuntimeError(f"CLEANUP AUDIT INSECURE: Audit role '{audit_user}' does not own '{tbl}' and lacks bypassrls.")

                print("  => CLEANUP CONNECTION PRIVILEGES VERIFIED: Full RLS bypass and table visibility confirmed.")

                # 1. Businesses by exact UUID
                cur.execute(
                    "SELECT count(*) FROM businesses WHERE id IN (%s, %s);",
                    (validated_manifest['biz_a'], validated_manifest['biz_b'])
                )
                cnt_biz = cur.fetchone()[0]

                # 2. Business Members by exact composite keys and exact UUIDs
                cur.execute("""
                    SELECT count(*) FROM business_members 
                    WHERE (business_id = %s AND user_id = %s)
                       OR (business_id = %s AND user_id = %s)
                       OR (business_id = %s AND user_id = %s)
                       OR business_id IN (%s, %s)
                       OR user_id IN (%s, %s, %s);
                """, (
                    validated_manifest['biz_a'], validated_manifest['admin_a'],
                    validated_manifest['biz_a'], validated_manifest['staff_a'],
                    validated_manifest['biz_b'], validated_manifest['admin_b'],
                    validated_manifest['biz_a'], validated_manifest['biz_b'],
                    validated_manifest['admin_a'], validated_manifest['admin_b'], validated_manifest['staff_a']
                ))
                cnt_members = cur.fetchone()[0]

                # 3. Products by exact UUID and business_id
                cur.execute(
                    "SELECT count(*) FROM products WHERE id IN (%s, %s) OR business_id IN (%s, %s);", 
                    (validated_manifest['prod_a'], validated_manifest['prod_b'],
                     validated_manifest['biz_a'], validated_manifest['biz_b'])
                )
                cnt_prod = cur.fetchone()[0]

                # 4. Inventory by exact UUID and product_id
                cur.execute(
                    "SELECT count(*) FROM inventory WHERE id IN (%s, %s) OR business_id IN (%s, %s) OR product_id IN (%s, %s);",
                    (validated_manifest['inv_a'], validated_manifest['inv_b'],
                     validated_manifest['biz_a'], validated_manifest['biz_b'],
                     validated_manifest['prod_a'], validated_manifest['prod_b'])
                )
                cnt_inv = cur.fetchone()[0]

                # 5. Stock Movements by exact movement_id, product_id, and business_id
                cur.execute(
                    "SELECT count(*) FROM stock_movements WHERE id IN (%s, %s) OR business_id IN (%s, %s) OR product_id IN (%s, %s);",
                    (validated_manifest['mvt_1'], validated_manifest['mvt_2'],
                     validated_manifest['biz_a'], validated_manifest['biz_b'],
                     validated_manifest['prod_a'], validated_manifest['prod_b'])
                )
                cnt_mvt = cur.fetchone()[0]

                # 6. Audit Logs by exact audit_id, business_id, and entity_id
                cur.execute(
                    "SELECT count(*) FROM audit_logs WHERE id IN (%s, %s) OR business_id IN (%s, %s) OR entity_id IN (%s, %s);",
                    (validated_manifest['audit_1'], validated_manifest['audit_2'],
                     validated_manifest['biz_a'], validated_manifest['biz_b'],
                     validated_manifest['inv_a'], validated_manifest['inv_b'])
                )
                cnt_audit = cur.fetchone()[0]

                print(f"  Exact businesses count:        {cnt_biz} (Expected: 0)")
                print(f"  Exact business_members count:  {cnt_members} (Expected: 0)")
                print(f"  Exact products count:          {cnt_prod} (Expected: 0)")
                print(f"  Exact inventory count:         {cnt_inv} (Expected: 0)")
                print(f"  Exact stock_movements count:   {cnt_mvt} (Expected: 0)")
                print(f"  Exact audit_logs count:        {cnt_audit} (Expected: 0)")

                if any([cnt_biz, cnt_members, cnt_prod, cnt_inv, cnt_mvt, cnt_audit]):
                    raise RuntimeError("EXACT-ID AUDIT FAILED: Uncommitted test entities survived rollback!")
                print("  => EXACT-ID POST-ROLLBACK VERIFICATION PASSED: All 6 tables verified 100% clean.")
        except Exception as audit_err:
            print(f"  [FATAL ERROR during cleanup audit] {audit_err}")
            raise RuntimeError(f"CLEANUP VERIFICATION INDETERMINATE OR FAILED: {audit_err}") from audit_err
        finally:
            if audit_conn and not audit_conn.closed:
                audit_conn.close()

        # Output JSON Summary
        summary = {
            "verdict": "LOCAL PASS",
            "phase": "PHASE_4T_F",
            "sql_script_path": str(SQL_SCRIPT_PATH.resolve()),
            "sql_script_sha256": sql_hash,
            "runner_path": str(runner_path),
            "runner_sha256": runner_hash,
            "pg_version": pg_version_str,
            "execution_duration_ms": exec_duration_ms,
            "acl_verification": {
                "security_definer": is_sec_def,
                "search_path": proconfig,
                "anon_can_execute": anon_exec,
                "authenticated_can_execute": auth_exec,
                "service_role_can_execute": service_exec,
                "proacl": proacl_str
            },
            "routine_acl_audit": routine_audit,
            "fk_verification": {
                "business_members_user_id_has_fk_to_auth": False,
                "triggers_verified": verified_triggers
            },
            "audit_connection_privileges": {
                "current_user": audit_user,
                "session_user": audit_sess_user,
                "rolsuper": is_super,
                "rolbypassrls": has_bypassrls,
                "table_owners": {tbl: owner for tbl, owner in tbl_owners}
            },
            "scenario_results": scenario_results,
            "manifest": validated_manifest,
            "exact_id_counts": {
                "businesses": cnt_biz,
                "business_members": cnt_members,
                "products": cnt_prod,
                "inventory": cnt_inv,
                "stock_movements": cnt_mvt,
                "audit_logs": cnt_audit,
            },
            "rollback_outcome": {
                "client_tx_rolled_back": client_tx_rolled_back,
                "engine_status": "Clean (row state reverted; sequence/OID/WAL side-effects preserved)"
            },
            "notices": notices,
        }

        with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as jf:
            json.dump(summary, jf, indent=2)

        print("\n=== PHASE 4T-E LOCAL VERIFICATION: SUCCESS (LOCAL PASS) ===")
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

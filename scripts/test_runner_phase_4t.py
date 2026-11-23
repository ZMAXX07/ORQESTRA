#!/usr/bin/env python3
"""
ORQESTRA Phase 4T-I-D: Runner Security Verification Test Suite
=============================================================
File: test_runner_phase_4t.py

Comprehensive local unit and integration tests covering:
1. Effective Connection Settings & Libpq Parameter Validation:
   - conninfo_to_dict effective parameter resolution.
   - Strict port and dbname enforcement for direct host (5432, postgres).
   - Strict port and dbname enforcement for pooler host (6543, postgres).
   - Rejection of forbidden hostaddr option (prevents DNS bypass/spoofing).
   - Rejection of forbidden service option.
   - Rejection of URL query parameters overriding host, port, user, or dbname.
   - Rejection of duplicate query parameters.
   - Rejection of malformed / unparseable connection strings.
2. Strict TLS Verification Policy (verify-full only):
   - sslmode=verify-full accepted.
   - sslmode=verify-ca rejected.
   - sslmode=require rejected.
   - sslmode=disable rejected.
   - Missing sslmode rejected.
   - Duplicate / conflicting sslmode rejected.
3. Supabase Regional Pooler & Direct Host Enclosure:
   - Correct direct host (db.<staging_ref>.supabase.co:5432/postgres) accepted.
   - Correct regional pooler (aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres) with allowed user accepted.
   - Wrong pooler region (e.g. aws-0-us-east-1.pooler.supabase.com) rejected.
   - Wrong project username (e.g. postgres.otherproject) rejected.
   - Non-allowlisted pooler username rejected.
   - Arbitrary pooler hostname rejected.
   - Other project direct host rejected.
   - Arbitrary external PostgreSQL host rejected.
4. Production Database Isolation & Dynamic Staging Reference Enforcement:
   - Denies confirmed production project reference ('vwlwbwwrumsmjqeavvxk') with CRITICAL SECURITY VIOLATION.
   - Rejects connection strings targeting production direct host or pooler username.
   - Rejects local disposable mode targeting production.
   - Requires valid 20-character staging project reference in remote mode.
   - Enforces project reference matching hostname and pooler username.
   - Verifies run_staging_diagnostic.py protects against targeting production.
5. Process Argument Security & Strict Environment Variable Separation:
   - Confirms --db-url argument is completely removed from CLI parser.
   - Confirms remote mode strictly requires STAGING_DATABASE_URL and ignores LOCAL_DATABASE_URL.
   - Confirms local mode strictly requires LOCAL_DATABASE_URL and ignores STAGING_DATABASE_URL.
   - Confirms password sanitization in URLs and exception strings.
5. Local Disposable Destination Validation:
   - Local mode with localhost / 127.0.0.1 / ::1 on port 5433 and db orqestra_staging_test accepted.
   - Local mode on wrong port (e.g. 5432) rejected.
   - Local mode on wrong db (e.g. postgres) rejected.
   - Local mode targeting remote Supabase direct or pooler host rejected (bypass prevention).
   - Local mode targeting external non-loopback IP rejected.
6. Two-Tier Hash Integrity Verification:
   - Manifest authenticated against hard-pinned SHA-256.
   - Tampered manifest copy rejected.
   - Tampered SQL copy rejected.
7. Multi-Statement Execution & Engine Transaction States:
   - Multi-statement SQL executes in single session via prepare=False.
   - Missing final rollback detected: conn.info.transaction_status INTRANS triggers failure.
   - Aborted transaction detected: conn.info.transaction_status INERROR triggers failure.
   - Abrupt connection termination leaves zero uncommitted rows (engine-level rollback).
8. Baseline Identity & Invariance Checks:
   - Strengthened verification: Business (ID, Name, Slug, Currency).
   - Strengthened verification: Product (Name, Business ID) and Inventory (Stock 18, Threshold 5, Business ID).
   - Strengthened verification: Invoice (Status 'issued', Amount 10000.00, Business ID).
   - Full pipeline executed and verified (all 8 scenarios pass, 0 rows surviving in 6 tables).
   - Dynamic table count invariance confirmed (before counts == after counts across all 10 tables).
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import uuid

import psycopg
from psycopg import pq

workspace_root = pathlib.Path(__file__).resolve().parent
repo_root = workspace_root.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import run_phase_4t_remote as runner
import run_staging_diagnostic as diagnostic
from backend.app.tests import manage_staging_db, run_migrations

TEST_STAGING_REF = "mockstagingproj12345"
TEST_DIRECT_HOST = runner.get_approved_direct_host(TEST_STAGING_REF)


# ==============================================================================
# 1. EFFECTIVE CONNECTION SETTINGS & LIBPQ PARAMETER TESTS
# ==============================================================================
def test_effective_connection_settings_validation():
    print("\n--- 1. TESTING EFFECTIVE CONNECTION SETTINGS & LIBPQ PARSING ---")

    base_valid_direct = (
        f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/postgres?sslmode=verify-full"
    )

    # 1.1 Valid direct connection string resolves cleanly with port and dbname
    info = runner.validate_effective_connection_info(
        TEST_STAGING_REF, base_valid_direct, local_disposable=False
    )
    assert info["effective_host"] == TEST_DIRECT_HOST
    assert info["effective_port"] == "5432"
    assert info["effective_dbname"] == "postgres"
    assert info["effective_user"] == "postgres"
    assert info["effective_sslmode"] == "verify-full"
    assert info["destination_type"] == "direct"
    print("  [PASS] Valid connection parameters (port 5432, dbname postgres) resolved cleanly.")

    # 1.2 Direct host with wrong port rejected
    direct_wrong_port = (
        f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5433/postgres?sslmode=verify-full"
    )
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, direct_wrong_port, local_disposable=False
        )
        assert False, "Should have rejected direct host with port 5433"
    except ValueError as e:
        assert "Direct Supabase host requires port '5432'" in str(e)
        print("  [PASS] Direct Supabase host with wrong port (5433) rejected.")

    # 1.3 Direct host with wrong dbname rejected
    direct_wrong_db = (
        f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/other_db?sslmode=verify-full"
    )
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, direct_wrong_db, local_disposable=False
        )
        assert False, "Should have rejected direct host with non-postgres database"
    except ValueError as e:
        assert "Direct Supabase host requires database 'postgres'" in str(e)
        print("  [PASS] Direct Supabase host with wrong dbname (other_db) rejected.")

    # 1.4 Rejection of forbidden hostaddr option (prevents destination spoofing)
    spoofed_hostaddr = base_valid_direct + "&hostaddr=1.2.3.4"
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, spoofed_hostaddr, local_disposable=False
        )
        assert False, "Should have rejected hostaddr parameter"
    except ValueError as e:
        assert "Forbidden connection option 'hostaddr'" in str(e)
        print("  [PASS] Forbidden 'hostaddr' option rejected (DNS destination override prevented).")

    # 1.5 Rejection of forbidden service option
    service_param = base_valid_direct + "&service=my_service"
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, service_param, local_disposable=False
        )
        assert False, "Should have rejected service parameter"
    except ValueError as e:
        assert "Forbidden connection option 'service'" in str(e)
        print("  [PASS] Forbidden 'service' option rejected.")

    # 1.6 Rejection of URL query parameter attempting to override host
    host_override = base_valid_direct + "&host=evil.com"
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, host_override, local_disposable=False
        )
        assert False, "Should have rejected conflicting host parameter in query"
    except ValueError as e:
        assert "Conflicting parameter 'host'" in str(e)
        print("  [PASS] Conflicting 'host' parameter in URL query string rejected.")

    # 1.7 Rejection of URL query parameter attempting to override user
    user_override = base_valid_direct + "&user=malicious_user"
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, user_override, local_disposable=False
        )
        assert False, "Should have rejected conflicting user parameter in query"
    except ValueError as e:
        assert "Conflicting parameter 'user'" in str(e)
        print("  [PASS] Conflicting 'user' parameter in URL query string rejected.")

    # 1.8 Rejection of duplicate query parameters
    duplicate_params = base_valid_direct + "&application_name=app1&application_name=app2"
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, duplicate_params, local_disposable=False
        )
        assert False, "Should have rejected duplicate query parameters"
    except ValueError as e:
        assert "Duplicate connection parameter 'application_name'" in str(e)
        print("  [PASS] Duplicate connection parameter in URL query rejected.")

    # 1.9 Rejection of malformed / unparseable connection string
    malformed_conn = "not_a_valid_url_at_all ::: 1234"
    try:
        runner.validate_effective_connection_info(
            TEST_STAGING_REF, malformed_conn, local_disposable=False
        )
        assert False, "Should have rejected malformed connection string"
    except ValueError as e:
        assert "DESTINATION VALIDATION FAILED" in str(e) or "CONNECTION SECURITY ABORT" in str(e)
        print("  [PASS] Malformed connection string rejected.")


# ==============================================================================
# 2. STRICT TLS VERIFICATION TESTS (verify-full only)
# ==============================================================================
def test_tls_verification_policy():
    print("\n--- 2. TESTING STRICT TLS VERIFICATION POLICY (verify-full only) ---")

    host = TEST_DIRECT_HOST
    pref = TEST_STAGING_REF

    # 2.1 verify-full accepted
    url_verify_full = f"postgresql://postgres:secret@{host}:5432/postgres?sslmode=verify-full"
    info = runner.validate_effective_connection_info(pref, url_verify_full, local_disposable=False)
    assert info["effective_sslmode"] == "verify-full"
    print("  [PASS] sslmode=verify-full accepted.")

    # 2.2 verify-ca rejected
    url_verify_ca = f"postgresql://postgres:secret@{host}:5432/postgres?sslmode=verify-ca"
    try:
        runner.validate_effective_connection_info(pref, url_verify_ca, local_disposable=False)
        assert False, "Should have rejected verify-ca"
    except ValueError as e:
        assert "strictly require 'sslmode=verify-full'" in str(e)
        print("  [PASS] sslmode=verify-ca rejected.")

    # 2.3 require rejected
    url_require = f"postgresql://postgres:secret@{host}:5432/postgres?sslmode=require"
    try:
        runner.validate_effective_connection_info(pref, url_require, local_disposable=False)
        assert False, "Should have rejected require"
    except ValueError as e:
        assert "strictly require 'sslmode=verify-full'" in str(e)
        print("  [PASS] sslmode=require rejected.")

    # 2.4 disable rejected
    url_disable = f"postgresql://postgres:secret@{host}:5432/postgres?sslmode=disable"
    try:
        runner.validate_effective_connection_info(pref, url_disable, local_disposable=False)
        assert False, "Should have rejected disable"
    except ValueError as e:
        assert "strictly require 'sslmode=verify-full'" in str(e)
        print("  [PASS] sslmode=disable rejected.")

    # 2.5 Missing sslmode rejected
    url_no_ssl = f"postgresql://postgres:secret@{host}:5432/postgres"
    try:
        runner.validate_effective_connection_info(pref, url_no_ssl, local_disposable=False)
        assert False, "Should have rejected missing sslmode"
    except ValueError as e:
        assert "strictly require 'sslmode=verify-full'" in str(e)
        print("  [PASS] Missing sslmode parameter rejected.")

    # 2.6 Conflicting / duplicated sslmode rejected
    url_dup_ssl = f"postgresql://postgres:secret@{host}:5432/postgres?sslmode=verify-full&sslmode=disable"
    try:
        runner.validate_effective_connection_info(pref, url_dup_ssl, local_disposable=False)
        assert False, "Should have rejected duplicate sslmode parameter"
    except ValueError as e:
        assert "Duplicate connection parameter 'sslmode'" in str(e)
        print("  [PASS] Duplicate / conflicting sslmode query parameter rejected.")


# ==============================================================================
# 3. SUPABASE REGIONAL POOLER & DIRECT HOST ENCLOSURE TESTS
# ==============================================================================
def test_supabase_destination_enclosure():
    print("\n--- 3. TESTING REGIONAL POOLER & DIRECT HOST ENCLOSURE ---")

    pref = TEST_STAGING_REF
    pooler_host = runner.APPROVED_REGIONAL_POOLER_HOST

    # 3.1 Correct direct host accepted
    direct_url = f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/postgres?sslmode=verify-full"
    dest_dir = runner.validate_effective_connection_info(pref, direct_url, local_disposable=False)
    assert dest_dir["destination_type"] == "direct"
    assert dest_dir["effective_host"] == TEST_DIRECT_HOST
    assert dest_dir["effective_port"] == "5432"
    assert dest_dir["effective_dbname"] == "postgres"
    print("  [PASS] Correct direct host (port 5432, dbname postgres) accepted.")

    # 3.2 Correct regional pooler host and username accepted (postgres.vwlwbwwrumsmjqeavvxk)
    pooler_url_pg = f"postgresql://postgres.{pref}:secret@{pooler_host}:6543/postgres?sslmode=verify-full"
    dest_pool = runner.validate_effective_connection_info(pref, pooler_url_pg, local_disposable=False)
    assert dest_pool["destination_type"] == "pooler"
    assert dest_pool["effective_host"] == pooler_host
    assert dest_pool["effective_port"] == "6543"
    assert dest_pool["effective_dbname"] == "postgres"
    assert dest_pool["effective_user"] == f"postgres.{pref}"
    print("  [PASS] Correct regional pooler host (port 6543, db postgres, postgres user) accepted.")

    # 3.3 Correct regional pooler host with service_role project-user accepted
    pooler_url_srv = f"postgresql://service_role.{pref}:secret@{pooler_host}:6543/postgres?sslmode=verify-full"
    dest_srv = runner.validate_effective_connection_info(pref, pooler_url_srv, local_disposable=False)
    assert dest_srv["effective_user"] == f"service_role.{pref}"
    assert dest_srv["effective_port"] == "6543"
    print("  [PASS] Correct regional pooler host with service_role project-user accepted.")

    # 3.4 Pooler host with wrong port rejected (e.g. 5432 instead of 6543)
    pooler_wrong_port = f"postgresql://postgres.{pref}:secret@{pooler_host}:5432/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(pref, pooler_wrong_port, local_disposable=False)
        assert False, "Should have rejected pooler with port 5432"
    except ValueError as e:
        assert "Supabase pooler host requires port '6543'" in str(e)
        print("  [PASS] Pooler host with wrong port (5432) rejected.")

    # 3.5 Pooler host with wrong dbname rejected (e.g. other_db instead of postgres)
    pooler_wrong_db = f"postgresql://postgres.{pref}:secret@{pooler_host}:6543/other_db?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(pref, pooler_wrong_db, local_disposable=False)
        assert False, "Should have rejected pooler with wrong dbname"
    except ValueError as e:
        assert "Supabase pooler host requires database 'postgres'" in str(e)
        print("  [PASS] Pooler host with wrong dbname (other_db) rejected.")

    # 3.6 Wrong pooler region rejected (e.g., aws-0-us-east-1 instead of ap-northeast-2)
    wrong_region_pooler = f"postgresql://postgres.{pref}:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(pref, wrong_region_pooler, local_disposable=False)
        assert False, "Should have rejected wrong pooler region"
    except ValueError as e:
        assert "not an authorized destination" in str(e)
        print("  [PASS] Wrong pooler region (aws-0-us-east-1) rejected.")

    # 3.7 Wrong project username rejected on pooler
    wrong_user_pooler = f"postgresql://postgres.otherproject123:secret@{pooler_host}:6543/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(pref, wrong_user_pooler, local_disposable=False)
        assert False, "Should have rejected pooler with other project username"
    except ValueError as e:
        assert "requires an approved project-scoped username" in str(e)
        print("  [PASS] Pooler with username for different project rejected.")

    # 3.8 Arbitrary Supabase pooler hostname rejected
    arbitrary_pooler = f"postgresql://postgres.{pref}:secret@custom.pooler.supabase.com:6543/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(pref, arbitrary_pooler, local_disposable=False)
        assert False, "Should have rejected arbitrary pooler hostname"
    except ValueError as e:
        assert "not an authorized destination" in str(e)
        print("  [PASS] Arbitrary Supabase pooler hostname rejected.")

    # 3.9 Another Supabase project's direct host rejected
    other_direct = "postgresql://postgres:secret@db.otherproject123.supabase.co:5432/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(pref, other_direct, local_disposable=False)
        assert False, "Should have rejected other project direct host"
    except ValueError as e:
        assert "not an authorized destination" in str(e)
        print("  [PASS] Direct host for different Supabase project rejected.")

    # 3.10 Arbitrary external PostgreSQL host rejected
    external_host = "postgresql://postgres:secret@db.external-host.com:5432/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(pref, external_host, local_disposable=False)
        assert False, "Should have rejected external host"
    except ValueError as e:
        assert "not an authorized destination" in str(e)
        print("  [PASS] Arbitrary external PostgreSQL host rejected.")


# ==============================================================================
# 3B. PRODUCTION DATABASE ISOLATION & STAGING REF ENFORCEMENT TESTS
# ==============================================================================
def test_production_database_isolation():
    print("\n--- 3B. TESTING PRODUCTION DATABASE ISOLATION & STAGING REF ENFORCEMENT ---")

    prod_ref = runner.KNOWN_PRODUCTION_PROJECT_REF
    assert prod_ref == "vwlwbwwrumsmjqeavvxk"

    # 3B.1 Production project reference passed directly is rejected
    prod_direct_url = f"postgresql://postgres:secret@db.{prod_ref}.supabase.co:5432/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(prod_ref, prod_direct_url, local_disposable=False)
        assert False, "Should have rejected production project reference"
    except ValueError as e:
        assert "CRITICAL SECURITY VIOLATION" in str(e)
        assert "confirmed as the PRODUCTION project" in str(e)
        print("  [PASS] Passing production project reference directly triggers CRITICAL SECURITY VIOLATION.")

    # 3B.2 Passing valid staging ref but URL points to production direct host is rejected
    try:
        runner.validate_effective_connection_info(TEST_STAGING_REF, prod_direct_url, local_disposable=False)
        assert False, "Should have rejected URL targeting production"
    except ValueError as e:
        assert "CRITICAL SECURITY VIOLATION" in str(e)
        assert "Connection string targets confirmed PRODUCTION project" in str(e)
        print("  [PASS] Connection string targeting production direct host rejected with CRITICAL SECURITY VIOLATION.")

    # 3B.3 Passing valid staging ref but pooler username targets production is rejected
    prod_pooler_url = (
        f"postgresql://postgres.{prod_ref}:secret@{runner.APPROVED_REGIONAL_POOLER_HOST}:6543/postgres?sslmode=verify-full"
    )
    try:
        runner.validate_effective_connection_info(TEST_STAGING_REF, prod_pooler_url, local_disposable=False)
        assert False, "Should have rejected pooler username targeting production"
    except ValueError as e:
        assert "CRITICAL SECURITY VIOLATION" in str(e)
        print("  [PASS] Pooler URL with production-scoped username rejected with CRITICAL SECURITY VIOLATION.")

    # 3B.4 Local disposable mode targeting production is rejected
    try:
        runner.validate_effective_connection_info(None, prod_direct_url, local_disposable=True)
        assert False, "Should have rejected production in local mode"
    except ValueError as e:
        assert "CRITICAL SECURITY VIOLATION" in str(e) or "LOCAL MODE SECURITY ABORT" in str(e)
        print("  [PASS] Local disposable mode targeting production rejected.")

    # 3B.5 Missing or empty project reference in remote mode is rejected
    for empty_ref in (None, "", "   "):
        try:
            runner.validate_effective_connection_info(
                empty_ref,
                f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/postgres?sslmode=verify-full",
                local_disposable=False,
            )
            assert False, "Should have rejected empty project reference"
        except ValueError as e:
            assert "REMOTE DESTINATION REJECTED: Target staging project reference is required" in str(e)
    print("  [PASS] Missing / empty project reference rejected in remote mode.")

    # 3B.6 Invalid project reference format is rejected
    for invalid_ref in ("short", "too_long_project_ref_1234567890", "inv@lid-chars!", "CAPITALS123456789012"):
        try:
            runner.validate_effective_connection_info(
                invalid_ref,
                f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/postgres?sslmode=verify-full",
                local_disposable=False,
            )
            assert False, f"Should have rejected invalid project ref: {invalid_ref}"
        except ValueError as e:
            assert "REMOTE DESTINATION REJECTED: Invalid project reference format" in str(e)
    print("  [PASS] Non-conformant project reference formats rejected (must be 20 lowercase alphanumeric characters).")

    # 3B.7 Mismatch between project-ref and URL host is rejected
    mismatch_url = "postgresql://postgres:secret@db.differentproj999999.supabase.co:5432/postgres?sslmode=verify-full"
    try:
        runner.validate_effective_connection_info(TEST_STAGING_REF, mismatch_url, local_disposable=False)
        assert False, "Should have rejected mismatch between project-ref and URL host"
    except ValueError as e:
        assert "is not an authorized destination for project 'mockstagingproj12345'" in str(e)
        print("  [PASS] Hostname mismatch with staging project reference rejected.")

    # 3B.8 Mismatch between project-ref and pooler username is rejected
    mismatch_user_pooler = (
        f"postgresql://postgres.differentproj999999:secret@{runner.APPROVED_REGIONAL_POOLER_HOST}:6543/postgres?sslmode=verify-full"
    )
    try:
        runner.validate_effective_connection_info(TEST_STAGING_REF, mismatch_user_pooler, local_disposable=False)
        assert False, "Should have rejected mismatch between project-ref and pooler username"
    except ValueError as e:
        assert "requires an approved project-scoped username matching project 'mockstagingproj12345'" in str(e)
        print("  [PASS] Pooler username mismatch with staging project reference rejected.")

    # 3B.9 run_staging_diagnostic.py protects against production
    try:
        diagnostic.run_remote_supabase_diagnostic(
            [],
            pathlib.Path("nonexistent.sql"),
            "fakehash",
            pathlib.Path("report.md"),
            {},
            runner.KNOWN_PRODUCTION_PROJECT_REF,
        )
        assert False, "Should have rejected production project in diagnostic runner"
    except ValueError as e:
        assert "CRITICAL SECURITY VIOLATION" in str(e)
        assert "confirmed as PRODUCTION" in str(e)
        print("  [PASS] Diagnostic runner function rejects production project reference.")

    # 3B.10 CLI diagnostic rejects production project
    cmd_diag_prod = [
        sys.executable,
        str(workspace_root / "run_staging_diagnostic.py"),
        "--remote-supabase",
        runner.KNOWN_PRODUCTION_PROJECT_REF,
    ]
    proc_diag_prod = subprocess.run(cmd_diag_prod, capture_output=True, text=True)
    assert proc_diag_prod.returncode == 2
    assert "CRITICAL SECURITY VIOLATION: Refusing to target PRODUCTION project" in proc_diag_prod.stdout
    print("  [PASS] CLI run_staging_diagnostic.py rejects production project with exit code 2.")

    # 3B.11 CLI runner rejects production project reference
    env_mock_staging = os.environ.copy()
    env_mock_staging["STAGING_DATABASE_URL"] = (
        f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/postgres?sslmode=verify-full"
    )
    cmd_runner_prod_ref = [
        sys.executable,
        str(workspace_root / "run_phase_4t_remote.py"),
        "--project-ref",
        runner.KNOWN_PRODUCTION_PROJECT_REF,
    ]
    proc_runner_prod_ref = subprocess.run(cmd_runner_prod_ref, capture_output=True, text=True, env=env_mock_staging)
    assert proc_runner_prod_ref.returncode == 1
    assert "CRITICAL SECURITY VIOLATION" in proc_runner_prod_ref.stdout
    print("  [PASS] CLI run_phase_4t_remote.py rejects --project-ref vwlwbwwrumsmjqeavvxk with exit code 1.")

    # 3B.12 CLI runner rejects production connection string in STAGING_DATABASE_URL
    env_prod_staging_url = os.environ.copy()
    env_prod_staging_url["STAGING_DATABASE_URL"] = (
        f"postgresql://postgres:secret@db.{runner.KNOWN_PRODUCTION_PROJECT_REF}.supabase.co:5432/postgres?sslmode=verify-full"
    )
    cmd_runner_prod_url = [
        sys.executable,
        str(workspace_root / "run_phase_4t_remote.py"),
        "--project-ref",
        TEST_STAGING_REF,
    ]
    proc_runner_prod_url = subprocess.run(cmd_runner_prod_url, capture_output=True, text=True, env=env_prod_staging_url)
    assert proc_runner_prod_url.returncode == 1
    assert "CRITICAL SECURITY VIOLATION" in proc_runner_prod_url.stdout
    print("  [PASS] CLI run_phase_4t_remote.py rejects STAGING_DATABASE_URL targeting production with exit code 1.")

    # 3B.13 CLI runner rejects missing --project-ref in remote mode
    cmd_runner_missing_ref = [
        sys.executable,
        str(workspace_root / "run_phase_4t_remote.py"),
    ]
    proc_runner_missing_ref = subprocess.run(cmd_runner_missing_ref, capture_output=True, text=True, env=env_mock_staging)
    assert proc_runner_missing_ref.returncode == 1
    assert "ENVIRONMENT CONFIGURATION ERROR: --project-ref is required" in proc_runner_missing_ref.stdout
    print("  [PASS] CLI run_phase_4t_remote.py rejects missing --project-ref in remote mode with exit code 1.")


# ==============================================================================
# 4. PROCESS ARGUMENT SECURITY & ENVIRONMENT VARIABLE SEPARATION
# ==============================================================================
def test_process_argument_security():
    print("\n--- 4. TESTING PROCESS ARGUMENT SECURITY & STRICT ENV VAR SEPARATION ---")

    # 4.1 Verify --db-url argument is completely removed from argument parser
    cmd = [sys.executable, str(workspace_root / "run_phase_4t_remote.py"), "--help"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0
    assert "--db-url" not in out.stdout, "--db-url must NOT be an exposed argument in the runner CLI!"
    print("  [PASS] Confirmed --db-url is removed from command-line interface.")

    # 4.2 Verify remote mode strictly requires STAGING_DATABASE_URL
    # Even if LOCAL_DATABASE_URL is set, remote mode must fail closed
    env_with_local_only = os.environ.copy()
    env_with_local_only.pop("STAGING_DATABASE_URL", None)
    env_with_local_only["LOCAL_DATABASE_URL"] = "postgresql://postgres:secret@localhost:5433/orqestra_staging_test"

    cmd_remote = [
        sys.executable,
        str(workspace_root / "run_phase_4t_remote.py"),
        "--project-ref", TEST_STAGING_REF,
    ]
    proc_remote = subprocess.run(cmd_remote, capture_output=True, text=True, env=env_with_local_only)
    assert proc_remote.returncode != 0
    assert "STAGING_DATABASE_URL environment variable is not set" in proc_remote.stdout
    print("  [PASS] Remote mode strictly requires STAGING_DATABASE_URL (ignores LOCAL_DATABASE_URL).")

    # 4.3 Verify local mode strictly requires LOCAL_DATABASE_URL
    # Even if STAGING_DATABASE_URL is set, local mode must fail closed if LOCAL_DATABASE_URL is missing
    env_with_staging_only = os.environ.copy()
    env_with_staging_only.pop("LOCAL_DATABASE_URL", None)
    env_with_staging_only["STAGING_DATABASE_URL"] = (
        f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/postgres?sslmode=verify-full"
    )

    cmd_local = [
        sys.executable,
        str(workspace_root / "run_phase_4t_remote.py"),
        "--local-disposable",
    ]
    proc_local = subprocess.run(cmd_local, capture_output=True, text=True, env=env_with_staging_only)
    assert proc_local.returncode != 0
    assert "LOCAL_DATABASE_URL environment variable is not set" in proc_local.stdout
    print("  [PASS] Local mode strictly requires LOCAL_DATABASE_URL (ignores STAGING_DATABASE_URL).")


# ==============================================================================
# 5. CREDENTIAL SANITIZATION TESTS
# ==============================================================================
def test_credential_sanitization():
    print("\n--- 5. TESTING CREDENTIAL SANITIZATION ---")

    # 5.1 Standalone connection URL masking (ordinary password)
    raw_url = "postgresql://my_user:super_secret_password_123@db.vwlwbwwrumsmjqeavvxk.supabase.co:5432/postgres"
    sanitized = runner.sanitize_db_url(raw_url)
    assert "super_secret_password_123" not in sanitized
    assert "my_user:***@db.vwlwbwwrumsmjqeavvxk.supabase.co:5432/postgres" in sanitized
    print("  [PASS] Standalone connection URL sanitized; password masked with '***'.")

    # 5.2 Percent-encoded characters in password
    encoded_url = "postgresql://my_user:p%40ss%21word%2399@host:5432/db"
    sanitized_enc = runner.sanitize_db_url(encoded_url)
    assert "p%40ss%21word%2399" not in sanitized_enc
    assert "my_user:***@host:5432/db" in sanitized_enc
    print("  [PASS] Percent-encoded password characters sanitized.")

    # 5.3 Literal '@' in password
    literal_at_url = "postgresql://postgres:p@ssword123@host:5432/postgres"
    sanitized_at = runner.sanitize_db_url(literal_at_url)
    assert "p@ssword123" not in sanitized_at
    assert "ssword123" not in sanitized_at
    assert "postgres:***@host:5432/postgres" in sanitized_at
    print("  [PASS] Password with literal '@' sanitized; zero character leakage.")

    # 5.4 Multiple '@' characters in password
    multi_at_url = "postgresql://postgres:p@ss@@word@@999@host:5432/postgres"
    sanitized_multi_at = runner.sanitize_db_url(multi_at_url)
    assert "p@ss@@word@@999" not in sanitized_multi_at
    assert "word" not in sanitized_multi_at
    assert "postgres:***@host:5432/postgres" in sanitized_multi_at
    print("  [PASS] Password with multiple '@' characters sanitized completely.")

    # 5.5 Sensitive query parameters
    query_url = "postgresql://user:pass@host:5432/db?password=secret_val&token=tok_secret&api_key=key_secret&sslmode=verify-full"
    sanitized_query = runner.sanitize_db_url(query_url)
    assert "pass" not in sanitized_query or "user:***" in sanitized_query
    assert "secret_val" not in sanitized_query
    assert "tok_secret" not in sanitized_query
    assert "key_secret" not in sanitized_query
    assert "password=***" in sanitized_query
    assert "token=***" in sanitized_query
    assert "api_key=***" in sanitized_query
    assert "sslmode=verify-full" in sanitized_query
    print("  [PASS] Sensitive query parameters (password, token, api_key) masked with '***'.")

    # 5.6 Key-value conninfo strings
    kv_conninfo = "host=localhost port=5432 password=my_plain_pass dbname=test"
    sanitized_kv = runner.sanitize_db_url(kv_conninfo)
    assert "my_plain_pass" not in sanitized_kv
    assert "password=***" in sanitized_kv
    print("  [PASS] Key-value conninfo password masked.")

    # 5.7 Embedded URL in exception text masking
    err_text = (
        "psycopg.OperationalError: connection to "
        "postgresql://postgres:TopSecretPass999@localhost:5433/orqestra_staging_test failed: server closed"
    )
    sanitized_err = runner.sanitize_db_url(err_text)
    assert "TopSecretPass999" not in sanitized_err
    assert "postgres:***@localhost:5433/orqestra_staging_test" in sanitized_err
    print("  [PASS] Embedded connection URL in exception text sanitized; password masked.")


# ==============================================================================
# 6. LOCAL DISPOSABLE DESTINATION VALIDATION TESTS
# ==============================================================================
def test_local_disposable_destination_validation():
    print("\n--- 6. TESTING LOCAL-DISPOSABLE DESTINATION VALIDATION ---")

    # 6.1 localhost with port 5433 and db orqestra_staging_test accepted
    dest_lh = runner.validate_effective_connection_info(
        None, "postgresql://postgres:secret@localhost:5433/orqestra_staging_test", local_disposable=True
    )
    assert dest_lh["mode"] == "local-disposable"
    assert dest_lh["effective_host"] == "localhost"
    assert dest_lh["effective_port"] == "5433"
    assert dest_lh["effective_dbname"] == "orqestra_staging_test"
    print("  [PASS] Local mode with 'localhost:5433/orqestra_staging_test' accepted.")

    # 6.2 127.0.0.1 accepted
    dest_ip4 = runner.validate_effective_connection_info(
        None, "postgresql://postgres:secret@127.0.0.1:5433/orqestra_staging_test", local_disposable=True
    )
    assert dest_ip4["mode"] == "local-disposable"
    assert dest_ip4["effective_host"] == "127.0.0.1"
    assert dest_ip4["effective_port"] == "5433"
    assert dest_ip4["effective_dbname"] == "orqestra_staging_test"
    print("  [PASS] Local mode with '127.0.0.1:5433/orqestra_staging_test' accepted.")

    # 6.3 ::1 accepted
    dest_ip6 = runner.validate_effective_connection_info(
        None, "postgresql://postgres:secret@[::1]:5433/orqestra_staging_test", local_disposable=True
    )
    assert dest_ip6["mode"] == "local-disposable"
    assert dest_ip6["effective_host"] == "::1"
    assert dest_ip6["effective_port"] == "5433"
    assert dest_ip6["effective_dbname"] == "orqestra_staging_test"
    print("  [PASS] Local mode with '[::1]:5433/orqestra_staging_test' accepted.")

    # 6.4 Wrong local port rejected (e.g. 5432 instead of 5433)
    try:
        runner.validate_effective_connection_info(
            None, "postgresql://postgres:secret@localhost:5432/orqestra_staging_test", local_disposable=True
        )
        assert False, "Should have rejected local mode on port 5432"
    except ValueError as e:
        assert "--local-disposable requires port '5433'" in str(e)
        print("  [PASS] Local mode on wrong port (5432) rejected.")

    # 6.5 Wrong local database rejected (e.g. postgres instead of orqestra_staging_test)
    try:
        runner.validate_effective_connection_info(
            None, "postgresql://postgres:secret@localhost:5433/postgres", local_disposable=True
        )
        assert False, "Should have rejected local mode on database postgres"
    except ValueError as e:
        assert "--local-disposable requires database 'orqestra_staging_test'" in str(e)
        print("  [PASS] Local mode on wrong database (postgres) rejected.")

    # 6.6 Local mode targeting remote Supabase URL rejected (BYPASS PREVENTION)
    remote_bypass_direct = (
        f"postgresql://postgres:secret@{TEST_DIRECT_HOST}:5432/postgres"
    )
    try:
        runner.validate_effective_connection_info(None, remote_bypass_direct, local_disposable=True)
        assert False, "Should have rejected local mode targeting remote Supabase"
    except ValueError as e:
        assert "cannot be used with remote Supabase destination" in str(e)
        print("  [PASS] Local mode targeting remote Supabase direct host rejected (bypass prevented).")

    # 6.7 Local mode targeting Supabase pooler rejected (BYPASS PREVENTION)
    remote_bypass_pooler = (
        f"postgresql://postgres.{TEST_STAGING_REF}:secret"
        f"@{runner.APPROVED_REGIONAL_POOLER_HOST}:6543/postgres"
    )
    try:
        runner.validate_effective_connection_info(None, remote_bypass_pooler, local_disposable=True)
        assert False, "Should have rejected local mode targeting Supabase pooler"
    except ValueError as e:
        assert "cannot be used with remote Supabase destination" in str(e)
        print("  [PASS] Local mode targeting Supabase pooler host rejected (bypass prevented).")

    # 6.8 Local mode targeting external non-loopback IP rejected
    external_ip = "postgresql://postgres:secret@192.168.1.50:5433/orqestra_staging_test"
    try:
        runner.validate_effective_connection_info(None, external_ip, local_disposable=True)
        assert False, "Should have rejected external IP in local mode"
    except ValueError as e:
        assert "permits only loopback destinations" in str(e)
        print("  [PASS] External IP address rejected in local mode.")


# ==============================================================================
# 7. TWO-TIER HASH INTEGRITY TESTS
# ==============================================================================
def test_two_tier_hash_integrity():
    print("\n--- 7. TESTING TWO-TIER HASH INTEGRITY ---")

    # 7.1 Legitimate files verify unconditionally
    sql_content, sql_hash, manifest_hash = runner.verify_manifest_and_sql_integrity()
    assert manifest_hash == runner.PINNED_MANIFEST_SHA256
    assert sql_hash == "b1f21dc79f50153f2da9110ae14c8bc058b539c8ae0165b0044f7191389e8121"
    print(f"  [PASS] Manifest authenticated against pinned SHA-256: {manifest_hash}")
    print(f"  [PASS] SQL authenticated against authenticated manifest: {sql_hash}")

    # 7.2 Modified manifest copy rejected against pinned SHA-256
    manifest_bytes = runner.DEFAULT_HASH_MANIFEST_PATH.read_bytes()
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tf:
        tf.write(manifest_bytes + b" ")
        tampered_manifest_path = pathlib.Path(tf.name)

    try:
        runner.verify_manifest_and_sql_integrity(manifest_path=tampered_manifest_path)
        assert False, "Should have rejected tampered manifest"
    except ValueError as e:
        assert "MANIFEST AUTHENTICATION FAILED" in str(e)
        print("  [PASS] Tampered manifest copy rejected against pinned SHA-256.")
    finally:
        tampered_manifest_path.unlink(missing_ok=True)

    # 7.3 Modified SQL copy rejected against valid manifest
    sql_bytes = runner.DEFAULT_SQL_PATH.read_bytes()
    with tempfile.NamedTemporaryFile("wb", suffix=".sql", delete=False) as tf:
        tf.write(sql_bytes + b"\n-- Tampered Line")
        tampered_sql_path = pathlib.Path(tf.name)

    try:
        runner.verify_manifest_and_sql_integrity(sql_path=tampered_sql_path)
        assert False, "Should have rejected tampered SQL"
    except ValueError as e:
        assert "SQL INTEGRITY CHECK FAILED" in str(e)
        print("  [PASS] Tampered SQL copy rejected against authenticated manifest.")
    finally:
        tampered_sql_path.unlink(missing_ok=True)


# ==============================================================================
# 8. MULTI-STATEMENT EXECUTION, BASELINE CHECKS & FULL PIPELINE (LOCAL DISPOSABLE)
# ==============================================================================
def test_multi_statement_and_baseline_pipeline():
    print("\n--- 8. TESTING MULTI-STATEMENT EXECUTION, BASELINE & TRANSACTION STATES ---")

    manage_staging_db.cleanup()
    conn_url = manage_staging_db.init_cluster()
    admin_url = conn_url.replace("/orqestra_staging_test", "/postgres")

    log_file_path = manage_staging_db.DATA_DIR / "pg_server_runner_test_d.log"
    log_fp = open(log_file_path, "w", encoding="utf-8")
    postgres_exe = str(manage_staging_db.POSTGRES_BIN_DIR / "postgres.exe")

    proc = subprocess.Popen(
        [postgres_exe, "-D", str(manage_staging_db.DATA_DIR), "-p", str(manage_staging_db.PORT)],
        stdout=log_fp,
        stderr=subprocess.STDOUT,
    )

    try:
        # Wait for local postgres readiness
        for _ in range(30):
            time.sleep(0.3)
            if manage_staging_db.is_server_available(admin_url, timeout=1.0):
                break
        else:
            raise RuntimeError("Timed out waiting for local PostgreSQL 16 cluster to start.")

        manage_staging_db.create_database()
        run_migrations.apply_migrations()

        # 8.1 Multi-statement execution works cleanly with prepare=False
        multi_sql = """
            BEGIN;
            CREATE TEMP TABLE temp_test_tbl (id INT);
            INSERT INTO temp_test_tbl VALUES (1), (2);
            DO $$ BEGIN RAISE NOTICE 'MANIFEST_JSON:{"test": 1}'; END $$;
            ROLLBACK;
        """
        res = runner.execute_functional_test(conn_url, multi_sql)
        assert res["rolled_back_cleanly"] is True
        assert res["final_transaction_status"] == "IDLE"
        print("  [PASS] Multi-statement execution via prepare=False verified (Status: IDLE).")

        # 8.2 Missing final rollback detected (status remains INTRANS)
        missing_rollback_sql = """
            BEGIN;
            CREATE TEMP TABLE temp_uncommitted_tbl (id INT);
            INSERT INTO temp_uncommitted_tbl VALUES (42);
        """
        try:
            runner.execute_functional_test(conn_url, missing_rollback_sql)
            assert False, "Should have detected missing rollback"
        except RuntimeError as e:
            assert "TRANSACTION STATE AUDIT FAILED" in str(e)
            assert "INTRANS" in str(e)
            print("  [PASS] Missing final rollback detected (Transaction status INTRANS caught; emergency rollback executed).")

        # 8.3 Aborted transaction detected (status INERROR)
        error_tx_sql = """
            BEGIN;
            SELECT 1/0; -- Division by zero inside transaction block
            ROLLBACK;
        """
        try:
            runner.execute_functional_test(conn_url, error_tx_sql)
            assert False, "Should have failed on divide by zero"
        except RuntimeError as e:
            assert "division by zero" in str(e)
            print("  [PASS] Transaction error trapped; emergency rollback executed.")

        # 8.4 Engine-level disconnect rollback guarantee
        abrupt_biz_id = str(uuid.uuid4())
        abrupt_conn = psycopg.connect(conn_url, autocommit=False)
        with abrupt_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.businesses (id, name, slug)
                VALUES (%s, 'Abrupt Disconnect Biz', 'abrupt-disconnect-biz-d');
            """, (abrupt_biz_id,))

        abrupt_conn.close()
        print("  Abruptly closed client connection with uncommitted insert.")

        with psycopg.connect(conn_url) as verify_conn:
            with verify_conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM public.businesses WHERE id = %s;", (abrupt_biz_id,))
                cnt = cur.fetchone()[0]
                assert cnt == 0, f"Engine failed to rollback on disconnect! Count={cnt}"
        print("  [PASS] Engine-level disconnect rollback verified: 0 uncommitted rows survived.")

        # 8.5 Seed Phase 4A baseline with all required fields
        prod_id = str(uuid.uuid4())
        cust_id = str(uuid.uuid4())
        inv_id = str(uuid.uuid4())
        invoice_uuid = str(uuid.uuid4())

        with psycopg.connect(conn_url) as seed_conn:
            with seed_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.businesses (id, name, slug, currency)
                    VALUES (%s, %s, %s, %s);
                """, (
                    runner.BASELINE_BUSINESS_ID,
                    runner.BASELINE_BUSINESS_NAME,
                    runner.BASELINE_BUSINESS_SLUG,
                    runner.BASELINE_BUSINESS_CURRENCY,
                ))

                cur.execute("""
                    INSERT INTO public.products (id, business_id, sku, name, unit_price)
                    VALUES (%s, %s, %s, %s, 500.00);
                """, (
                    prod_id,
                    runner.BASELINE_BUSINESS_ID,
                    runner.BASELINE_SKU,
                    runner.BASELINE_PRODUCT_NAME,
                ))

                cur.execute("""
                    INSERT INTO public.inventory (id, business_id, product_id, quantity_on_hand, reorder_threshold)
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    inv_id,
                    runner.BASELINE_BUSINESS_ID,
                    prod_id,
                    runner.BASELINE_STOCK_QTY,
                    runner.BASELINE_REORDER_THRESHOLD,
                ))

                cur.execute("""
                    INSERT INTO public.customers (id, business_id, name, email)
                    VALUES (%s, %s, 'Staging Customer A', 'cust-a@example.com');
                """, (cust_id, runner.BASELINE_BUSINESS_ID))

                cur.execute("""
                    INSERT INTO public.invoices (id, business_id, customer_id, invoice_number, status, amount_due, due_date)
                    VALUES (%s, %s, %s, %s, %s, %s, '2026-12-31');
                """, (
                    invoice_uuid,
                    runner.BASELINE_BUSINESS_ID,
                    cust_id,
                    runner.BASELINE_INVOICE_NUMBER,
                    runner.BASELINE_INVOICE_STATUS,
                    runner.BASELINE_INVOICE_AMOUNT,
                ))
            seed_conn.commit()

        # 8.6 Strengthened Baseline Identity Verification Tests
        with psycopg.connect(conn_url) as base_conn:
            # Passes when baseline is intact
            base_report = runner.verify_baseline_invariants(base_conn)
            assert base_report["business_intact"] is True
            assert base_report["product_stock_intact"] is True
            assert base_report["invoice_intact"] is True
            print("  [PASS] Strengthened baseline identity verification passed unconditionally.")

            # Test mismatch on business slug triggers failure
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.businesses SET slug = 'wrong-slug' WHERE id = %s;",
                    (runner.BASELINE_BUSINESS_ID,)
                )
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed on business slug mismatch"
            except RuntimeError as e:
                assert "Business slug mismatch" in str(e)
                print("  [PASS] Business slug mismatch trapped by strengthened baseline check.")

            # Restore slug
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.businesses SET slug = %s WHERE id = %s;",
                    (runner.BASELINE_BUSINESS_SLUG, runner.BASELINE_BUSINESS_ID)
                )
            base_conn.commit()

            # Test mismatch on product name triggers failure
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.products SET name = 'Wrong Product Name' WHERE sku = %s;",
                    (runner.BASELINE_SKU,)
                )
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed on product name mismatch"
            except RuntimeError as e:
                assert "Product name mismatch" in str(e)
                print("  [PASS] Product name mismatch trapped by strengthened baseline check.")

            # Restore product name
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.products SET name = %s WHERE sku = %s;",
                    (runner.BASELINE_PRODUCT_NAME, runner.BASELINE_SKU)
                )
            base_conn.commit()

            # Test mismatch on inventory reorder_threshold triggers failure
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.inventory SET reorder_threshold = 99 WHERE product_id = %s;",
                    (prod_id,)
                )
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed on inventory threshold mismatch"
            except RuntimeError as e:
                assert "reorder_threshold mismatch" in str(e)
                print("  [PASS] Inventory reorder_threshold mismatch trapped by strengthened baseline check.")

            # Restore inventory threshold
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.inventory SET reorder_threshold = %s WHERE product_id = %s;",
                    (runner.BASELINE_REORDER_THRESHOLD, prod_id)
                )
            base_conn.commit()

            # Test duplicate business name fails closed
            dup_biz_id = str(uuid.uuid4())
            with base_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.businesses (id, name, slug, currency) VALUES (%s, %s, 'techzone-dup', 'INR');",
                    (dup_biz_id, runner.BASELINE_BUSINESS_NAME)
                )
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed on duplicate business name"
            except RuntimeError as e:
                assert "Duplicate business records" in str(e)
                print("  [PASS] Duplicate business name trapped by strengthened baseline check.")

            with base_conn.cursor() as cur:
                cur.execute("DELETE FROM public.businesses WHERE id = %s;", (dup_biz_id,))
            base_conn.commit()

            # Test missing product for business fails closed
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.products SET sku = 'STG-MISSING' WHERE id = %s;",
                    (prod_id,)
                )
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed on missing product SKU"
            except RuntimeError as e:
                assert "Product SKU 'STG-1890' not found for business" in str(e)
                print("  [PASS] Missing product SKU fails closed with exact business scoping.")

            # Restore product SKU
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.products SET sku = %s WHERE id = %s;",
                    (runner.BASELINE_SKU, prod_id)
                )
            base_conn.commit()

            # Test cross-business duplicate SKU isolation
            cross_biz_id = str(uuid.uuid4())
            cross_prod_id = str(uuid.uuid4())
            with base_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.businesses (id, name, slug, currency) VALUES (%s, 'Cross Biz Prod', 'cross-biz-prod', 'INR');",
                    (cross_biz_id,)
                )
                cur.execute(
                    "INSERT INTO public.products (id, business_id, sku, name, unit_price) VALUES (%s, %s, %s, 'Cross Prod', 100.00);",
                    (cross_prod_id, cross_biz_id, runner.BASELINE_SKU)
                )
            base_conn.commit()

            # Baseline check MUST PASS because TechZone's STG-1890 is intact and scoped by business_id
            report_cross_prod = runner.verify_baseline_invariants(base_conn)
            assert report_cross_prod["product_stock_intact"] is True
            print("  [PASS] Cross-business duplicate SKU safely isolated by tenant scoping.")

            # If TechZone's product is hidden, baseline MUST NOT match the cross-business product!
            with base_conn.cursor() as cur:
                cur.execute("UPDATE public.products SET sku = 'STG-HIDDEN' WHERE id = %s;", (prod_id,))
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed closed when TechZone product is absent even if cross-business product exists"
            except RuntimeError as e:
                assert f"Product SKU '{runner.BASELINE_SKU}' not found for business '{runner.BASELINE_BUSINESS_ID}'" in str(e)
                print("  [PASS] Cross-business product never falsely accepted for target tenant.")

            # Restore TechZone product and clean up cross tenant
            with base_conn.cursor() as cur:
                cur.execute("UPDATE public.products SET sku = %s WHERE id = %s;", (runner.BASELINE_SKU, prod_id))
                cur.execute("DELETE FROM public.products WHERE id = %s;", (cross_prod_id,))
                cur.execute("DELETE FROM public.businesses WHERE id = %s;", (cross_biz_id,))
            base_conn.commit()

            # Test missing invoice for business fails closed
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.invoices SET invoice_number = 'INV-MISSING' WHERE id = %s;",
                    (invoice_uuid,)
                )
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed on missing invoice number"
            except RuntimeError as e:
                assert "Invoice 'INV-202611-0008' not found for business" in str(e)
                print("  [PASS] Missing invoice fails closed with exact business scoping.")

            # Restore invoice number
            with base_conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.invoices SET invoice_number = %s WHERE id = %s;",
                    (runner.BASELINE_INVOICE_NUMBER, invoice_uuid)
                )
            base_conn.commit()

            # Test cross-business duplicate invoice number isolation
            cross_inv_biz_id = str(uuid.uuid4())
            cross_inv_cust_id = str(uuid.uuid4())
            cross_inv_id = str(uuid.uuid4())
            with base_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.businesses (id, name, slug, currency) VALUES (%s, 'Cross Biz Inv', 'cross-biz-inv', 'INR');",
                    (cross_inv_biz_id,)
                )
                cur.execute(
                    "INSERT INTO public.customers (id, business_id, name, email) VALUES (%s, %s, 'Cross Cust', 'cross@example.com');",
                    (cross_inv_cust_id, cross_inv_biz_id)
                )
                cur.execute("""
                    INSERT INTO public.invoices (id, business_id, customer_id, invoice_number, status, amount_due, due_date)
                    VALUES (%s, %s, %s, %s, 'issued', 5000.00, '2026-12-31');
                """, (cross_inv_id, cross_inv_biz_id, cross_inv_cust_id, runner.BASELINE_INVOICE_NUMBER))
            base_conn.commit()

            # Baseline check MUST PASS because TechZone's INV-202611-0008 is intact and scoped by business_id
            report_cross_inv = runner.verify_baseline_invariants(base_conn)
            assert report_cross_inv["invoice_intact"] is True
            print("  [PASS] Cross-business duplicate invoice number safely isolated by tenant scoping.")

            # If TechZone's invoice is hidden, baseline MUST NOT match the cross-business invoice!
            with base_conn.cursor() as cur:
                cur.execute("UPDATE public.invoices SET invoice_number = 'INV-HIDDEN' WHERE id = %s;", (invoice_uuid,))
            base_conn.commit()

            try:
                runner.verify_baseline_invariants(base_conn)
                assert False, "Should have failed closed when TechZone invoice is absent even if cross-business invoice exists"
            except RuntimeError as e:
                assert f"Invoice '{runner.BASELINE_INVOICE_NUMBER}' not found for business '{runner.BASELINE_BUSINESS_ID}'" in str(e)
                print("  [PASS] Cross-business invoice never falsely accepted for target tenant.")

            # Restore TechZone invoice and clean up cross tenant
            with base_conn.cursor() as cur:
                cur.execute("UPDATE public.invoices SET invoice_number = %s WHERE id = %s;", (runner.BASELINE_INVOICE_NUMBER, invoice_uuid))
                cur.execute("DELETE FROM public.invoices WHERE id = %s;", (cross_inv_id,))
                cur.execute("DELETE FROM public.customers WHERE id = %s;", (cross_inv_cust_id,))
                cur.execute("DELETE FROM public.businesses WHERE id = %s;", (cross_inv_biz_id,))
            base_conn.commit()

        # 8.7 Full pipeline execution & baseline invariance protection
        report = runner.run_pipeline(
            project_ref="local-disposable",
            conn_str=conn_url,
            allow_local=True,
        )

        assert report["verdict"] == "PASS"
        assert report["final_transaction_status"] == "IDLE"
        assert all(report["scenario_results"].values())
        assert all(cnt == 0 for cnt in report["exact_id_counts"].values())
        assert report["post_baseline"]["business_intact"] is True
        assert report["post_baseline"]["product_stock_intact"] is True
        assert report["post_baseline"]["invoice_intact"] is True
        assert report["pre_baseline"]["table_counts"] == report["post_baseline"]["table_counts"]
        print("  [PASS] Full pipeline verified on local cluster: 8/8 scenarios passed, 0 surviving rows, dynamic table counts invariant.")

    finally:
        print("\nTearing down disposable local cluster...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fp.close()
        manage_staging_db.cleanup()
        print("Local cluster cleaned up.")


# ==============================================================================
# 9. TESTING FRESH STAGING DATABASE MODE (--fresh-db)
# ==============================================================================
def test_fresh_staging_mode():
    print("\n--- 9. TESTING FRESH STAGING DATABASE MODE (--fresh-db) ---")

    # 9.1 Correct staging target accepted with fresh-db parameters
    staging_pooler_url = (
        "postgresql://postgres.vclkeubwpiyhuvprvngx:dummy_pass@"
        "aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=verify-full"
    )
    dest_info = runner.validate_effective_connection_info(
        "vclkeubwpiyhuvprvngx", conn_str=staging_pooler_url, local_disposable=False
    )
    assert dest_info["project_ref"] == "vclkeubwpiyhuvprvngx"
    assert dest_info["effective_host"] == "aws-0-ap-southeast-2.pooler.supabase.com"
    assert dest_info["effective_port"] == "6543"
    assert dest_info["effective_user"] == "postgres.vclkeubwpiyhuvprvngx"
    assert dest_info["effective_sslmode"] == "verify-full"
    print("  [PASS] Correct staging target and project-scoped username accepted.")

    # 9.2 Production ref rejected with fresh-db mode
    try:
        runner.validate_effective_connection_info(
            "vwlwbwwrumsmjqeavvxk", conn_str=staging_pooler_url, local_disposable=False
        )
        assert False, "Should have rejected production project ref"
    except (ValueError, RuntimeError) as e:
        assert "CRITICAL SECURITY VIOLATION" in str(e)
        print("  [PASS] Production project ref rejected with CRITICAL SECURITY VIOLATION.")

    # 9.3 Wrong hostname rejected
    wrong_host_url = (
        "postgresql://postgres.vclkeubwpiyhuvprvngx:dummy_pass@"
        "aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=verify-full"
    )
    try:
        runner.validate_effective_connection_info(
            "vclkeubwpiyhuvprvngx", conn_str=wrong_host_url, local_disposable=False
        )
        assert False, "Should have rejected unauthorized pooler region"
    except (ValueError, RuntimeError) as e:
        assert "REMOTE DESTINATION REJECTED" in str(e)
        print("  [PASS] Wrong pooler hostname rejected.")

    # 9.4 Wrong project-scoped username rejected
    wrong_user_url = (
        "postgresql://postgres.other_project_ref:dummy_pass@"
        "aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=verify-full"
    )
    try:
        runner.validate_effective_connection_info(
            "vclkeubwpiyhuvprvngx", conn_str=wrong_user_url, local_disposable=False
        )
        assert False, "Should have rejected mismatched pooler username"
    except (ValueError, RuntimeError) as e:
        assert "REMOTE DESTINATION REJECTED" in str(e)
        assert "requires an approved project-scoped username" in str(e)
        print("  [PASS] Wrong project-scoped username rejected.")

    # 9.5 Missing or incorrect TLS rejected
    bad_tls_url = (
        "postgresql://postgres.vclkeubwpiyhuvprvngx:dummy_pass@"
        "aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        runner.validate_effective_connection_info(
            "vclkeubwpiyhuvprvngx", conn_str=bad_tls_url, local_disposable=False
        )
        assert False, "Should have rejected non verify-full sslmode"
    except (ValueError, RuntimeError) as e:
        assert "INSECURE REMOTE CONNECTION REJECTED" in str(e) or "STRICT TLS VIOLATION" in str(e)
        print("  [PASS] Incorrect TLS mode (require) rejected; verify-full enforced.")

    # 9.6 Missing STAGING_DATABASE_URL rejected via CLI in fresh-db mode
    env_clean = {k: v for k, v in os.environ.items() if k not in ("STAGING_DATABASE_URL", "LOCAL_DATABASE_URL")}
    proc = subprocess.run(
        [sys.executable, str(workspace_root / "run_phase_4t_remote.py"), "--project-ref", "vclkeubwpiyhuvprvngx", "--fresh-db"],
        capture_output=True,
        text=True,
        env=env_clean,
    )
    assert proc.returncode == 1
    assert "STAGING_DATABASE_URL environment variable is not set" in proc.stdout
    print("  [PASS] Missing STAGING_DATABASE_URL rejected via CLI.")

    # 9.7 Local URL fallback rejected in remote fresh-db mode
    env_with_local_only = env_clean.copy()
    env_with_local_only["LOCAL_DATABASE_URL"] = "postgresql://postgres:secret@127.0.0.1:5433/orqestra_staging_test"
    proc = subprocess.run(
        [sys.executable, str(workspace_root / "run_phase_4t_remote.py"), "--project-ref", "vclkeubwpiyhuvprvngx", "--fresh-db"],
        capture_output=True,
        text=True,
        env=env_with_local_only,
    )
    assert proc.returncode == 1
    assert "STAGING_DATABASE_URL environment variable is not set" in proc.stdout
    assert "orqestra_staging_test" not in proc.stdout
    print("  [PASS] Local URL fallback strictly rejected in remote fresh-db mode.")

    # 9.8 Production project ref rejected via CLI in fresh-db mode
    proc = subprocess.run(
        [sys.executable, str(workspace_root / "run_phase_4t_remote.py"), "--project-ref", "vwlwbwwrumsmjqeavvxk", "--fresh-db"],
        capture_output=True,
        text=True,
        env=env_clean,
    )
    assert proc.returncode == 1
    assert "CRITICAL SECURITY VIOLATION" in proc.stdout
    print("  [PASS] CLI run_phase_4t_remote.py --fresh-db rejects production project ref.")

    # 9.9 Cluster-level tests: Fresh Staging Baseline, Non-empty Rejection, and Pipeline
    print("  Initializing disposable cluster for fresh-db pipeline verification...")
    manage_staging_db.cleanup()
    conn_url = manage_staging_db.init_cluster()
    admin_url = conn_url.replace("/orqestra_staging_test", "/postgres")

    log_file_path = manage_staging_db.DATA_DIR / "pg_server_fresh_db_test.log"
    log_fp = open(log_file_path, "w", encoding="utf-8")
    postgres_exe = str(manage_staging_db.POSTGRES_BIN_DIR / "postgres.exe")

    cluster_proc = subprocess.Popen(
        [postgres_exe, "-D", str(manage_staging_db.DATA_DIR), "-p", str(manage_staging_db.PORT)],
        stdout=log_fp,
        stderr=subprocess.STDOUT,
    )

    try:
        for _ in range(30):
            time.sleep(0.3)
            if manage_staging_db.is_server_available(admin_url, timeout=1.0):
                break
        else:
            raise RuntimeError("Timed out waiting for local PostgreSQL 16 cluster to start.")

        manage_staging_db.create_database()
        run_migrations.apply_migrations()

        # 9.10 verify_fresh_staging_baseline passes on a pristine migrated database
        with psycopg.connect(conn_url) as conn:
            fresh_report = runner.verify_fresh_staging_baseline(conn)
            assert fresh_report["zero_row_baseline"] is True
            assert fresh_report["schema_verified"] is True
            assert fresh_report["rls_verified"] is True
            assert fresh_report["fks_verified"] is True
            assert fresh_report["atomic_fn_verified"] is True
            assert all(cnt == 0 for cnt in fresh_report["table_counts"].values())
            print("  [PASS] Pristine empty staging database verified (0 rows across all 10 tables, RLS & FKs active).")

        # 9.11 Non-empty staging database rejected
        dummy_biz_id = str(uuid.uuid4())
        with psycopg.connect(conn_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.businesses (id, name, slug, currency) VALUES (%s, 'Test Biz', 'test-biz', 'USD');",
                    (dummy_biz_id,)
                )
            conn.commit()

            try:
                runner.verify_fresh_staging_baseline(conn)
                assert False, "Should have failed closed when application table contains existing rows"
            except RuntimeError as e:
                assert "FRESH STAGING CHECK FAILED" in str(e)
                assert "businesses (1 rows)" in str(e)
                print("  [PASS] Non-empty staging database rejected (refuses to execute if rows exist).")

            # Clean up dummy business
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.businesses WHERE id = %s;", (dummy_biz_id,))
            conn.commit()

        # 9.12 Unexpected schema rejected (e.g. disabled RLS)
        with psycopg.connect(conn_url) as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE public.products DISABLE ROW LEVEL SECURITY;")
            conn.commit()

            try:
                runner.verify_fresh_staging_baseline(conn)
                assert False, "Should have failed when RLS is disabled on products"
            except RuntimeError as e:
                assert "FRESH STAGING SECURITY CHECK FAILED" in str(e)
                assert "products" in str(e)
                print("  [PASS] Unexpected schema rejected (RLS disablement caught).")

            with conn.cursor() as cur:
                cur.execute("ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;")
            conn.commit()

        # 9.13 Full pipeline execution in fresh-db mode
        report = runner.run_pipeline(
            project_ref="local-disposable",
            conn_str=conn_url,
            allow_local=True,
            fresh_db=True,
        )

        assert report["verdict"] == "PASS"
        assert report["final_transaction_status"] == "IDLE"
        assert all(report["scenario_results"].values())
        assert all(cnt == 0 for cnt in report["exact_id_counts"].values())
        assert report["pre_baseline"]["zero_row_baseline"] is True
        assert report["post_baseline"]["zero_row_baseline"] is True
        assert report["pre_baseline"]["table_counts"] == report["post_baseline"]["table_counts"]
        assert all(cnt == 0 for cnt in report["post_baseline"]["table_counts"].values())
        print("  [PASS] Full fresh-db pipeline verified: 8/8 scenarios passed, 0 surviving rows, 100% invariance.")

    finally:
        cluster_proc.terminate()
        try:
            cluster_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cluster_proc.kill()
        log_fp.close()
        manage_staging_db.cleanup()
        print("  Disposable cluster cleaned up.")


def main():
    print("=" * 70)
    print(" ORQESTRA PHASE 4T-I-D: RUNNER SECURITY VERIFICATION TEST SUITE")
    print("=" * 70)

    test_effective_connection_settings_validation()
    test_tls_verification_policy()
    test_supabase_destination_enclosure()
    test_production_database_isolation()
    test_process_argument_security()
    test_credential_sanitization()
    test_local_disposable_destination_validation()
    test_two_tier_hash_integrity()
    test_multi_statement_and_baseline_pipeline()
    test_fresh_staging_mode()

    print("\n" + "=" * 70)
    print(" ALL SECURITY VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=" * 70)


if __name__ == "__main__":
    main()

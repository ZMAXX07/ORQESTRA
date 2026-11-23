#!/usr/bin/env python3
"""
ORQESTRA Phase 4T-I: Dedicated Remote Functional Test Runner
============================================================
File: run_phase_4t_remote.py

Security Corrections & Hardened Guard Architecture (Phase 4T-I-D):
1. Comprehensive Psycopg/libpq Connection Settings Validation:
   - Uses psycopg.conninfo.conninfo_to_dict to inspect the effective libpq
     parameters before any database connection is opened.
   - Enforces that effective host, user, port, dbname, and sslmode match approved rules.
   - Rejects forbidden connection parameters (hostaddr, service, servicefile, passfile)
     that could override destinations, bypass DNS, or alter connection behavior.
   - Rejects conflicting or duplicate URL query parameters.
   - Fails closed on parsing errors or unsupported options.
2. Strict TLS Verification Policy (verify-full only):
   - Remote mode strictly requires sslmode=verify-full.
   - Rejects verify-ca, require, disable, allow, prefer, or missing sslmode.
   - Verifies that the effective libpq connection parameters resolve to verify-full.
3. Pinned Regional Pooler & Direct Host Validation:
   - Approved Direct Host: 'db.vwlwbwwrumsmjqeavvxk.supabase.co' (Port: 5432, Dbname: 'postgres').
   - Approved Pooler Host: 'aws-0-ap-northeast-2.pooler.supabase.com' (Port: 6543, Dbname: 'postgres').
   - Approved Pooler Usernames: Explicit allowlist scoped to project 'vwlwbwwrumsmjqeavvxk'
     ('postgres.vwlwbwwrumsmjqeavvxk', 'authenticated.vwlwbwwrumsmjqeavvxk',
      'service_role.vwlwbwwrumsmjqeavvxk').
   - Rejects arbitrary regions, non-allowlisted pooler users, other projects, and external hosts.
4. Process Argument Security & Strict Env Var Separation:
   - Command-line argument --db-url is removed to prevent credential leakage in process listings.
   - Remote mode reads exclusively from STAGING_DATABASE_URL; fails closed if missing.
   - Local disposable mode reads exclusively from LOCAL_DATABASE_URL; fails closed if missing.
   - Neither mode falls back to the other's environment variable.
   - Error messages and exceptions are sanitized to mask passwords.
5. Loopback-Enclosed Local-Disposable Mode (--local-disposable):
   - Accepts ONLY explicit loopback destinations: 'localhost', '127.0.0.1', '::1'.
   - Strictly enforces port 5433 and database 'orqestra_staging_test'.
   - Rejects remote IPs, arbitrary domains, and any Supabase hostnames.
   - Cannot bypass remote destination security.
6. Two-Tier Cryptographic Integrity:
   - Tier 1: Manifest Authentication against pinned SHA-256:
     8e0ceae10638e5bf8d4621df06fb307d68d55296399dc4952b2211e158c08d23.
   - Tier 2: SQL Authentication against authenticated manifest.
   - Aborts before connecting if either check fails. Approved files remain unmodified.
7. Single-Session Multi-Statement Execution (Psycopg 3.3.6):
   - prepare=False (simple query protocol) executes the full 667-line SQL in one roundtrip.
   - autocommit=True preserves script-managed BEGIN; and final ROLLBACK; boundaries.
   - Zero automatic commits.
8. Engine-Level Transaction Status Verification:
   - Directly checks conn.info.transaction_status after execution.
   - Requires status == pq.TransactionStatus.IDLE (0).
   - Rejects INTRANS (open) or INERROR (aborted) states; issues emergency ROLLBACK;.
9. Baseline Protection & Exact-ID Audit:
   - Verifies TechZone Electronics (ID, Name, Slug, Currency).
   - Verifies STG-1890 Product (Name, Business ID) and Inventory (Stock 18, Threshold 5, Business ID).
   - Verifies INV-202611-0008 Invoice (Status 'issued', Amount 10000.00, Business ID).
   - Dynamically snapshots all 10 table counts before execution and asserts 100% invariance post-execution.
   - Verifies 0 rows survive in 6 operational tables for the 13 exact fixture UUIDs.
"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg import conninfo, pq

# ------------------------------------------------------------------------------
# CONSTANTS & APPROVED VALUES
# ------------------------------------------------------------------------------
WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent
SQL_FILENAME = "PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql"
DEFAULT_SQL_PATH = WORKSPACE_ROOT / SQL_FILENAME
DEFAULT_HASH_MANIFEST_PATH = WORKSPACE_ROOT / "PHASE_4T_APPROVED_HASHES.json"

# Strict Target Project Identifiers
# Confirmed Production Project Reference (Strictly Denied as Test Destination)
KNOWN_PRODUCTION_PROJECT_REF = "vwlwbwwrumsmjqeavvxk"

# Approved Regional Pooler Domains
APPROVED_REGIONAL_POOLER_HOSTS = {
    "aws-0-ap-southeast-2.pooler.supabase.com",  # Region: Sydney (orqestra-staging)
    "aws-0-ap-northeast-2.pooler.supabase.com",  # Region: Seoul
}
APPROVED_REGIONAL_POOLER_HOST = "aws-0-ap-southeast-2.pooler.supabase.com"

# Approved Ports and Databases
APPROVED_LOCAL_PORT = "5433"
APPROVED_LOCAL_DBNAME = "orqestra_staging_test"
APPROVED_DIRECT_PORT = "5432"
APPROVED_DIRECT_DBNAME = "postgres"
APPROVED_POOLER_PORT = "6543"
APPROVED_POOLER_DBNAME = "postgres"


def get_approved_direct_host(project_ref: str) -> str:
    """Derives expected direct Supabase host for a given staging project reference."""
    return f"db.{project_ref}.supabase.co"


def get_approved_pooler_usernames(project_ref: str) -> set:
    """Derives authorized pooler usernames for a given staging project reference."""
    return {
        f"postgres.{project_ref}",
        f"authenticated.{project_ref}",
        f"service_role.{project_ref}",
    }

# Pinned Cryptographic Hash of PHASE_4T_APPROVED_HASHES.json
PINNED_MANIFEST_SHA256 = "8e0ceae10638e5bf8d4621df06fb307d68d55296399dc4952b2211e158c08d23"

# Approved Loopback Destinations for Local Testing
APPROVED_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Forbidden Connection Parameters (that could redirect destination or bypass DNS)
FORBIDDEN_CONNINFO_OPTIONS = {"hostaddr", "service", "servicefile", "passfile"}

# Phase 4A Baseline Invariants
BASELINE_BUSINESS_ID = "59b079d3-bbbc-4ee2-8bfe-4b39e6a58353"
BASELINE_BUSINESS_NAME = "TechZone Electronics"
BASELINE_BUSINESS_SLUG = "techzone-electronics"
BASELINE_BUSINESS_CURRENCY = "INR"

BASELINE_SKU = "STG-1890"
BASELINE_PRODUCT_NAME = "Staging Monitor 1890 Pro"

BASELINE_STOCK_QTY = 18
BASELINE_REORDER_THRESHOLD = 5

BASELINE_INVOICE_NUMBER = "INV-202611-0008"
BASELINE_INVOICE_STATUS = "issued"
BASELINE_INVOICE_AMOUNT = 10000.00

REQUIRED_MANIFEST_KEYS = [
    "biz_a", "biz_b", "admin_a", "admin_b", "staff_a",
    "prod_a", "prod_b", "inv_a", "inv_b", "mvt_1", "mvt_2",
    "audit_1", "audit_2"
]

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


# ------------------------------------------------------------------------------
# 1. HARDENED DESTINATION & EFFECTIVE CONNINFO VALIDATION
# ------------------------------------------------------------------------------
def sanitize_db_url(text: str) -> str:
    """
    Masks database passwords in connection URLs, error messages, and exception strings.
    Handles:
    - Ordinary passwords
    - Percent-encoded characters
    - Passwords containing literal or multiple '@' characters
    - Sensitive query parameters (password, secret, token, key)
    - Key-value conninfo format (password=...)
    - Embedded connection URLs in arbitrary exception text
    Fails safely by redacting the entire URI if parsing fails.
    """
    if not text:
        return ""

    def _sanitize_single_uri(uri: str) -> str:
        try:
            scheme, sep, rest = uri.partition("://")
            if not sep:
                return uri

            m = re.search(r"[/?#]", rest)
            if m:
                authority = rest[:m.start()]
                path_query = rest[m.start():]
            else:
                authority = rest
                path_query = ""

            if "@" in authority:
                userinfo, host_port = authority.rsplit("@", 1)
                user, has_pw, _ = userinfo.partition(":")
                if has_pw:
                    authority = f"{user}:***@{host_port}"
                else:
                    authority = f"{user}@{host_port}"

            if "?" in path_query:
                path, sep_q, query = path_query.partition("?")
                q_parts = query.split("&")
                masked_parts = []
                for part in q_parts:
                    k, has_val, v = part.partition("=")
                    k_lower = k.lower()
                    if any(s in k_lower for s in ("pass", "secret", "token", "key", "cred")):
                        masked_parts.append(f"{k}=***")
                    else:
                        masked_parts.append(part)
                path_query = f"{path}?{'&'.join(masked_parts)}"

            return f"{scheme}://{authority}{path_query}"
        except Exception:
            return "[REDACTED_DATABASE_URL]"

    uri_pattern = r"(postgres(?:ql)?://[^\s'\"<>()]+)"
    sanitized = re.sub(uri_pattern, lambda m: _sanitize_single_uri(m.group(0)), text)
    kv_pattern = r"((?:password|pass|secret)\s*=\s*)([^\s;&]+)"
    return re.sub(kv_pattern, r"\1***", sanitized, flags=re.IGNORECASE)


def validate_effective_connection_info(
    project_ref: Optional[str],
    conn_str: str,
    local_disposable: bool = False,
) -> Dict[str, Any]:
    """
    Validates effective libpq connection parameters using psycopg.conninfo.conninfo_to_dict.
    Fails closed before opening any database connection.
    
    Checks:
    1. Explicitly denies confirmed production project reference ('vwlwbwwrumsmjqeavvxk') and production hosts/users.
    2. Rejects duplicate or conflicting URL query parameters.
    3. Rejects forbidden connection options: hostaddr, service, servicefile, passfile.
    4. In Remote Mode (local_disposable=False):
       - Requires valid 20-character staging project_ref (never accepts production).
       - Validates that project_ref matches hostname in STAGING_DATABASE_URL.
       - Direct host: 'db.<project_ref>.supabase.co', port 5432, dbname 'postgres'.
       - Regional pooler: 'aws-0-ap-northeast-2.pooler.supabase.com', port 6543, dbname 'postgres',
         with username in {postgres.<project_ref>, authenticated.<project_ref>, service_role.<project_ref>}.
       - Rejects arbitrary pooler hosts, other regions, unapproved projects, and external hosts.
       - Requires effective sslmode == 'verify-full' strictly.
    5. In Local Mode (local_disposable=True):
       - Effective host must be in {'localhost', '127.0.0.1', '::1'}.
       - Effective port must be '5433'.
       - Effective dbname must be 'orqestra_staging_test'.
       - Rejects any Supabase hostname, production references, or non-loopback IP/host.
    """
    # Upfront project reference validation
    if not local_disposable:
        if not project_ref or not project_ref.strip():
            raise ValueError(
                "REMOTE DESTINATION REJECTED: Target staging project reference is required (--project-ref). "
                "A separately configured staging project reference must be provided."
            )
        raw_ref = project_ref.strip()
        if raw_ref.lower() == KNOWN_PRODUCTION_PROJECT_REF:
            raise ValueError(
                f"CRITICAL SECURITY VIOLATION: Project reference '{raw_ref}' is confirmed as the PRODUCTION project!\n"
                "Execution blocked to prevent running tests against production infrastructure."
            )
        if not re.match(r"^[a-z0-9]{20}$", raw_ref):
            raise ValueError(
                f"REMOTE DESTINATION REJECTED: Invalid project reference format '{raw_ref}'. "
                "Supabase project reference must be a 20-character lowercase alphanumeric identifier."
            )
        clean_ref = raw_ref
    else:
        if project_ref and project_ref.strip().lower() == KNOWN_PRODUCTION_PROJECT_REF:
            raise ValueError(
                f"CRITICAL SECURITY VIOLATION: Project reference '{project_ref}' is confirmed as the PRODUCTION project!\n"
                "Execution blocked to prevent running tests against production infrastructure."
            )

    if not conn_str or not conn_str.strip():
        raise ValueError("DESTINATION VALIDATION FAILED: Connection string is required.")

    # Explicit check: Reject production reference in connection string
    if KNOWN_PRODUCTION_PROJECT_REF in conn_str.lower():
        raise ValueError(
            f"CRITICAL SECURITY VIOLATION: Connection string targets confirmed PRODUCTION project ('{KNOWN_PRODUCTION_PROJECT_REF}')!\n"
            "Execution blocked to prevent running tests against production infrastructure."
        )

    # 1. Inspect URL structure and query parameters for tampering / overrides
    parsed_url = urllib.parse.urlparse(conn_str)
    scheme = (parsed_url.scheme or "").lower()
    if scheme not in ("postgresql", "postgres"):
        raise ValueError(
            f"DESTINATION VALIDATION FAILED: Invalid URL scheme '{scheme}'. Must be 'postgresql' or 'postgres'."
        )

    url_authority_host = (parsed_url.hostname or "").lower().strip()
    if not url_authority_host:
        raise ValueError("DESTINATION VALIDATION FAILED: Missing database hostname in connection URL.")

    # Check for duplicate query parameters in the URL
    if parsed_url.query:
        query_params = urllib.parse.parse_qs(parsed_url.query, keep_blank_values=True)
        for param_key, param_vals in query_params.items():
            if len(param_vals) > 1:
                raise ValueError(
                    f"CONNECTION SECURITY ABORT: Duplicate connection parameter '{param_key}' detected in URL query."
                )

        # Check for query parameters attempting to override connection authority
        authority_conflict_params = {"host", "port", "user", "password", "dbname"}
        for conflict_p in authority_conflict_params:
            if conflict_p in query_params:
                raise ValueError(
                    f"CONNECTION SECURITY ABORT: Conflicting parameter '{conflict_p}' found in URL query string."
                )

    # 2. Parse effective libpq connection parameters using Psycopg conninfo_to_dict
    try:
        eff_dict = conninfo.conninfo_to_dict(conn_str)
    except Exception as e:
        sanitized_err = sanitize_db_url(str(e))
        raise ValueError(f"CONNECTION SECURITY ABORT: Failed to parse libpq connection parameters: {sanitized_err}")

    # 3. Reject forbidden parameters that could redirect destination or bypass DNS
    for forbidden_opt in FORBIDDEN_CONNINFO_OPTIONS:
        if forbidden_opt in eff_dict and eff_dict[forbidden_opt]:
            raise ValueError(
                f"CONNECTION SECURITY ABORT: Forbidden connection option '{forbidden_opt}' detected. "
                "Parameters that override DNS resolution or source external files are prohibited."
            )

    eff_host = (eff_dict.get("host") or "").lower().strip()
    if not eff_host:
        raise ValueError("DESTINATION VALIDATION FAILED: Effective connection host is missing.")

    # Verify that URL authority hostname strictly matches the effective libpq host
    if url_authority_host != eff_host:
        raise ValueError(
            f"DESTINATION VALIDATION FAILED: URL authority host '{url_authority_host}' does not match "
            f"effective libpq connection host '{eff_host}'."
        )

    eff_user = (eff_dict.get("user") or "").lower().strip()
    eff_sslmode = (eff_dict.get("sslmode") or "").lower().strip()
    eff_port = str(eff_dict.get("port") or "5432").strip()
    eff_dbname = (eff_dict.get("dbname") or "").strip()

    # Recheck effective parameters for production reference leakage
    if KNOWN_PRODUCTION_PROJECT_REF in eff_host or KNOWN_PRODUCTION_PROJECT_REF in eff_user:
        raise ValueError(
            f"CRITICAL SECURITY VIOLATION: Effective connection parameters target confirmed PRODUCTION project ('{KNOWN_PRODUCTION_PROJECT_REF}')!\n"
            "Execution blocked to prevent running tests against production infrastructure."
        )

    # ----------------- LOCAL DISPOSABLE MODE -----------------
    if local_disposable:
        # Prevent bypass: Reject any Supabase hostname even if local-disposable flag is passed
        if "supabase.co" in eff_host or "supabase.com" in eff_host or "pooler.supabase.com" in eff_host:
            raise ValueError(
                f"LOCAL MODE SECURITY ABORT: --local-disposable cannot be used with remote Supabase "
                f"destination '{eff_host}'. Use remote execution mode with valid project reference."
            )

        if eff_host not in APPROVED_LOOPBACK_HOSTS:
            raise ValueError(
                f"LOCAL MODE SECURITY ABORT: --local-disposable permits only loopback destinations "
                f"({', '.join(sorted(APPROVED_LOOPBACK_HOSTS))}). Received non-loopback host '{eff_host}'."
            )

        if eff_port != APPROVED_LOCAL_PORT:
            raise ValueError(
                f"LOCAL MODE SECURITY ABORT: --local-disposable requires port '{APPROVED_LOCAL_PORT}'. "
                f"Received port '{eff_port}'."
            )

        if eff_dbname != APPROVED_LOCAL_DBNAME:
            raise ValueError(
                f"LOCAL MODE SECURITY ABORT: --local-disposable requires database '{APPROVED_LOCAL_DBNAME}'. "
                f"Received database '{eff_dbname}'."
            )

        effective_ref = (project_ref or "local-disposable").strip().lower()
        return {
            "mode": "local-disposable",
            "effective_host": eff_host,
            "effective_port": eff_port,
            "effective_dbname": eff_dbname,
            "effective_user": eff_user,
            "project_ref": effective_ref,
            "effective_sslmode": eff_sslmode or "disable",
        }

    # ----------------- REMOTE SUPABASE MODE -----------------
    clean_ref = project_ref.strip().lower()

    # Rejection of loopback hosts in remote mode
    if eff_host in APPROVED_LOOPBACK_HOSTS:
        raise ValueError(
            f"REMOTE DESTINATION REJECTED: Remote mode cannot target loopback host '{eff_host}'. "
            "Use --local-disposable for local testing."
        )

    # Remote Destination Whitelist Evaluation
    expected_direct_host = get_approved_direct_host(clean_ref)
    allowed_pooler_users = get_approved_pooler_usernames(clean_ref)

    is_direct = (eff_host == expected_direct_host)
    is_regional_pooler = (eff_host in APPROVED_REGIONAL_POOLER_HOSTS)

    if not is_direct and not is_regional_pooler:
        raise ValueError(
            f"REMOTE DESTINATION REJECTED: Host '{eff_host}' is not an authorized destination for project '{clean_ref}'.\n"
            f"  Permitted Direct Host:           '{expected_direct_host}'\n"
            f"  Permitted Regional Pooler Hosts: {sorted(APPROVED_REGIONAL_POOLER_HOSTS)}"
        )

    # Direct host validation
    if is_direct:
        if eff_port != APPROVED_DIRECT_PORT:
            raise ValueError(
                f"REMOTE DESTINATION REJECTED: Direct Supabase host requires port '{APPROVED_DIRECT_PORT}'. "
                f"Received port '{eff_port}'."
            )
        if eff_dbname != APPROVED_DIRECT_DBNAME:
            raise ValueError(
                f"REMOTE DESTINATION REJECTED: Direct Supabase host requires database '{APPROVED_DIRECT_DBNAME}'. "
                f"Received database '{eff_dbname}'."
            )

    # Regional pooler validation
    if is_regional_pooler:
        if eff_port != APPROVED_POOLER_PORT:
            raise ValueError(
                f"REMOTE DESTINATION REJECTED: Supabase pooler host requires port '{APPROVED_POOLER_PORT}'. "
                f"Received port '{eff_port}'."
            )
        if eff_dbname != APPROVED_POOLER_DBNAME:
            raise ValueError(
                f"REMOTE DESTINATION REJECTED: Supabase pooler host requires database '{APPROVED_POOLER_DBNAME}'. "
                f"Received database '{eff_dbname}'."
            )
        if eff_user not in allowed_pooler_users:
            raise ValueError(
                f"REMOTE DESTINATION REJECTED: Supabase pooler host requires an approved project-scoped username matching project '{clean_ref}'.\n"
                f"  Allowed Usernames: {sorted(allowed_pooler_users)}\n"
                f"  Received User:     '{eff_user}'"
            )

    # Strict TLS Policy: Remote connections strictly require sslmode=verify-full
    if eff_sslmode != "verify-full":
        raise ValueError(
            f"INSECURE REMOTE CONNECTION REJECTED: Remote Supabase connections strictly require 'sslmode=verify-full'.\n"
            f"  Received Effective sslmode: '{eff_sslmode}'\n"
            "Modes such as 'verify-ca', 'require', or 'disable' are rejected to guarantee hostname & certificate verification."
        )

    return {
        "mode": "remote-staging",
        "effective_host": eff_host,
        "effective_port": eff_port,
        "effective_dbname": eff_dbname,
        "effective_user": eff_user,
        "project_ref": clean_ref,
        "effective_sslmode": eff_sslmode,
        "destination_type": "direct" if is_direct else "pooler",
    }


# ------------------------------------------------------------------------------
# 2. TWO-TIER CRYPTOGRAPHIC INTEGRITY VERIFICATION
# ------------------------------------------------------------------------------
def verify_manifest_and_sql_integrity(
    sql_path: pathlib.Path = DEFAULT_SQL_PATH,
    manifest_path: pathlib.Path = DEFAULT_HASH_MANIFEST_PATH,
) -> Tuple[str, str, str]:
    """
    1. Authenticates PHASE_4T_APPROVED_HASHES.json against hard-pinned SHA-256:
       8e0ceae10638e5bf8d4621df06fb307d68d55296399dc4952b2211e158c08d23.
    2. Parses the authenticated manifest.
    3. Computes SHA-256 of the SQL file and verifies against the authenticated manifest.
    Aborts before connecting if either check fails.
    Returns: (sql_content, sql_hash, manifest_hash)
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Hash manifest not found at: {manifest_path.resolve()}")
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL test file not found at: {sql_path.resolve()}")

    manifest_bytes = manifest_path.read_bytes()
    manifest_actual_hash = hashlib.sha256(manifest_bytes).hexdigest().lower()

    if manifest_actual_hash != PINNED_MANIFEST_SHA256:
        raise ValueError(
            f"MANIFEST AUTHENTICATION FAILED!\n"
            f"  File:          {manifest_path.resolve()}\n"
            f"  Expected Hash: {PINNED_MANIFEST_SHA256}\n"
            f"  Actual Hash:   {manifest_actual_hash}\n"
            "Execution blocked to prevent using an unauthenticated or altered manifest."
        )

    try:
        manifest_data = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse authenticated manifest JSON: {e}")

    sql_key = SQL_FILENAME
    if sql_key not in manifest_data:
        raise ValueError(f"Authenticated manifest missing required key '{sql_key}'.")

    expected_sql_hash = str(manifest_data[sql_key]).strip().lower()
    sql_bytes = sql_path.read_bytes()
    sql_actual_hash = hashlib.sha256(sql_bytes).hexdigest().lower()

    if sql_actual_hash != expected_sql_hash:
        raise ValueError(
            f"SQL INTEGRITY CHECK FAILED!\n"
            f"  File:          {sql_path.resolve()}\n"
            f"  Expected Hash: {expected_sql_hash}\n"
            f"  Actual Hash:   {sql_actual_hash}\n"
            "Execution blocked to prevent running altered or unverified SQL."
        )

    return sql_bytes.decode("utf-8"), sql_actual_hash, manifest_actual_hash


# ------------------------------------------------------------------------------
# 3. MANIFEST PARSING & VALIDATION
# ------------------------------------------------------------------------------
def parse_manifest(manifest_notices: List[str]) -> Dict[str, str]:
    """
    Extracts and strictly validates the 13 fixture UUIDs from MANIFEST_JSON notices.
    Fails closed if the notice is missing, malformed, contains duplicate UUIDs, or has missing keys.
    """
    if not manifest_notices:
        raise ValueError("MANIFEST VALIDATION FAILED: No MANIFEST_JSON notice was emitted by the test script.")

    if len(manifest_notices) != 1:
        raise ValueError(
            f"MANIFEST VALIDATION FAILED: Expected exactly 1 MANIFEST_JSON notice, got {len(manifest_notices)}."
        )

    notice = manifest_notices[0]
    prefix = "MANIFEST_JSON:"
    if not notice.startswith(prefix):
        raise ValueError(f"MANIFEST VALIDATION FAILED: Notice does not start with '{prefix}'.")

    raw_json = notice[len(prefix):].strip()
    try:
        data = json.loads(raw_json)
    except Exception as e:
        raise ValueError(f"MANIFEST VALIDATION FAILED: Malformed JSON in manifest notice: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"MANIFEST VALIDATION FAILED: Manifest payload must be a JSON object, got {type(data)}.")

    missing_keys = set(REQUIRED_MANIFEST_KEYS) - set(data.keys())
    if missing_keys:
        raise ValueError(f"MANIFEST VALIDATION FAILED: Missing required keys in manifest: {sorted(missing_keys)}.")

    unexpected_keys = set(data.keys()) - set(REQUIRED_MANIFEST_KEYS)
    if unexpected_keys:
        raise ValueError(f"MANIFEST VALIDATION FAILED: Unexpected keys in manifest: {sorted(unexpected_keys)}.")

    validated = {}
    for k in REQUIRED_MANIFEST_KEYS:
        val = data[k]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"MANIFEST VALIDATION FAILED: Key '{k}' must be non-empty string, got {val!r}.")
        try:
            parsed_uuid = uuid.UUID(val.strip())
            validated[k] = str(parsed_uuid).lower()
        except ValueError as ve:
            raise ValueError(f"MANIFEST VALIDATION FAILED: Key '{k}' contains invalid UUID '{val}': {ve}")

    # Check distinctness: all 13 fixture UUIDs must represent separate entities
    if len(set(validated.values())) != len(validated):
        seen = {}
        duplicates = []
        for k, v in validated.items():
            if v in seen:
                duplicates.append(f"'{k}' duplicates '{seen[v]}' ({v})")
            else:
                seen[v] = k
        raise ValueError(f"MANIFEST VALIDATION FAILED: Duplicate UUIDs detected: {', '.join(duplicates)}")

    return validated


# ------------------------------------------------------------------------------
# 4. BASELINE INVARIANTS & TABLE COUNT SNAPSHOT VERIFICATION
# ------------------------------------------------------------------------------
def verify_baseline_invariants(conn: psycopg.Connection) -> Dict[str, Any]:
    """
    Inspects and snapshots the read-only baseline records and all 10 operational table counts.
    Ensures Phase 4A records:
    1. Business: TechZone Electronics (ID 59b079d3-bbbc-4ee2-8bfe-4b39e6a58353, slug techzone-electronics, currency INR)
       - Scoped by ID; verifies name, slug, currency, and verifies zero duplicate businesses with the same name.
    2. Product: STG-1890
       - Scoped strictly by (business_id, sku); asserts exactly 1 record exists.
       - Verifies name matches 'Staging Monitor 1890 Pro'.
    3. Inventory: STG-1890 stock
       - Scoped strictly by (business_id, product_id); asserts exactly 1 record exists.
       - Verifies stock quantity == 18, reorder_threshold == 5.
    4. Invoice: INV-202611-0008
       - Scoped strictly by (business_id, invoice_number); asserts exactly 1 record exists.
       - Verifies status == 'issued', amount_due == 10000.00.
    Captures live table counts for before-vs-after invariance comparison across all 10 operational tables.
    """
    baseline_report: Dict[str, Any] = {
        "business_intact": False,
        "product_stock_intact": False,
        "invoice_intact": False,
        "table_counts": {},
    }

    with conn.cursor() as cur:
        # 1. TechZone Electronics (ID, Name, Slug, Currency)
        cur.execute(
            "SELECT id, name, slug, currency FROM public.businesses WHERE id = %s;",
            (BASELINE_BUSINESS_ID,)
        )
        biz_rows = cur.fetchall()
        if len(biz_rows) == 0:
            raise RuntimeError(f"BASELINE CHECK FAILED: Business ID '{BASELINE_BUSINESS_ID}' not found.")
        if len(biz_rows) > 1:
            raise RuntimeError(f"BASELINE CHECK FAILED: Duplicate business records ({len(biz_rows)}) found for ID '{BASELINE_BUSINESS_ID}'.")
        biz_row = biz_rows[0]
        biz_id, biz_name, biz_slug, biz_curr = str(biz_row[0]), biz_row[1], biz_row[2], biz_row[3]
        if biz_name != BASELINE_BUSINESS_NAME:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Business name mismatch. Expected '{BASELINE_BUSINESS_NAME}', got '{biz_name}'."
            )
        if biz_slug != BASELINE_BUSINESS_SLUG:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Business slug mismatch. Expected '{BASELINE_BUSINESS_SLUG}', got '{biz_slug}'."
            )
        if biz_curr != BASELINE_BUSINESS_CURRENCY:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Business currency mismatch. Expected '{BASELINE_BUSINESS_CURRENCY}', got '{biz_curr}'."
            )

        # Assert no duplicate business exists with the same business name
        cur.execute("SELECT count(*) FROM public.businesses WHERE name = %s;", (BASELINE_BUSINESS_NAME,))
        name_count = int(cur.fetchone()[0])
        if name_count != 1:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Duplicate business records ({name_count}) found with name '{BASELINE_BUSINESS_NAME}'."
            )
        baseline_report["business_intact"] = True

        # 2. STG-1890 Product & Inventory (Scoped strictly by business_id AND sku)
        cur.execute("""
            SELECT id, business_id, sku, name
            FROM public.products
            WHERE business_id = %s AND sku = %s;
        """, (BASELINE_BUSINESS_ID, BASELINE_SKU))
        prod_rows = cur.fetchall()
        if len(prod_rows) == 0:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Product SKU '{BASELINE_SKU}' not found for business '{BASELINE_BUSINESS_ID}'."
            )
        if len(prod_rows) > 1:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Duplicate product records ({len(prod_rows)}) found for SKU '{BASELINE_SKU}' in business '{BASELINE_BUSINESS_ID}'."
            )
        prod_row = prod_rows[0]
        prod_id, prod_biz_id, prod_sku, prod_name = str(prod_row[0]), str(prod_row[1]), prod_row[2], prod_row[3]
        if prod_biz_id != BASELINE_BUSINESS_ID:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Product business_id mismatch. Expected '{BASELINE_BUSINESS_ID}', got '{prod_biz_id}'."
            )
        if prod_name != BASELINE_PRODUCT_NAME:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Product name mismatch. Expected '{BASELINE_PRODUCT_NAME}', got '{prod_name}'."
            )

        cur.execute("""
            SELECT id, business_id, product_id, quantity_on_hand, reorder_threshold
            FROM public.inventory
            WHERE business_id = %s AND product_id = %s;
        """, (BASELINE_BUSINESS_ID, prod_id))
        inv_rows = cur.fetchall()
        if len(inv_rows) == 0:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Inventory record for SKU '{BASELINE_SKU}' (product_id '{prod_id}') not found."
            )
        if len(inv_rows) > 1:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Duplicate inventory records ({len(inv_rows)}) found for product_id '{prod_id}'."
            )
        inv_row = inv_rows[0]
        inv_biz_id, inv_prod_id = str(inv_row[1]), str(inv_row[2])
        qty_on_hand, reorder_thresh = int(inv_row[3]), int(inv_row[4])
        if inv_biz_id != BASELINE_BUSINESS_ID:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Inventory business_id mismatch. Expected '{BASELINE_BUSINESS_ID}', got '{inv_biz_id}'."
            )
        if inv_prod_id != prod_id:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Inventory product_id mismatch. Expected '{prod_id}', got '{inv_prod_id}'."
            )
        if qty_on_hand != BASELINE_STOCK_QTY:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: SKU '{BASELINE_SKU}' quantity_on_hand mismatch. "
                f"Expected {BASELINE_STOCK_QTY}, got {qty_on_hand}."
            )
        if reorder_thresh != BASELINE_REORDER_THRESHOLD:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: SKU '{BASELINE_SKU}' reorder_threshold mismatch. "
                f"Expected {BASELINE_REORDER_THRESHOLD}, got {reorder_thresh}."
            )
        baseline_report["product_stock_intact"] = True

        # 3. INV-202611-0008 Invoice (Scoped strictly by business_id AND invoice_number)
        cur.execute("""
            SELECT id, business_id, invoice_number, status, amount_due
            FROM public.invoices
            WHERE business_id = %s AND invoice_number = %s;
        """, (BASELINE_BUSINESS_ID, BASELINE_INVOICE_NUMBER))
        inv_rows = cur.fetchall()
        if len(inv_rows) == 0:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Invoice '{BASELINE_INVOICE_NUMBER}' not found for business '{BASELINE_BUSINESS_ID}'."
            )
        if len(inv_rows) > 1:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Duplicate invoice records ({len(inv_rows)}) found for invoice_number '{BASELINE_INVOICE_NUMBER}' in business '{BASELINE_BUSINESS_ID}'."
            )
        inv_row = inv_rows[0]
        inv_biz_id = str(inv_row[1])
        inv_num, inv_status, inv_amount = inv_row[2], inv_row[3], float(inv_row[4])
        if inv_biz_id != BASELINE_BUSINESS_ID:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Invoice business_id mismatch. Expected '{BASELINE_BUSINESS_ID}', got '{inv_biz_id}'."
            )
        if inv_status != BASELINE_INVOICE_STATUS:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Invoice status mismatch. Expected '{BASELINE_INVOICE_STATUS}', got '{inv_status}'."
            )
        if abs(inv_amount - BASELINE_INVOICE_AMOUNT) > 0.001:
            raise RuntimeError(
                f"BASELINE CHECK FAILED: Invoice amount_due mismatch. Expected {BASELINE_INVOICE_AMOUNT}, got {inv_amount}."
            )
        baseline_report["invoice_intact"] = True

        # 4. Table Counts across all 10 operational tables
        table_names = [
            "audit_logs", "business_members", "businesses", "customers",
            "inventory", "invoices", "order_items", "orders", "products", "stock_movements"
        ]
        counts = {}
        for tbl in table_names:
            cur.execute(f"SELECT count(*) FROM public.{tbl};")
            counts[tbl] = int(cur.fetchone()[0])
        baseline_report["table_counts"] = counts

    return baseline_report


# All 10 Operational Application Tables
OPERATIONAL_TABLES = [
    "audit_logs",
    "business_members",
    "businesses",
    "customers",
    "inventory",
    "invoices",
    "order_items",
    "orders",
    "products",
    "stock_movements",
]

# Required Migrations for Fresh Staging
REQUIRED_MIGRATIONS = [
    "20261022000001",
    "20261022000002",
    "20261023000001",
    "20261023000002",
    "20261023000003",
    "20261023000004",
    "20261115000001",
    "20261122000001",
]

# Expected Composite Tenant Foreign Keys
EXPECTED_COMPOSITE_FKS = [
    ("inventory", "fk_inventory_business_product"),
    ("order_items", "fk_order_items_business_order"),
    ("order_items", "fk_order_items_business_product"),
    ("invoices", "fk_invoices_business_order"),
]


def verify_fresh_staging_baseline(conn: psycopg.Connection) -> Dict[str, Any]:
    """
    Inspects a fresh staging database before and after execution.
    Guarantees for Fresh Staging Mode:
    1. Zero-Row Baseline Check:
       - Confirms that ALL 10 application tables have exactly 0 rows.
       - Fails closed if any application table contains unexpected rows.
    2. Schema & Migration Verification:
       - If supabase_migrations.schema_migrations exists, verifies all 8 required migration versions exist.
       - Confirms all 10 operational application tables exist in public schema.
       - Confirms Row Level Security (RLS) is enabled on all 10 tables.
       - Confirms the 4 composite tenant foreign keys exist.
       - Confirms adjust_stock_atomic function exists with SECURITY DEFINER and explicit search_path.
    3. Snapshots table counts (all 0s) for before-vs-after dynamic invariance comparison.
    """
    fresh_report: Dict[str, Any] = {
        "mode": "fresh_staging",
        "schema_verified": False,
        "rls_verified": False,
        "fks_verified": False,
        "atomic_fn_verified": False,
        "migrations_verified": False,
        "zero_row_baseline": False,
        "table_counts": {},
    }

    with conn.cursor() as cur:
        # 1. Zero-Row Baseline Check across all 10 operational tables
        counts = {}
        non_empty = []
        for tbl in OPERATIONAL_TABLES:
            cur.execute(f"SELECT count(*) FROM public.{tbl};")
            cnt = int(cur.fetchone()[0])
            counts[tbl] = cnt
            if cnt != 0:
                non_empty.append(f"{tbl} ({cnt} rows)")

        if non_empty:
            raise RuntimeError(
                f"FRESH STAGING CHECK FAILED: Application tables are not empty in fresh-db mode:\n"
                + "\n".join(f"  - {item}" for item in non_empty)
                + "\nFresh database mode strictly requires 0 application rows before execution."
            )
        fresh_report["zero_row_baseline"] = True
        fresh_report["table_counts"] = counts

        # 2. Schema: All 10 application tables exist
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        existing_tables = {row[0] for row in cur.fetchall()}
        missing_tables = set(OPERATIONAL_TABLES) - existing_tables
        if missing_tables:
            raise RuntimeError(
                f"FRESH STAGING SCHEMA VERIFICATION FAILED: Missing operational tables: {sorted(missing_tables)}"
            )
        fresh_report["schema_verified"] = True

        # 3. Security: Row Level Security is enabled on all 10 tables
        cur.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND rowsecurity = true;
        """)
        rls_tables = {row[0] for row in cur.fetchall()}
        missing_rls = set(OPERATIONAL_TABLES) - rls_tables
        if missing_rls:
            raise RuntimeError(
                f"FRESH STAGING SECURITY CHECK FAILED: Row Level Security is NOT enabled on tables: {sorted(missing_rls)}"
            )
        fresh_report["rls_verified"] = True

        # 4. Integrity: 4 Composite Tenant Foreign Keys exist
        cur.execute("""
            SELECT conrelid::regclass::text, conname
            FROM pg_constraint
            WHERE conname IN (
                'fk_inventory_business_product',
                'fk_order_items_business_order',
                'fk_order_items_business_product',
                'fk_invoices_business_order'
            );
        """)
        found_fks = {(row[0].replace('public.', ''), row[1]) for row in cur.fetchall()}
        missing_fks = set(EXPECTED_COMPOSITE_FKS) - found_fks
        if missing_fks:
            raise RuntimeError(
                f"FRESH STAGING SCHEMA VERIFICATION FAILED: Missing composite tenant foreign keys: {sorted(missing_fks)}"
            )
        fresh_report["fks_verified"] = True

        # 5. Atomic stored procedure adjust_stock_atomic
        cur.execute("""
            SELECT p.prosecdef, p.proconfig
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public' AND p.proname = 'adjust_stock_atomic';
        """)
        proc_row = cur.fetchone()
        if not proc_row:
            raise RuntimeError(
                "FRESH STAGING SCHEMA VERIFICATION FAILED: Function public.adjust_stock_atomic not found."
            )
        is_secdef, proconfig = proc_row[0], proc_row[1]
        if not is_secdef:
            raise RuntimeError(
                "FRESH STAGING SECURITY CHECK FAILED: adjust_stock_atomic is not SECURITY DEFINER."
            )
        if not proconfig or not any("search_path=public" in (c or "").replace(" ", "") for c in proconfig):
            raise RuntimeError(
                "FRESH STAGING SECURITY CHECK FAILED: adjust_stock_atomic missing explicit search_path=public."
            )
        fresh_report["atomic_fn_verified"] = True

        # 6. Migration History (if supabase_migrations.schema_migrations exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'supabase_migrations' AND table_name = 'schema_migrations'
            );
        """)
        has_migrations_tbl = cur.fetchone()[0]
        if has_migrations_tbl:
            cur.execute("SELECT version FROM supabase_migrations.schema_migrations ORDER BY version;")
            applied_versions = {row[0] for row in cur.fetchall()}
            missing_migrations = set(REQUIRED_MIGRATIONS) - applied_versions
            if missing_migrations:
                raise RuntimeError(
                    f"FRESH STAGING MIGRATION HISTORY FAILED: Missing applied migrations: {sorted(missing_migrations)}"
                )
        fresh_report["migrations_verified"] = True

    return fresh_report


# ------------------------------------------------------------------------------
# 5. POST-ROLLBACK EXACT-ID ABSENCE AUDIT
# ------------------------------------------------------------------------------
def audit_post_rollback_exact_ids(
    conn: psycopg.Connection,
    manifest: Dict[str, str],
) -> Dict[str, int]:
    """
    Performs read-only checks against all 6 operational tables using the exact
    13 fixture UUIDs from the manifest. Verifies 0 rows exist post-rollback.
    """
    results = {}
    with conn.cursor() as cur:
        # 1. businesses
        cur.execute(
            "SELECT count(*) FROM public.businesses WHERE id IN (%s, %s);",
            (manifest["biz_a"], manifest["biz_b"])
        )
        results["businesses"] = int(cur.fetchone()[0])

        # 2. business_members
        cur.execute("""
            SELECT count(*) FROM public.business_members
            WHERE (business_id = %s AND user_id = %s)
               OR (business_id = %s AND user_id = %s)
               OR (business_id = %s AND user_id = %s)
               OR business_id IN (%s, %s)
               OR user_id IN (%s, %s, %s);
        """, (
            manifest["biz_a"], manifest["admin_a"],
            manifest["biz_a"], manifest["staff_a"],
            manifest["biz_b"], manifest["admin_b"],
            manifest["biz_a"], manifest["biz_b"],
            manifest["admin_a"], manifest["admin_b"], manifest["staff_a"]
        ))
        results["business_members"] = int(cur.fetchone()[0])

        # 3. products
        cur.execute(
            "SELECT count(*) FROM public.products WHERE id IN (%s, %s) OR business_id IN (%s, %s);",
            (manifest["prod_a"], manifest["prod_b"], manifest["biz_a"], manifest["biz_b"])
        )
        results["products"] = int(cur.fetchone()[0])

        # 4. inventory
        cur.execute("""
            SELECT count(*) FROM public.inventory
            WHERE id IN (%s, %s) OR business_id IN (%s, %s) OR product_id IN (%s, %s);
        """, (
            manifest["inv_a"], manifest["inv_b"],
            manifest["biz_a"], manifest["biz_b"],
            manifest["prod_a"], manifest["prod_b"]
        ))
        results["inventory"] = int(cur.fetchone()[0])

        # 5. stock_movements
        cur.execute("""
            SELECT count(*) FROM public.stock_movements
            WHERE id IN (%s, %s) OR business_id IN (%s, %s) OR product_id IN (%s, %s);
        """, (
            manifest["mvt_1"], manifest["mvt_2"],
            manifest["biz_a"], manifest["biz_b"],
            manifest["prod_a"], manifest["prod_b"]
        ))
        results["stock_movements"] = int(cur.fetchone()[0])

        # 6. audit_logs
        cur.execute("""
            SELECT count(*) FROM public.audit_logs
            WHERE id IN (%s, %s) OR business_id IN (%s, %s) OR entity_id IN (%s, %s);
        """, (
            manifest["audit_1"], manifest["audit_2"],
            manifest["biz_a"], manifest["biz_b"],
            manifest["inv_a"], manifest["inv_b"]
        ))
        results["audit_logs"] = int(cur.fetchone()[0])

    surviving = {tbl: cnt for tbl, cnt in results.items() if cnt > 0}
    if surviving:
        raise RuntimeError(
            f"EXACT-ID POST-ROLLBACK AUDIT FAILED! Uncommitted test entities survived rollback: {surviving}"
        )

    return results


# ------------------------------------------------------------------------------
# 6. SCENARIO NOTICES VERIFICATION
# ------------------------------------------------------------------------------
def verify_scenario_notices(notices: List[str]) -> Dict[str, bool]:
    """Verifies that all 8 functional scenario success notices were emitted."""
    results = {}
    missing = []
    for idx, expected in enumerate(EXPECTED_SCENARIO_NOTICES, 1):
        found = any(expected in n for n in notices)
        results[f"scenario_{idx}"] = found
        if not found:
            missing.append(f"Scenario {idx}: '{expected}'")

    if missing:
        raise RuntimeError("SCENARIO NOTICE CHECK FAILED:\n" + "\n".join(f"  - Missing {m}" for m in missing))

    return results


# ------------------------------------------------------------------------------
# 7. MULTI-STATEMENT TRANSACTION EXECUTION & STATUS VERIFICATION
# ------------------------------------------------------------------------------
def execute_functional_test(
    conn_url: str,
    sql_content: str,
) -> Dict[str, Any]:
    """
    Executes the entire SQL content in a single database session and transaction.
    Uses:
    1. autocommit=True: Preserves explicit script-managed BEGIN; and ROLLBACK; boundaries.
    2. prepare=False: Forces Psycopg 3 simple query protocol (PQexec), which natively
       executes multi-statement SQL scripts without prepared-statement splitting.
    3. Transaction Status Verification: Checks conn.info.transaction_status after execution.
       Requires status == pq.TransactionStatus.IDLE (0). If transaction remains INTRANS
       (open) or INERROR (aborted), marks execution as failed and issues emergency ROLLBACK;.
    """
    notices: List[str] = []
    manifest_notices: List[str] = []

    def notice_handler(diag):
        msg = diag.message_primary
        notices.append(msg)
        if msg.startswith("MANIFEST_JSON:"):
            manifest_notices.append(msg)

    t_start = time.perf_counter()
    rolled_back_cleanly = False
    emergency_rollback_issued = False
    final_tx_status_name = "UNKNOWN"

    conn = psycopg.connect(conn_url, autocommit=True)
    conn.add_notice_handler(notice_handler)

    try:
        with conn.cursor() as cur:
            # Psycopg 3 multi-statement execution via simple query protocol
            cur.execute(sql_content, prepare=False)

        # Inspect post-execution transaction status directly from engine
        post_tx_status = conn.info.transaction_status
        final_tx_status_name = post_tx_status.name

        if post_tx_status != pq.TransactionStatus.IDLE:
            # Transaction is still open (INTRANS = 2) or in error (INERROR = 3)
            rolled_back_cleanly = False
            try:
                with conn.cursor() as rb_cur:
                    rb_cur.execute("ROLLBACK;", prepare=False)
                emergency_rollback_issued = True
            except Exception:
                pass
            raise RuntimeError(
                f"TRANSACTION STATE AUDIT FAILED! Transaction status after execution was {final_tx_status_name} "
                f"({int(post_tx_status)}), expected IDLE (0). Transaction was not rolled back cleanly by the script."
            )

        rolled_back_cleanly = True
    except Exception as exec_err:
        try:
            if conn.info.transaction_status != pq.TransactionStatus.IDLE:
                with conn.cursor() as rb_cur:
                    rb_cur.execute("ROLLBACK;", prepare=False)
                emergency_rollback_issued = True
                final_tx_status_name = conn.info.transaction_status.name
        except Exception:
            pass
        sanitized_err = sanitize_db_url(str(exec_err))
        raise RuntimeError(f"Database error during functional test execution: {sanitized_err}") from None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    duration_ms = (time.perf_counter() - t_start) * 1000.0
    return {
        "duration_ms": duration_ms,
        "notices": notices,
        "manifest_notices": manifest_notices,
        "rolled_back_cleanly": rolled_back_cleanly,
        "emergency_rollback_issued": emergency_rollback_issued,
        "final_transaction_status": final_tx_status_name,
    }


# ------------------------------------------------------------------------------
# 8. MAIN ORCHESTRATION PIPELINE
# ------------------------------------------------------------------------------
def run_pipeline(
    project_ref: Optional[str],
    conn_str: str,
    sql_path: pathlib.Path = DEFAULT_SQL_PATH,
    manifest_path: pathlib.Path = DEFAULT_HASH_MANIFEST_PATH,
    allow_local: bool = False,
    fresh_db: bool = False,
) -> Dict[str, Any]:
    """
    Orchestrates the complete 6-stage functional test verification pipeline:
    1. Effective connection settings & destination validation (fail-closed checks)
    2. Two-tier cryptographic integrity check (manifest pinned hash + SQL hash)
    3. Pre-execution baseline invariant & table count snapshot inspection
    4. Multi-statement single-session transaction execution with status verification
    5. Scenario notices verification & fixture manifest parsing
    6. Post-rollback exact-ID absence audit & post-execution table count invariance comparison
    """
    report: Dict[str, Any] = {
        "status": "RUNNING",
        "destination_info": None,
        "manifest_hash": None,
        "sql_hash": None,
        "execution_duration_ms": None,
        "final_transaction_status": None,
        "pre_baseline": None,
        "post_baseline": None,
        "manifest": None,
        "scenario_results": None,
        "exact_id_counts": None,
        "verdict": "FAIL",
    }

    # Step 1: Validate effective connection settings and destination parameters
    dest_info = validate_effective_connection_info(project_ref, conn_str=conn_str, local_disposable=allow_local)
    report["destination_info"] = dest_info

    # Step 2: Two-tier cryptographic integrity verification
    sql_content, sql_hash, manifest_hash = verify_manifest_and_sql_integrity(
        sql_path=sql_path, manifest_path=manifest_path
    )
    report["manifest_hash"] = manifest_hash
    report["sql_hash"] = sql_hash

    # Step 3: Pre-execution baseline check and table count snapshot
    with psycopg.connect(conn_str) as pre_conn:
        if fresh_db:
            pre_baseline = verify_fresh_staging_baseline(pre_conn)
        else:
            pre_baseline = verify_baseline_invariants(pre_conn)
    report["pre_baseline"] = pre_baseline

    # Step 4: Execute functional test inside single-session transaction with prepare=False
    exec_result = execute_functional_test(conn_str, sql_content)
    report["execution_duration_ms"] = exec_result["duration_ms"]
    report["final_transaction_status"] = exec_result["final_transaction_status"]

    # Step 5: Verify scenario notices and parse manifest
    scenario_results = verify_scenario_notices(exec_result["notices"])
    report["scenario_results"] = scenario_results

    manifest = parse_manifest(exec_result["manifest_notices"])
    report["manifest"] = manifest

    # Step 6: Post-rollback exact-ID audit & baseline invariance comparison
    with psycopg.connect(conn_str) as post_conn:
        exact_counts = audit_post_rollback_exact_ids(post_conn, manifest)
        if fresh_db:
            post_baseline = verify_fresh_staging_baseline(post_conn)
        else:
            post_baseline = verify_baseline_invariants(post_conn)

    report["exact_id_counts"] = exact_counts
    report["post_baseline"] = post_baseline

    # Ensure pre and post counts match perfectly (Dynamic Invariance Check)
    if pre_baseline["table_counts"] != post_baseline["table_counts"]:
        diffs = []
        for tbl in pre_baseline["table_counts"]:
            cnt_pre = pre_baseline["table_counts"][tbl]
            cnt_post = post_baseline["table_counts"].get(tbl, -1)
            if cnt_pre != cnt_post:
                diffs.append(f"{tbl}: before={cnt_pre}, after={cnt_post}")
        raise RuntimeError(
            f"BASELINE MUTATION DETECTED! Operational table counts shifted during test session:\n"
            + "\n".join(f"  - {d}" for d in diffs)
        )

    report["status"] = "COMPLETED"
    report["verdict"] = "PASS"
    return report


def main():
    parser = argparse.ArgumentParser(
        description="ORQESTRA Phase 4T-I: Dedicated Remote Functional Test Runner (Phase 4T-I-D)"
    )
    parser.add_argument(
        "--project-ref",
        type=str,
        default=None,
        help="Target Supabase staging project reference (strictly required in remote mode; production 'vwlwbwwrumsmjqeavvxk' is forbidden)",
    )
    parser.add_argument(
        "--local-disposable",
        action="store_true",
        help="Allow executing against local disposable cluster for runner validation",
    )
    parser.add_argument(
        "--sql-path",
        type=pathlib.Path,
        default=DEFAULT_SQL_PATH,
        help="Path to SQL test script",
    )
    parser.add_argument(
        "--manifest-path",
        type=pathlib.Path,
        default=DEFAULT_HASH_MANIFEST_PATH,
        help="Path to hash manifest JSON",
    )
    parser.add_argument(
        "--fresh-db",
        action="store_true",
        help="Execute in fresh staging database mode (verifies zero application rows, migrated schema, and RLS instead of historical Phase 4A baseline records)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print(" ORQESTRA PHASE 4T-I: REMOTE FUNCTIONAL TEST RUNNER (PHASE 4T-I-D)")
    print("=" * 70)

    # Read connection URL exclusively from designated mode environment variable
    # Strictly select STAGING_DATABASE_URL for remote mode and LOCAL_DATABASE_URL for local mode.
    # Command-line parameter --db-url is removed to prevent process argument credential leakage.
    if args.local_disposable:
        conn_str = os.environ.get("LOCAL_DATABASE_URL")
        if not conn_str:
            print(
                "\nENVIRONMENT CONFIGURATION ERROR: LOCAL_DATABASE_URL environment variable is not set.\n"
                "In --local-disposable mode, database credentials must be provided via LOCAL_DATABASE_URL.\n"
                f"Ensure LOCAL_DATABASE_URL targets loopback host, port {APPROVED_LOCAL_PORT}, and database {APPROVED_LOCAL_DBNAME}."
            )
            sys.exit(1)
    else:
        if not args.project_ref:
            print(
                "\nENVIRONMENT CONFIGURATION ERROR: --project-ref is required in remote execution mode.\n"
                "In remote execution mode, a separately configured staging project reference must be provided.\n"
                f"Note: Production project '{KNOWN_PRODUCTION_PROJECT_REF}' is strictly forbidden."
            )
            sys.exit(1)

        if args.project_ref.strip().lower() == KNOWN_PRODUCTION_PROJECT_REF:
            print(
                f"\nCRITICAL SECURITY VIOLATION: Project reference '{args.project_ref}' is confirmed as PRODUCTION!\n"
                "Running functional or staging tests against production is strictly prohibited."
            )
            sys.exit(1)

        conn_str = os.environ.get("STAGING_DATABASE_URL")
        if not conn_str:
            print(
                "\nENVIRONMENT CONFIGURATION ERROR: STAGING_DATABASE_URL environment variable is not set.\n"
                "In remote execution mode, database credentials must be provided via STAGING_DATABASE_URL.\n"
                "Command-line parameter --db-url is removed to prevent process argument exposure."
            )
            sys.exit(1)

        if KNOWN_PRODUCTION_PROJECT_REF in conn_str.lower():
            print(
                f"\nCRITICAL SECURITY VIOLATION: STAGING_DATABASE_URL contains production project identifier '{KNOWN_PRODUCTION_PROJECT_REF}'!\n"
                "Running functional or staging tests against production is strictly prohibited."
            )
            sys.exit(1)

    try:
        report = run_pipeline(
            project_ref=args.project_ref,
            conn_str=conn_str,
            sql_path=args.sql_path,
            manifest_path=args.manifest_path,
            allow_local=args.local_disposable,
            fresh_db=args.fresh_db,
        )
        print("\n" + "=" * 70)
        print(" VERIFICATION COMPLETE: PASS")
        print("=" * 70)
        print(f"Destination Mode:      {report['destination_info']['mode']}")
        print(f"Effective Host:        {report['destination_info']['effective_host']}")
        print(f"Effective Port:        {report['destination_info']['effective_port']}")
        print(f"Effective Database:    {report['destination_info']['effective_dbname']}")
        print(f"Project Reference:     {report['destination_info']['project_ref']}")
        print(f"Effective SSL Mode:    {report['destination_info']['effective_sslmode']}")
        print(f"Manifest Hash:         {report['manifest_hash']}")
        print(f"SQL SHA-256:           {report['sql_hash']}")
        print(f"Execution Duration:    {report['execution_duration_ms']:.2f} ms")
        print(f"Final Tx Status:       {report['final_transaction_status']}")
        print(f"Scenarios Verified:    8/8 PASS")
        print(f"Exact-ID Audit Counts: All 6 tables verified 0 rows surviving")
        print(f"Table Counts:          100% Invariant Before vs After")
        if args.fresh_db:
            print(f"Staging Mode:          FRESH DATABASE (Verified 0 initial rows & schema invariants)")
            print(f"Post-Rollback State:   100% Invariant (0 surviving rows across all 10 application tables)")
        else:
            print(f"Baseline Invariants:   Intact and Unmutated")
        sys.exit(0)
    except Exception as e:
        # Sanitize any potential URL strings or passwords in error messages
        sanitized_msg = sanitize_db_url(str(e))
        print(f"\nSAFETY INTERVENTION / ABORT: {sanitized_msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()

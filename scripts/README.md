# ORQESTRA Verification & Staging Tooling

This directory contains database verification scripts, staging test runners, cryptographic hash manifests, and diagnostics used to ensure database integrity, Row-Level Security (RLS) enforcement, and transaction safety.

---

## 1. Active Verification Runners

### 1.1 `test_runner_phase_4t.py`
**Comprehensive Security Guard & Runner Integration Suite**
- **Purpose**: Runs a complete local test suite verifying all 10 security domains of the staging runner architecture without contacting remote databases.
- **Key Guards Tested**:
  1. Effective connection parameter resolution (`psycopg.conninfo.conninfo_to_dict`).
  2. Strict TLS verification policy (`sslmode=verify-full` mandatory).
  3. Supabase regional pooler and direct host enclosure.
  4. Production database isolation: strictly forbids target project `vwlwbwwrumsmjqeavvxk`.
  5. Process argument security: ensures credentials cannot be passed via command-line arguments.
  6. Credential sanitization: guarantees passwords and tokens are masked with `***` in logs and exceptions.
  7. Loopback-enclosed local disposable validation (`localhost`, `127.0.0.1`, `[::1]`).
  8. Two-tier cryptographic hash authentication against hard-pinned SHA-256.
  9. Multi-statement execution with guaranteed rollback and transaction state validation (`pq.TransactionStatus.IDLE`).
  10. Fresh staging database mode (`--fresh-db` verification).
- **Execution**:
  ```powershell
  backend\.venv\Scripts\python scripts/test_runner_phase_4t.py
  ```

### 1.2 `run_phase_4t_remote.py`
**Dedicated Staging Database Functional Test Runner**
- **Purpose**: Safely executes `PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql` against an authorized Supabase staging database or a local disposable PostgreSQL 16 cluster.
- **Safety Invariants**:
  - Requires `--project-ref` matching the target staging environment.
  - Refuses to connect if the target project matches production (`vwlwbwwrumsmjqeavvxk`).
  - Reads connection URLs exclusively from environment variables (`STAGING_DATABASE_URL` in remote mode, `LOCAL_DATABASE_URL` in local mode).
  - Authenticates `PHASE_4T_APPROVED_HASHES.json` against hard-pinned SHA-256 before reading SQL.
  - Verifies database-level `IDLE` status post-execution, ensuring every transaction cleanly rolls back.
- **Local Disposable Mode**:
  ```powershell
  backend\.venv\Scripts\python scripts/run_phase_4t_remote.py --local-disposable --fresh-db
  ```

### 1.3 `run_staging_diagnostic.py`
**Read-Only Staging Diagnostic Runner**
- **Purpose**: Executes `PHASE_4L_CANONICAL_DIAGNOSTIC_1.sql` against a target database to inspect table existence, RLS status, function ACLs, and migration versions.
- **Safety Invariants**:
  - Read-only queries only (`SELECT` from catalog and `information_schema`).
  - Rejects connection strings targeting the confirmed production project.
  - Requires `--remote-authorized` flag before opening remote connections.

---

## 2. SQL Scripts & Cryptographic Manifests

| File | Purpose | Hash Invariant |
|---|---|---|
| `PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql` | Hardened 8-scenario functional test verifying stock mutations, role permissions, and transaction rollbacks. | SHA-256 pinned in `PHASE_4T_APPROVED_HASHES.json` (`b1f21dc7...`) |
| `PHASE_4T_APPROVED_HASHES.json` | Two-tier hash manifest containing verified SHA-256 digests. | SHA-256 hard-pinned in `run_phase_4t_remote.py` (`8e0ceae1...`) |
| `PHASE_4L_CANONICAL_DIAGNOSTIC_1.sql` | Read-only diagnostic query script inspecting PostgreSQL catalog tables. | SHA-256 pinned in `run_staging_diagnostic.py` |

---

## 3. Historical & Archival Artifacts

| File | Historical Context |
|---|---|
| `test_phase_4r_local.py` | Phase 4R local test runner for catalog and RLS inspection. |
| `PHASE_4R_CORRECTED_FUNCTIONAL_TEST.sql` | Phase 4R functional test script. |
| `PHASE_4R_LOCAL_VERIFICATION_RESULTS.json` | Recorded local verification outputs from Phase 4R execution. |
| `test_phase_4t_local.py` | Phase 4T-F local runner (immutable hash-verified artifact). |
| `PHASE_4T_LOCAL_VERIFICATION_RESULTS.json` | Recorded local verification outputs from Phase 4T-F execution. |

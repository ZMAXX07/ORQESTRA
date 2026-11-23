# ORQESTRA — Phase 4E: Controlled Staging Deployment Runbook

**Document Version:** 1.0.0  
**Target Environment:** Staging (`https://vwlwbwwrumsmjqeavvxk.supabase.co`)  
**Project Reference:** `vwlwbwwrumsmjqeavvxk`  
**Patch Migration:** `supabase/migrations/20261115000001_remediate_adjust_stock_atomic.sql`  
**Execution Mode:** Operator-Driven Manual Execution (Pending Explicit User Approval)  
**Safety Status:** PRE-FLIGHT VERIFIED — ZERO MUTATIONS PERFORMED DURING AUDIT

---

## 1. Pre-Deployment Backup and Recovery Requirements

Prior to performing any remote database operations, a complete logical backup of both schema and data must be captured and stored securely.

### 1.1 Logical Schema & Data Backup Commands

#### Command 1.1A: Export Complete Public Schema DDL
```bash
npx supabase db dump --project-ref vwlwbwwrumsmjqeavvxk --schema public -f backup_staging_schema_20261115.sql
```
- **Purpose:** Exports all active table definitions, constraints, indexes, triggers, RLS policies, and stored procedures currently present in the remote PostgreSQL instance.
- **Expected Result:** Generates file `backup_staging_schema_20261115.sql` containing valid PostgreSQL SQL statements. File size approximately 80 KB to 150 KB.
- **Potential Failure Consequences:**
  - *CLI Token Missing / Expired:* Prompts for `supabase login`.
  - *Network Timeout:* Retries required; do not proceed until dump completes successfully.
  - *Mitigation:* Verify non-zero file size: `Get-Item backup_staging_schema_20261115.sql`.

#### Command 1.1B: Export Remote Staging Table Data
```bash
npx supabase db dump --project-ref vwlwbwwrumsmjqeavvxk --data-only --schema public -f backup_staging_data_20261115.sql
```
- **Purpose:** Captures all existing staging business records, user memberships, customer accounts, products, inventory quantities, orders, and historical invoices.
- **Expected Result:** Generates `backup_staging_data_20261115.sql` containing `INSERT` statements for all existing staging data.
- **Potential Failure Consequences:**
  - *Database Lock Contention:* PostgREST reads might time out if heavy concurrent mutations are active. Staging traffic is idle; risk is minimal.
  - *Mitigation:* Ensure data dump completes with return code `0`.

#### Command 1.1C: Compute Backup Checksums
```powershell
Get-FileHash backup_staging_*.sql -Algorithm SHA256
```
- **Purpose:** Establishes cryptographic hashes for rollback verification.
- **Expected Result:** Distinct SHA-256 hashes printed for schema and data dumps. Store hashes in the operator deployment log.

---

## 2. Supabase Project Reference Verification

Before interacting with the remote environment, the operator must verify that the local CLI configuration targets the staging project (`vwlwbwwrumsmjqeavvxk`) and **never** a production project.

#### Command 2.1: Verify Linked Project Configuration
```bash
npx supabase status
```
- **Purpose:** Verifies CLI link status, API URLs, and project credentials.
- **Expected Result:**
  ```
  API URL: https://vwlwbwwrumsmjqeavvxk.supabase.co
  GraphQL URL: https://vwlwbwwrumsmjqeavvxk.supabase.co/graphql/v1
  DB URL: postgresql://postgres:***@db.vwlwbwwrumsmjqeavvxk.supabase.co:5432/postgres
  ```
- **Potential Failure Consequences:**
  - *Target Mismatch:* If the status lists any project ID other than `vwlwbwwrumsmjqeavvxk`, **STOP IMMEDIATELY**. Do not proceed.
  - *Resolution:* Run `npx supabase link --project-ref vwlwbwwrumsmjqeavvxk` to link strictly to staging.

---

## 3. Exact Commands to Record Historical Migrations

Because migrations `20261022000001` through `20261023000004` were originally provisioned via the Supabase Web SQL Editor, their database objects exist in `public`, but their version IDs are unrecorded in `supabase_migrations.schema_migrations`. 

Running `supabase migration repair --status applied` updates the CLI ledger table **without executing SQL DDL or altering business data**.

#### Command 3.1: Record Core Schema Migration
```bash
npx supabase migration repair --status applied 20261022000001 --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Records version `20261022000001` (`20261022000001_core_schema.sql`) as applied.
- **Expected Result:** `Repaired migration 20261022000001 to applied.`
- **Failure Consequence:** If omitted, subsequent `supabase db push` will attempt `CREATE TABLE businesses`, crashing with `relation "businesses" already exists`.

#### Command 3.2: Record Row Level Security Migration
```bash
npx supabase migration repair --status applied 20261022000002 --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Records version `20261022000002` (`20261022000002_row_level_security.sql`) as applied.
- **Expected Result:** `Repaired migration 20261022000002 to applied.`
- **Failure Consequence:** If omitted, CLI will attempt to re-create existing helper functions and triggers.

#### Command 3.3: Record Operations & Transactions Migration
```bash
npx supabase migration repair --status applied 20261023000001 --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Records version `20261023000001` (`20261023000001_operations_transactions.sql`) as applied.
- **Expected Result:** `Repaired migration 20261023000001 to applied.`
- **Failure Consequence:** If omitted, CLI will attempt `ALTER TYPE order_status ADD VALUE 'rejected'`, which fails if already committed.

#### Command 3.4: Record Realtime Publications Migration
```bash
npx supabase migration repair --status applied 20261023000002 --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Records version `20261023000002` (`20261023000002_realtime_publications.sql`) as applied.
- **Expected Result:** `Repaired migration 20261023000002 to applied.`
- **Failure Consequence:** If omitted, CLI will attempt to add tables to `supabase_realtime` that are already members.

#### Command 3.5: Record Invoices & Allocation Migration
```bash
npx supabase migration repair --status applied 20261023000003 --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Records version `20261023000003` (`20261023000003_invoices_and_allocation.sql`) as applied.
- **Expected Result:** `Repaired migration 20261023000003 to applied.`
- **Failure Consequence:** If omitted, CLI will attempt `CREATE INDEX idx_invoices_business_created`, causing redundant index build locks.

#### Command 3.6: Record Invoice Snapshots & Constraints Migration
```bash
npx supabase migration repair --status applied 20261023000004 --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Records version `20261023000004` (`20261023000004_invoice_snapshots_and_constraints.sql`) as applied.
- **Expected Result:** `Repaired migration 20261023000004 to applied.`
- **Failure Consequence:** If omitted, CLI will attempt to re-add JSONB snapshot columns to `invoices`.

---

## 4. Verification of Migration Ledger State

Before pushing the new migration, the operator must verify that the remote ledger reflects the repaired state.

#### Command 4.1: Inspect Migration Ledger Parity
```bash
npx supabase migration list --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Queries remote `supabase_migrations.schema_migrations` and compares with local `supabase/migrations/`.
- **Expected Result:**
  ```
  Local               | Remote              | Time (UTC)
  --------------------+---------------------+-----------------------
  20261022000001      | 20261022000001      | 2026-10-22 00:00:01
  20261022000002      | 20261022000002      | 2026-10-22 00:00:02
  20261023000001      | 20261023000001      | 2026-10-23 00:00:01
  20261023000002      | 20261023000002      | 2026-10-23 00:00:02
  20261023000003      | 20261023000003      | 2026-10-23 00:00:03
  20261023000004      | 20261023000004      | 2026-10-23 00:00:04
  20261115000001      | Not applied         |
  ```
- **Potential Failure Consequences:**
  - *Mismatch / Unapplied Historical Migrations:* If any migration between `20261022000001` and `20261023000004` shows as "Not applied", **DO NOT PUSH**. Re-run the repair command for that specific migration.

---

## 5. Application of Patch Migration `20261115000001`

Once ledger parity is confirmed, apply the single pending migration.

#### Command 5.1: Push Pending Remediation Migration
```bash
npx supabase db push --project-ref vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Executes only unapplied migrations (`20261115000001_remediate_adjust_stock_atomic.sql`) against the remote database within an atomic transaction.
- **Expected Result:**
  ```
  Connecting to remote database...
  Applying migration 20261115000001_remediate_adjust_stock_atomic.sql...
  Finished supabase db push.
  ```
- **Potential Failure Consequences:**
  - *SQL Syntax / Compiler Error:* The transaction rolls back automatically. The remote database remains on its previous functional state.
  - *Permission Denied:* Occurs only if the connected CLI role lacks DDL administration privileges.

---

## 6. Verification of Deployed Function Definition

Confirm that the remote PostgreSQL engine has replaced the function body and compiled with `#variable_conflict error`.

#### Command 6.1: Verify Function Source via Read-Only PostgREST RPC Probe
```bash
# Verify RPC endpoint responds with parameter schema
curl -s -X GET "https://vwlwbwwrumsmjqeavvxk.supabase.co/rest/v1/" \
  -H "apikey: <VITE_SUPABASE_ANON_KEY>" | jq '.paths["/rpc/adjust_stock_atomic"]'
```
- **Purpose:** Inspects PostgREST OpenAPI metadata to verify that `adjust_stock_atomic` is published and expects the exact four output fields: `inventory_id`, `product_id`, `new_quantity`, `movement_id`.
- **Expected Result:** HTTP 200 with OpenAPI method definition matching the expected parameters.

#### Command 6.2: Direct SQL Definition Verification (Via Web SQL Editor or Admin psql)
```sql
SELECT 
    proname, 
    prosecdef, 
    proconfig,
    pg_get_functiondef(oid) LIKE '%#variable_conflict error%' AS has_variable_conflict_directive,
    pg_get_functiondef(oid) LIKE '%inventory.business_id = p_business_id%' AS has_qualified_predicates
FROM pg_proc 
WHERE proname = 'adjust_stock_atomic';
```
- **Expected Result:**
  - `prosecdef`: `true` (`SECURITY DEFINER`)
  - `proconfig`: `{search_path=public,pg_temp}`
  - `has_variable_conflict_directive`: `true`
  - `has_qualified_predicates`: `true`

---

## 7. Verification of Function Permissions & Security

Verify that anonymous users cannot invoke the function directly and that execution is locked down.

#### Command 7.1: Verify Anonymous Rejection
```bash
curl -s -X POST "https://vwlwbwwrumsmjqeavvxk.supabase.co/rest/v1/rpc/adjust_stock_atomic" \
  -H "apikey: <VITE_SUPABASE_ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"p_business_id": "00000000-0000-0000-0000-000000000000", "p_product_id": "00000000-0000-0000-0000-000000000000", "p_quantity_change": 1, "p_movement_type": "restock", "p_notes": "Probe check"}'
```
- **Purpose:** Asserts that anonymous public requests are rejected at the database level.
- **Expected Result:** HTTP 401 Unauthorized or HTTP 403 Forbidden with error message: `"Unauthenticated caller cannot execute stock adjustments"`.
- **Failure Consequence:** If HTTP 200 or an internal SQL error occurs, permissions were not locked down. Immediately re-run `REVOKE EXECUTE ON FUNCTION public.adjust_stock_atomic FROM PUBLIC;`.

---

## 8. Remote Smoke-Test Plan

The operator executes four targeted operational tests against the remote staging environment using an authenticated staging account (`staging_admin`):

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Staging Admin (UI/API)
    participant API as FastAPI Backend
    participant PG as Remote Supabase PG
    participant Ledger as Stock Movements & Audit Logs

    Note over Admin,Ledger: Test 1: Positive Stock Adjustment
    Admin->>API: POST /rpc/adjust_stock_atomic (+10 units)
    API->>PG: adjust_stock_atomic(biz, prod, 10, 'restock', 'Smoke test')
    PG->>PG: Lock row FOR UPDATE (qualified)
    PG->>Ledger: Insert stock_movements & audit_logs
    PG-->>API: RETURN (inv_id, prod_id, new_qty=30, mvt_id)
    API-->>Admin: HTTP 200 OK (Zero 42702 errors)

    Note over Admin,Ledger: Test 2: Insufficient Stock Rejection
    Admin->>API: POST /rpc/adjust_stock_atomic (-100 units)
    API->>PG: adjust_stock_atomic(biz, prod, -100, ...)
    PG-->>API: Exception: would result in negative quantity (-70)
    API-->>Admin: HTTP 400 Bad Request (Stock unchanged)

    Note over Admin,Ledger: Test 3: Order Approval Atomic Deduction
    Admin->>API: POST /api/v1/orders/{id}/approve
    API->>PG: approve_order_atomic(order_id, user_id, biz_id)
    PG->>PG: Deduct stock from 30 -> 26
    PG-->>Admin: HTTP 200 OK (Status: approved)
```

### Smoke Test Suite Matrix

| Test ID | Action | Payload / Endpoint | Expected Response | Verifies |
|---|---|---|---|---|
| **SMK-01** | Manual Restock | `POST /rpc/adjust_stock_atomic`<br/>`qty: +5, type: 'restock', note: 'Staging smoke'` | `HTTP 200`<br/>`new_quantity` increments by 5 | Resolves defect `42702`; verifies positive adjustment. |
| **SMK-02** | Manual Deduction | `POST /rpc/adjust_stock_atomic`<br/>`qty: -2, type: 'adjustment', note: 'Smoke deduction'` | `HTTP 200`<br/>`new_quantity` decrements by 2 | Verifies negative adjustment. |
| **SMK-03** | Oversell / Negative Stock | `POST /rpc/adjust_stock_atomic`<br/>`qty: -999, type: 'adjustment', note: 'Excessive'` | `HTTP 400 / 409`<br/>`Stock adjustment rejected: would result in negative quantity` | Verifies constraint enforcement & rollback. |
| **SMK-04** | Cross-Business Isolation | Target product belonging to different business ID | `HTTP 400 / 403`<br/>`Product ... does not belong to business ...` | Verifies tenant isolation. |
| **SMK-05** | Order Approval | `POST /api/v1/orders/{order_id}/approve` | `HTTP 200`<br/>`order_status: 'approved'` | Verifies compatibility with `approve_order_atomic`. |

---

## 9. Post-Deployment Health Checks

Execute automated health probes against both backend and frontend staging endpoints.

#### Command 9.1: Probe Backend API Health & Database Connectivity
```bash
curl -s -i "https://staging-api.orqestra.internal/api/v1/health"
```
*(Or local staging instance `http://127.0.0.1:8000/api/v1/health`)*
- **Expected Result:**
  ```json
  {
    "status": "healthy",
    "environment": "staging",
    "version": "0.1.0",
    "database": {
      "status": "operational",
      "detail": "Supabase PostgreSQL database connection verified and operational"
    }
  }
  ```
- **Failure Consequence:** If `database.status` is `"error"` or `"unconfigured"`, inspect backend logs immediately. Backend lifespan prevents startup on unconfigured database connections.

#### Command 9.2: Frontend Single Page Application Verification
1. Open Staging URL in browser: `https://staging.orqestra.internal` (or `http://127.0.0.1:4173`).
2. Verify HTTP status `200` on bundle assets.
3. Open Developer Tools > Console: assert **zero uncaught exceptions**.
4. Confirm Realtime WebSocket connection status: Phoenix socket connected with green status indicator.

---

## 10. Rollback and Recovery Procedures

If unexpected regressions, database lock deadlocks, or functional anomalies occur during post-deployment verification, execute the appropriate rollback protocol below.

### Scenario A: Migration Fails During `supabase db push`
- **Condition:** Network disconnect or DDL failure during execution.
- **Behavior:** PostgreSQL executes migrations within an atomic transaction. If any statement fails, the entire migration aborts and rolls back automatically.
- **Action:** No database changes were persisted. Investigate error logs and resolve before re-attempting.

### Scenario B: Remediation Function Deployed but Operational Defect Identified
If `adjust_stock_atomic` exhibits unexpected behavior in staging:

#### Step 1: Execute Standalone Rollback Migration
Create and push an emergency rollback migration restoring the prior function definition or applying a targeted hotfix:
```bash
# Example emergency rollback SQL: supabase/migrations/20261115000002_rollback_adjust_stock_atomic.sql
npx supabase db push --project-ref vwlwbwwrumsmjqeavvxk
```

### Scenario C: Complete Database State Restoration from Pre-Deployment Backup
If data corruption occurs during manual testing:

#### Step 1: Restore Staging Public Schema
```bash
# Re-apply schema snapshot taken in Step 1.1A
npx supabase db execute --project-ref vwlwbwwrumsmjqeavvxk -f backup_staging_schema_20261115.sql
```

#### Step 2: Restore Staging Business Data
```bash
# Re-apply data snapshot taken in Step 1.1B
npx supabase db execute --project-ref vwlwbwwrumsmjqeavvxk -f backup_staging_data_20261115.sql
```

#### Step 3: Verify Post-Recovery Consistency
- Run `GET /api/v1/health` to confirm database connectivity.
- Verify inventory counts match pre-deployment counts.

---

## 11. Final Operator Readiness Sign-Off

| Verification Item | Requirement | Pre-Flight Status |
| :--- | :--- | :---: |
| **Code Review** | Patch migration reviewed line-by-line | **PASSED (Phase 4C)** |
| **Migration Parity** | 7 files reconciled against remote schema | **PASSED (Phase 4D)** |
| **Regression Suite** | 141 backend tests + 136 frontend tests passed | **PASSED (100%)** |
| **Frontend Production Build** | `tsc && vite build` built in 1.45s | **PASSED** |
| **Disposable DB Tests** | Real PostgreSQL Scenario 13 verified | **PASSED (10/10)** |
| **Safety Compliance** | Remote database untouched | **CONFIRMED** |

### Operator Instruction
This runbook is complete and verified. **Do not execute any command in this document until receiving explicit user authorization.**

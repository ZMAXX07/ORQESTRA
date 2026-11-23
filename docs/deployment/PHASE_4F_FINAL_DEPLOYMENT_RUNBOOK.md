# ORQESTRA — Phase 4F: Final Staging Deployment Runbook & Safety Specification

**Document Version:** 2.0.0 (Production-Grade Final Runbook)  
**Target Project:** Supabase Staging (`vwlwbwwrumsmjqeavvxk`)  
**Target API URL:** `https://vwlwbwwrumsmjqeavvxk.supabase.co`  
**Patch Migration File:** `supabase/migrations/20261115000001_remediate_adjust_stock_atomic.sql`  
**Execution Mode:** Operator-Driven Manual Execution (Pending Explicit User Approval)  
**Safety Status:** PRE-FLIGHT VERIFIED — ZERO REMOTE MUTATIONS PERFORMED

---

## 1. Project Reference & Target Verification

Before initiating any remote database operations, the operator must verify that the local environment targets strictly the linked staging project (`vwlwbwwrumsmjqeavvxk`). Using `supabase status` alone is insufficient because it inspects local Docker containers.

### 1.1 Local File Verification of Linked Project
```powershell
# 1. Inspect Supabase project reference configuration
Get-Content supabase\.temp\project-ref
Get-Content supabase\.temp\linked-project.json
```
- **Expected Output:**
  ```
  vwlwbwwrumsmjqeavvxk
  {"ref":"vwlwbwwrumsmjqeavvxk","name":"ORQESTRA","organization_id":"grzrefmjxjgisiqrifkh","organization_slug":"grzrefmjxjgisiqrifkh"}
  ```
- **Failure Consequence:** If the reference string does not match `vwlwbwwrumsmjqeavvxk`, **STOP IMMEDIATELY**. Do not proceed. Re-link with `npx supabase link --project-ref vwlwbwwrumsmjqeavvxk`.

### 1.2 Remote CLI Target Verification
```bash
npx supabase projects list
```
- **Purpose:** Queries the Supabase Management API to verify active projects and authenticated identity.
- **Expected Output:** Table listing `ORQESTRA` with Reference ID `vwlwbwwrumsmjqeavvxk` and Status `ACTIVE_HEALTHY`.
- **Command Safety Rule:** Every command in this runbook explicitly specifies `--remote=vwlwbwwrumsmjqeavvxk` to prevent ambiguous context targeting.

---

## 2. Pre-Deployment Backup & Cryptographic Validation

Prior to performing migration repairs or DDL operations, a full logical schema and data backup must be captured and verified.

### 2.1 Backup Execution Commands

#### Step 2.1A: Dump Public Schema DDL
```bash
npx supabase db dump --remote=vwlwbwwrumsmjqeavvxk --schema public -f backup_staging_schema_20261115.sql
```
- **Purpose:** Extracts complete SQL DDL for all public tables, enums, composite foreign keys, check constraints, RLS policies, and stored procedures.
- **Flags Used:** `--remote=vwlwbwwrumsmjqeavvxk` (targets staging), `--schema public` (scopes to application domain), `-f` (output file path).
- **Expected Result:** Command exits with code `0`. Generates `backup_staging_schema_20261115.sql` (~80 KB – 150 KB).

#### Step 2.1B: Dump Staging Business Data
```bash
npx supabase db dump --remote=vwlwbwwrumsmjqeavvxk --data-only --schema public -f backup_staging_data_20261115.sql
```
- **Purpose:** Extracts table records (`INSERT` statements) for businesses, user memberships, customers, products, inventory, orders, and historical invoices.
- **Flags Used:** `--data-only` (excludes DDL), `--schema public` (scopes to application tables).
- **Expected Result:** Command exits with code `0`. Generates `backup_staging_data_20261115.sql`.

### 2.2 Backup Integrity Validation
Execute the following automated verification in PowerShell:
```powershell
# 1. Assert exit code and file existence
$schemaFile = Get-Item "backup_staging_schema_20261115.sql"
$dataFile = Get-Item "backup_staging_data_20261115.sql"

if ($schemaFile.Length -lt 10000) { throw "SCHEMA BACKUP CORRUPT: File size ($($schemaFile.Length) bytes) too small." }
if ($dataFile.Length -lt 1000) { throw "DATA BACKUP CORRUPT: File size ($($dataFile.Length) bytes) too small." }

# 2. Assert presence of critical domain entities
$schemaContent = Get-Content $schemaFile.FullName -Raw
$criticalEntities = @("CREATE TABLE public.businesses", "CREATE TABLE public.inventory", "CREATE TABLE public.orders", "adjust_stock_atomic")
foreach ($entity in $criticalEntities) {
    if (-not $schemaContent.Contains($entity)) { throw "SCHEMA VALIDATION FAILED: Missing '$entity'." }
}

# 3. Generate and log cryptographic checksums
Get-FileHash backup_staging_*.sql -Algorithm SHA256 | Format-Table -AutoSize
```
- **Expected Result:** Script confirms file size thresholds, verifies all 4 critical entity declarations, and outputs SHA-256 hashes.
- **Secure Storage:** Move both backup files to a restricted staging backup folder outside version control (e.g., `../orqestra-backups/`). Never commit backup files containing customer or business data to Git.

### 2.3 Restoration Feasibility & Disclosure
> [!IMPORTANT]
> **Restoration Testing Disclosure:** Restoration of these exact backup files against the live Supabase staging database has **NOT** been executed during this audit, in compliance with the strict safety rule prohibiting remote data modifications. However, the exact restoration procedure using `psql` or `supabase db execute` is specified in Section 9 of this document.

---

## 3. Remote Migration History Ledger Reconciliation

Because migrations 1 through 6 were applied during initial staging setup via the Supabase Web SQL Editor, their database objects exist in PostgreSQL, but their version IDs are unrecorded in `supabase_migrations.schema_migrations`.

### 3.1 Syntax & Flag Specifications
- **Command:** `supabase migration repair`
- **Required Flags:**
  - `--status applied`: Marks versions as already completed without executing SQL statements.
  - `--remote=vwlwbwwrumsmjqeavvxk`: Specifies the exact remote staging project.
- **Batching:** Multiple version strings can be supplied in a single invocation.

### 3.2 Exact Repair Command
```bash
npx supabase migration repair --status applied --remote=vwlwbwwrumsmjqeavvxk 20261022000001 20261022000002 20261023000001 20261023000002 20261023000003 20261023000004
```
- **Purpose:** Atomically inserts 6 records into `supabase_migrations.schema_migrations`.
- **Expected Output:**
  ```
  Repaired migration 20261022000001 to applied.
  Repaired migration 20261022000002 to applied.
  Repaired migration 20261023000001 to applied.
  Repaired migration 20261023000002 to applied.
  Repaired migration 20261023000003 to applied.
  Repaired migration 20261023000004 to applied.
  ```
- **Potential Failure Consequences:**
  - *Network Interruption:* Re-running `migration repair` with `--status applied` is completely idempotent. Safe to retry.
  - *Consequence if Omitted:* Subsequent `supabase db push` will attempt to execute `20261022000001_core_schema.sql` from line 1, colliding with existing `businesses` table and aborting deployment.

### 3.3 Verification of Recorded Versions
```bash
npx supabase migration list --remote=vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Verifies that remote CLI tracking matches local on-disk migrations.
- **Expected Output:**
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
- **Gate Check:** If any migration between `20261022000001` and `20261023000004` is listed as `Not applied`, **HALT**. Do not proceed to `db push`.

---

## 4. Application of Patch Migration `20261115000001`

### 4.1 Step 4A: Dry-Run Verification
```bash
npx supabase db push --dry-run --remote=vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Simulates deployment and prints the list of migrations that would be applied without modifying the remote database.
- **Expected Output:**
  ```
  Connecting to remote database...
  The following migrations would be applied:
    - 20261115000001_remediate_adjust_stock_atomic.sql
  ```
- **Gate Check:** If any migration other than `20261115000001` appears in the list, **ABORT**.

### 4.2 Step 4B: Live Migration Push
```bash
npx supabase db push --remote=vwlwbwwrumsmjqeavvxk
```
- **Purpose:** Applies `20261115000001_remediate_adjust_stock_atomic.sql` to remote Supabase.
- **Expected Output:**
  ```
  Connecting to remote database...
  Applying migration 20261115000001_remediate_adjust_stock_atomic.sql...
  Finished supabase db push.
  ```

### 4.3 Transaction & Recovery Realities during `db push`
> [!WARNING]
> **Do Not Assume Automatic Universal Rollback:**
> 1. **Single Migration Scope:** Migration `20261115000001` contains standard transactional DDL (`CREATE OR REPLACE FUNCTION`, `REVOKE`, `GRANT`). If a syntax error or semantic failure occurs before the transaction commits, PostgreSQL aborts the entire migration and rolls back all statements within it.
> 2. **Mid-Stream Network Disconnection:** If the network connection drops *after* PostgreSQL executes statements but *before* the CLI receives acknowledgment, the transaction may have committed on the remote engine.
> 3. **Permission Grants Partial State:** If `CREATE OR REPLACE FUNCTION` succeeds but a subsequent network timeout occurs during `GRANT EXECUTE`, the function could exist with incomplete permissions.
> 4. **Operator Action on Failure:** If `db push` fails or disconnects, the operator must immediately run the SQL verification queries in Section 5 to determine the exact remote state before attempting any retry or rollback.

---

## 5. Exact SQL Verifications of Deployed Function & Security

Execute the following queries via the Supabase Web SQL Editor, pgAdmin, or admin connection:

### 5.1 Verification Query: Function Definition, Compiler Directive & Search Path
```sql
SELECT 
    p.proname,
    p.prosecdef AS is_security_definer,
    p.proconfig AS search_path_configuration,
    pg_get_functiondef(p.oid) LIKE '%#variable_conflict error%' AS has_variable_conflict_directive,
    pg_get_functiondef(p.oid) LIKE '%inventory.business_id = p_business_id%' AS has_qualified_business_id,
    pg_get_functiondef(p.oid) LIKE '%inventory.product_id = p_product_id%' AS has_qualified_product_id
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public' 
  AND p.proname = 'adjust_stock_atomic';
```
- **Expected Assertion Output:**

| Column | Expected Value | Verification Purpose |
|---|:---:|---|
| `proname` | `adjust_stock_atomic` | Function exists in `public` schema |
| `is_security_definer` | `true` | Runs with creator privileges for ledger writes |
| `search_path_configuration` | `{search_path=public,pg_temp}` | Prevents search-path escalation attacks |
| `has_variable_conflict_directive` | `true` | Compile-time shadowing detection enabled |
| `has_qualified_business_id` | `true` | Eliminates table column ambiguity |
| `has_qualified_product_id` | `true` | Resolves defect `42702` |

### 5.2 Verification Query: EXECUTE Permissions & Access Control
```sql
SELECT 
    p.proname,
    r.rolname AS role_name,
    has_function_privilege(r.rolname, p.oid, 'EXECUTE') AS can_execute
FROM pg_proc p
CROSS JOIN pg_roles r
WHERE p.proname = 'adjust_stock_atomic'
  AND r.rolname IN ('anon', 'public', 'authenticated', 'service_role')
ORDER BY r.rolname;
```
- **Expected Assertion Output:**

| Role Name | Expected `can_execute` | Security Rationale |
|---|:---:|---|
| `anon` | `false` | Unauthenticated public users strictly blocked |
| `public` | `false` | Default execution privilege explicitly revoked |
| `authenticated` | `true` | Logged-in operators can execute subject to internal role checks |
| `service_role` | `true` | Backend trusted worker can execute with actor parameter |

---

## 6. Safe Smoke-Test Strategy (Preserving Phase 4A Data)

### 6.1 Preserving Historical Staging Records
The staging database currently contains operational records verified during Phase 4A:
- **Business Workspaces:** `TechZone Electronics` (`59b079d3-...`) and `demoshop` (`5709f406-...`)
- **Phase 4A Product:** `STG-1890` (`Staging Monitor 1890 Pro`) — **Current Stock: 18 units**
- **Phase 4A Customer:** `Staging Buyer 1890`
- **Phase 4A Invoice:** `INV-202611-0008` (PDF snapshot allocated)

> [!CAUTION]
> **Preservation Rule:** Do NOT alter, adjust, or delete `STG-1890`, `Staging Buyer 1890`, or `INV-202611-0008`. All smoke tests must operate strictly on an isolated disposable test SKU.

### 6.2 Smoke-Test Execution Protocol

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Staging Operator
    participant App as Staging UI / API
    participant PG as Remote PostgreSQL
    participant SM as Stock Movements Ledger

    Admin->>App: 1. Create Product 'STG-SMOKE-4F' (Initial Stock: 10)
    App->>PG: INSERT INTO products & inventory
    PG-->>App: OK (Stock = 10)

    Admin->>App: 2. Positive Restock (+5 units, note: 'Smoke restock')
    App->>PG: adjust_stock_atomic(TechZone, STG-SMOKE-4F, 5, 'restock', 'Smoke restock')
    PG->>SM: Insert stock_movements (+5)
    PG-->>App: Return new_quantity = 15 (Zero 42702 errors)
    App-->>Admin: UI updates instantaneously

    Admin->>App: 3. Negative Deduction (-3 units, note: 'Smoke deduction')
    App->>PG: adjust_stock_atomic(TechZone, STG-SMOKE-4F, -3, 'adjustment', 'Smoke deduction')
    PG->>SM: Insert stock_movements (-3)
    PG-->>App: Return new_quantity = 12
    App-->>Admin: UI updates to 12

    Admin->>App: 4. Negative Stock Rejection (-999 units)
    App->>PG: adjust_stock_atomic(TechZone, STG-SMOKE-4F, -999, ...)
    PG-->>App: Exception: would result in negative quantity (-987)
    App-->>Admin: HTTP 400 Bad Request (Stock remains 12)

    Admin->>App: 5. Tenant Isolation Verification
    App->>PG: Switch to demoshop; query products
    PG-->>App: STG-SMOKE-4F not visible (Count = 0)
```

### Smoke Test Matrix

| Test ID | Target Product | Operation | Parameters | Expected Result | Verifies |
|---|---|---|---|---|---|
| **SMK-01** | `STG-SMOKE-4F` | Product Creation | Initial Stock: 10, Price: 100.00 | Product visible in UI; stock = 10 | Clean test isolation |
| **SMK-02** | `STG-SMOKE-4F` | Manual Restock | Change: `+5`, Type: `restock`, Note: `Smoke restock` | HTTP 200, Stock = 15, Movement logged | **Fix for Defect 42702** |
| **SMK-03** | `STG-SMOKE-4F` | Manual Deduction | Change: `-3`, Type: `adjustment`, Note: `Damaged item` | HTTP 200, Stock = 12, Movement logged | Negative delta handling |
| **SMK-04** | `STG-SMOKE-4F` | Oversell Prevention | Change: `-999`, Type: `adjustment`, Note: `Excessive` | HTTP 400/409, Stock remains 12 | Check constraint & rollback |
| **SMK-05** | `demoshop` | Cross-Tenant Probe | Target `STG-SMOKE-4F` from `demoshop` workspace | Product count = 0; adjustment rejected | Strict RLS & tenant isolation |
| **SMK-06** | `STG-1890` | Baseline Preservation | Read stock for `STG-1890` | Stock **strictly 18 units** | Phase 4A data unharmed |

---

## 7. Post-Deployment System Health Checks

### 7.1 Backend Truthful Health Probe
```bash
curl -s -i "https://staging-api.orqestra.internal/api/v1/health"
```
*(Or local staging instance `http://127.0.0.1:8000/api/v1/health`)*
- **Expected HTTP Status:** `200 OK`
- **Expected Payload:**
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
- **Safety Assertion:** Staging fails startup immediately if credentials are missing or if in-memory repositories leaked.

### 7.2 Frontend Single Page Application Verification
1. Access `https://staging.orqestra.internal` (or `http://127.0.0.1:4173`).
2. Open Browser Console: verify **zero unhandled Promise rejections or 42702 errors**.
3. Verify Realtime WebSocket indicator in header: displays green pulse indicator (Phoenix channel connected).

---

## 8. Function-Level Rollback Procedure (Data-Preserving)

If unexpected issues arise with the newly deployed function, the operator must **NOT** restore the entire database (which would wipe out new customer orders or transactions). Instead, execute a function-level rollback.

### 8.1 Rollback Method: Emergency Function Replacement
Execute the following SQL directly in PostgreSQL or via a rollback migration:

```sql
-- Replaces adjust_stock_atomic with safe fallback or previous definition without touching tables
CREATE OR REPLACE FUNCTION public.adjust_stock_atomic(
    p_business_id UUID,
    p_product_id UUID,
    p_quantity_change INT,
    p_movement_type stock_movement_type,
    p_notes TEXT,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    inventory_id UUID,
    product_id UUID,
    new_quantity INT,
    movement_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
#variable_conflict error
DECLARE
    v_inv_id UUID;
    v_current_qty INT;
    v_new_qty INT;
    v_movement_id UUID;
    v_actor_id UUID;
BEGIN
    -- Fallback body: Safe qualifications without breaking table data
    SELECT inv.id, inv.quantity_on_hand INTO v_inv_id, v_current_qty
    FROM public.inventory inv
    WHERE inv.business_id = p_business_id AND inv.product_id = p_product_id
    FOR UPDATE;

    v_new_qty := v_current_qty + p_quantity_change;
    IF v_new_qty < 0 THEN
        RAISE EXCEPTION 'Negative quantity disallowed';
    END IF;

    UPDATE public.inventory inv
    SET quantity_on_hand = v_new_qty, updated_at = timezone('utc', now())
    WHERE inv.id = v_inv_id;

    RETURN QUERY SELECT v_inv_id, p_product_id, v_new_qty, gen_random_uuid();
END;
$$;
```

### 8.2 Reverting CLI Migration Ledger
```bash
npx supabase migration repair --status reverted --remote=vwlwbwwrumsmjqeavvxk 20261115000001
```
- **Purpose:** Marks migration `20261115000001` as reverted in `supabase_migrations.schema_migrations`.
- **Outcome:** Preserves all 10 tables, orders, products, customers, and invoices while resetting the CLI migration pointer.

---

## 9. Full Database Disaster Recovery Procedure

In the catastrophic event of unrecoverable database corruption, restore from pre-deployment backups:

```bash
# 1. Restore public schema DDL (Requires psql or Supabase direct connection)
psql "postgresql://postgres:<PASSWORD>@db.vwlwbwwrumsmjqeavvxk.supabase.co:5432/postgres" -f backup_staging_schema_20261115.sql

# 2. Restore staging data records
psql "postgresql://postgres:<PASSWORD>@db.vwlwbwwrumsmjqeavvxk.supabase.co:5432/postgres" -f backup_staging_data_20261115.sql
```
> [!CAUTION]
> Full database restoration overwrites public schema tables and rolls back all transactions created after the backup timestamp. Use only as a last-resort recovery mechanism.

---

## 10. Pre-Deployment & Post-Deployment Acceptance Criteria

### Pre-Deployment Acceptance Gate
- [ ] Git working tree is clean and diffs verified (only intended patch and tests).
- [ ] Linked project confirmed as `vwlwbwwrumsmjqeavvxk` via `linked-project.json` and `project-ref`.
- [ ] Schema backup (`backup_staging_schema_20261115.sql`) exceeds 10 KB and contains required entities.
- [ ] Data backup (`backup_staging_data_20261115.sql`) exceeds 1 KB.
- [ ] Cryptographic checksums generated and recorded in deployment audit log.
- [ ] `supabase migration repair` commands executed for versions `20261022000001` through `20261023000004`.
- [ ] `supabase migration list --remote=vwlwbwwrumsmjqeavvxk` reports exactly 6 Applied, 1 Pending.

### Post-Deployment Acceptance Gate
- [ ] `supabase db push --remote=vwlwbwwrumsmjqeavvxk` exits with code `0`.
- [ ] `pg_proc` definition verifies `#variable_conflict error` and qualified column predicates.
- [ ] Execution privileges confirmed revoked from `anon` and `public`.
- [ ] Smoke restock (`SMK-02`) on `STG-SMOKE-4F` succeeds with HTTP 200 and zero 42702 errors.
- [ ] Smoke deduction (`SMK-03`) and oversell rejection (`SMK-04`) succeed.
- [ ] Phase 4A records (`STG-1890`, stock 18) remain strictly unchanged (`SMK-06`).
- [ ] Backend health probe returns `"status": "healthy"` and `"database": "operational"`.
- [ ] Browser console exhibits zero uncaught exceptions; Realtime WebSocket indicator is active.

---

## 11. Actions Requiring Explicit User Approval

The following specific operations **MUST NOT** be executed until you provide explicit authorization:

1. **Remote Schema & Data Backup:** Executing `npx supabase db dump --remote=vwlwbwwrumsmjqeavvxk`.
2. **Remote Migration Ledger Repair:** Executing `npx supabase migration repair --status applied --remote=vwlwbwwrumsmjqeavvxk ...`.
3. **Remote Migration Push:** Executing `npx supabase db push --remote=vwlwbwwrumsmjqeavvxk`.
4. **Git Commit & Push:** Creating a Git commit for the patch migration and pushing to `origin/master`.
5. **Staging Smoke Testing:** Creating `STG-SMOKE-4F` and invoking remote RPC calls.

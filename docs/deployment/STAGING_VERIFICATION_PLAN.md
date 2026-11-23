# ORQESTRA | Staging Integration and Security Verification Plan

This document establishes the architecture, test harness design, environment discovery results, and operational runbooks for verifying Orqestra's database transactions, tenant isolation, invoice integrity, storage access, and AI endpoint protections against isolated infrastructure.

---

## 1. Environment Discovery & Baseline Assessment

### 1.1 Local Host Inspection
Exact PowerShell discovery commands executed on the host system:

| Check | Command | Result | Implications |
|---|---|---|---|
| PostgreSQL Client & Utilities | `'psql', 'pg_isready' \| ForEach-Object { "$_ : $([bool](Get-Command $_ -ErrorAction SilentlyContinue))" }` | `psql : False`<br>`pg_isready : False` | Direct PostgreSQL CLI utilities unavailable. |
| Container Engine | `'docker', 'podman' \| ForEach-Object { "$_ : $([bool](Get-Command $_ -ErrorAction SilentlyContinue))" }` | `docker : False`<br>`podman : False` | No container runtime available on host. |
| Supabase CLI | `'supabase' \| ForEach-Object { "$_ : $([bool](Get-Command $_ -ErrorAction SilentlyContinue))" }` | `supabase : False` | Local Supabase emulation stack unavailable. |
| Port 5432 Listener | `Get-NetTCPConnection -LocalPort 5432 -ErrorAction SilentlyContinue` | Exit code 1 (None) | No local database instance running. |
| Host Services | `Get-Service *postgres*, *docker* -ErrorAction SilentlyContinue` | 0 matching services | No PostgreSQL or Docker daemon registered. |
| Active Secret Files | `Get-ChildItem -Path . -Filter *.env* -Recurse -Depth 2` | Only `.env.example` templates exist | Zero live credentials exposed on filesystem. |

**Discovery Conclusion:** The current local development host does not possess an active PostgreSQL engine, Docker daemon, or Supabase CLI. Under strict safety rules, no external infrastructure was installed.

---

## 2. Migration Order and Architectural Verification

All 6 migrations in `supabase/migrations/` have been audited in sequence:

1. `20261022000001_core_schema.sql`
   - **Schema Foundation:** Creates custom enums (`app_role`, `order_status`, `invoice_status`, `stock_movement_type`) and 10 core tables: `businesses`, `business_members`, `products`, `inventory`, `customers`, `orders`, `order_items`, `invoices`, `stock_movements`, `audit_logs`.
   - **Multi-Tenant Composite Keys:** Enforces tenant boundary at foreign key definition (`fk_order_items_business_order`, `fk_order_items_business_product`, `fk_inventory_business_product`, `fk_invoices_business_customer`, `fk_invoices_business_order`, `fk_stock_movements_business_product`).
   - **Data Types & Constraints:** Currency stored as ISO string, financial quantities use exact `NUMERIC(12, 2)` with non-negative check constraints (`CHECK (unit_price >= 0)`).

2. `20261022000002_row_level_security.sql`
   - **RLS Activation:** Explicitly enabled on all 10 core tables.
   - **Non-Recursive Helper Functions:** `get_auth_user_id()`, `get_business_member_role()`, `has_business_role()` declared with `SECURITY DEFINER` and `SET search_path = public`.
   - **Execution Grants:** Execution permissions strictly revoked from `PUBLIC` and granted only to `authenticated, service_role`.
   - **Privilege Escalation Protection:** Admin role can only invite staff; assigning `admin` or `owner` strictly requires an existing `owner`.
   - **Trigger-Enforced Immutability:** `trg_stock_movements_immutable` and `trg_audit_logs_immutable` raise database exceptions on any `UPDATE` or `DELETE`.

3. `20261023000001_operations_transactions.sql`
   - **Enum Extension:** Adds `'rejected'` to `order_status` safely using `ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'rejected'`.
   - **Atomic Operations:** Implements `adjust_stock_atomic`, `approve_order_atomic`, and `cancel_order_atomic`.
   - **Concurrency & Deadlock Prevention:** Sorts order items by `product_id` prior to locking inventory rows with `FOR UPDATE`.
   - **Independent Authorization:** RPCs independently query `has_business_role` and enforce anti-spoofing identity matching between caller token and actor ID.

4. `20261023000002_realtime_publications.sql`
   - **Publication Creation:** Idempotently ensures `supabase_realtime` publication exists.
   - **Replica Identity Full:** Sets `REPLICA IDENTITY FULL` on `products`, `inventory`, `orders`, `stock_movements` to include `business_id` in WAL payloads for tenant-scoped Realtime filtering.

5. `20261023000003_invoices_and_allocation.sql`
   - **Realtime Integration:** Configures `REPLICA IDENTITY FULL` on `public.invoices` and publishes to `supabase_realtime`.
   - **Sequential Allocation:** Defines `allocate_invoice_atomic` with business-scoped sequence generation (`INV-YYYYMM-XXXX`).

6. `20261023000004_invoice_snapshots_and_constraints.sql`
   - **Uniqueness Partial Index:** `CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_business_order_unique ON public.invoices(business_id, order_id) WHERE order_id IS NOT NULL;`
   - **Immutable Snapshots:** Adds nullable `line_items_snapshot JSONB` and `customer_snapshot JSONB`.
   - **Hardened Lock Ordering:** Locks parent `public.businesses` row first before locking `public.orders`, establishing strict hierarchical lock ordering.
   - **Resilient Fallback:** Repository and PDF service gracefully fall back to live records when snapshot columns are `NULL` on legacy invoices.

---

## 3. Staging Test Suite Audit (12 Scenarios)

Every test in [test_postgres_staging.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_postgres_staging.py) has been audited for genuine database execution:

| Scenario # | Tested Behavior | Real DB Connection | Executes Actual SQL | Required Migrations / Functions | Success Assertion | Current Status | Safeguards & Teardown |
|---|---|---|---|---|---|---|---|
| **01** | Clean Migration Execution | Yes (`staging_connection`) | Yes (Iterates all 6 migration files, executes raw DDL) | Migrations 1 through 6 | 10 core tables in `information_schema.tables`, 4 RPCs in `pg_proc` | SKIPPED (No local DB) | Validates DB name has `test`/`staging` marker before applying |
| **02** | Composite FK Relationships | Yes | Yes (Creates 2 businesses, 1 product, tries cross-insert) | Migration 1 (`fk_inventory_business_product`) | Catches SQLSTATE `23503` (foreign key violation) | SKIPPED | Automated teardown |
| **03** | Atomic Stock Lifecycle | Yes | Yes (Calls `approve_order_atomic` and `cancel_order_atomic`) | Migrations 1, 2, 3 | Stock is deducted (-25) then restored (+25); movements logged | SKIPPED | `synthetic_business` fixture teardown |
| **04** | Invoice Allocation Idempotency | Yes | Yes (Calls `allocate_invoice_atomic` twice on same order) | Migrations 1, 3, 5, 6 | `res1['id'] == res2['id']`, `res2['is_existing'] == True`, count = 1 | SKIPPED | `synthetic_business` fixture teardown |
| **05** | Concurrent Allocation | Yes (5 independent threads with 5 separate connections) | Yes (Calls `allocate_invoice_atomic` concurrently) | Migrations 5, 6 (`FOR UPDATE` on businesses) | All 5 succeed, 0 deadlocks, 5 unique sequential invoice numbers | SKIPPED | Independent connection cleanup |
| **06** | Invoice Numbering & Rollover | Yes | Yes (Inserts prior month invoice, attempts duplicate) | Migrations 1, 5, 6 | Unique violation on duplicate number in same tenant | SKIPPED | `synthetic_business` fixture teardown |
| **07** | Rollback on Injected Failure | Yes | Yes (Calls `approve_order_atomic` with insufficient stock) | Migration 3 (`approve_order_atomic`) | Raises exception, inventory unreduced, order remains pending | SKIPPED | `synthetic_business` fixture teardown |
| **08** | Snapshot Immutability | Yes | Yes (Mutates customer & product after invoice allocation) | Migration 6 (`customer_snapshot`, `line_items_snapshot`) | Invoice snapshots retain original name and line prices | SKIPPED | `synthetic_business` fixture teardown |
| **09** | Cross-Business Isolation (RLS) | Yes | Yes (Sets `role = 'authenticated'` and `jwt.claim.sub` to Tenant A) | Migration 2 (RLS policies on products) | Query on Tenant B returns 0 rows | SKIPPED | Automated session reset |
| **10** | Direct RPC Authorization | Yes | Yes (Calls `adjust_stock_atomic` as unauthorized user) | Migrations 2, 3 (`has_business_role`) | Catches SQLSTATE `42501` (access denied) | SKIPPED | Automated session reset |
| **11** | Audit-Log Immutability | Yes | Yes (Attempts `UPDATE` and `DELETE` on `audit_logs`) | Migration 2 (`trg_audit_logs_immutable`) | Both raise `strictly immutable` exception | SKIPPED | `synthetic_business` fixture teardown |
| **12** | Duplicate Invoice Detection | Yes | Yes (Runs pre-migration duplicate check query) | Migration 6 (`uq_invoices_business_order_unique`) | Duplicate count is 0 | SKIPPED | Pre-index verification |

---

## 4. Local Environment Plan (PostgreSQL Staging)

When approved by the user, the least-complex local PostgreSQL setup is a temporary, isolated local container or portable PostgreSQL instance.

### 4.1 Multi-Layered Safety Interlocks Implemented in Test Harness
1. **Host Safety Interlock:** [validate_safe_test_database](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_postgres_staging.py#L50-L76) strictly validates that the target host is a local loopback interface (`localhost`, `127.0.0.1`, `::1`). Any attempt to point to an external hostname, cloud provider, or remote IP is blocked.
2. **Database Name Interlock:** The database name must explicitly contain an approved test marker (`test`, `staging`, `disposable`, `sandbox`) and is strictly forbidden from matching default or production names (`postgres`, `template1`, `production`, `prod`, `main`, `live`, `master`).
3. **Data Safety Interlock (Pre-Flight Cleanliness):** [verify_disposable_database_clean](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_postgres_staging.py#L79-L99) inspects existing tables on connect. If non-test businesses are detected, the runner immediately halts to prevent data destruction.
4. **Credential Masking:** [sanitize_db_url](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_postgres_staging.py#L38-L47) strips credentials and masks passwords (`***`) across all logging and error outputs.

### 4.2 Approved Setup Instructions (To Be Executed ONLY After Explicit Permission)

#### Option A: Ephemeral Docker Container (Recommended)
```powershell
# 1. Generate an ephemeral, cryptographically random password for the test session
$EphemeralPass = [Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 256) })) -replace '[/+=]', 'x'

# 2. Start disposable test container with isolated port, scram-sha-256, and random password
docker run --name orqestra-staging-db `
  -e POSTGRES_PASSWORD=$EphemeralPass `
  -e POSTGRES_DB=orqestra_staging_test `
  -e POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256 --auth-local=scram-sha-256" `
  -p 5433:5432 -d postgres:16-alpine

# 3. Install client driver in test virtualenv
backend\.venv\Scripts\pip install psycopg[binary]

# 4. Configure local environment variable with ephemeral password
$env:STAGING_DATABASE_URL="postgresql://postgres:${EphemeralPass}@127.0.0.1:5433/orqestra_staging_test"

# 5. Execute integration test suite
backend\.venv\Scripts\pytest backend\app\tests\test_postgres_staging.py -v

# 6. Complete teardown, wipe secrets, and destroy container
docker stop orqestra-staging-db
docker rm orqestra-staging-db
Remove-Item Env:\STAGING_DATABASE_URL
Clear-Variable EphemeralPass -ErrorAction SilentlyContinue
```

#### Option B: Standalone Portable Local PostgreSQL (Without Docker)
```powershell
# 1. Generate ephemeral session password and write to temporary restricted file
$EphemeralPass = [Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 256) })) -replace '[/+=]', 'x'
$PwFile = "$env:TEMP\pg_init_pw_$([guid]::NewGuid().ToString('N')).txt"
Set-Content -Path $PwFile -Value $EphemeralPass -Encoding ASCII

# 2. Initialize disposable cluster using SCRAM-SHA-256 authentication (NEVER trust authentication)
initdb -D "$env:TEMP\orqestra_test_cluster" -U postgres -A scram-sha-256 --pwfile="$PwFile"
Remove-Item -Force $PwFile

# 3. Start temporary cluster on isolated port 5433
pg_ctl -D "$env:TEMP\orqestra_test_cluster" -o "-p 5433" start

# 4. Create dedicated disposable test database
createdb -p 5433 -U postgres orqestra_staging_test

# 5. Set environment and execute
$env:STAGING_DATABASE_URL="postgresql://postgres:${EphemeralPass}@127.0.0.1:5433/orqestra_staging_test"
backend\.venv\Scripts\pytest backend\app\tests\test_postgres_staging.py -v

# 6. Complete teardown & destroy cluster directory
pg_ctl -D "$env:TEMP\orqestra_test_cluster" stop
Remove-Item -Recurse -Force "$env:TEMP\orqestra_test_cluster"
Remove-Item Env:\STAGING_DATABASE_URL
Clear-Variable EphemeralPass -ErrorAction SilentlyContinue
```

---

## 5. Scope Separation: PostgreSQL vs Cloud / Supabase Auth

To prevent false assumptions during staging verification, tests are partitioned into distinct operational scopes:

| Scope | Requires Local PostgreSQL | Requires Supabase Cloud / Remote Auth | Verification Approach |
|---|---|---|---|
| **SQL Schema & Foreign Keys** | Yes | No | Direct DDL/DML in [test_postgres_staging.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_postgres_staging.py). |
| **Atomic Transactions & Locks** | Yes | No | Real PostgreSQL concurrency harness in [test_postgres_staging.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_postgres_staging.py). |
| **RLS Policy Engine** | Yes | No | Simulates Supabase session variables (`SET LOCAL role = 'authenticated'`, `SET LOCAL request.jwt.claim.sub = '...'`). |
| **JWT Verification** | No | No | Offline cryptographic verification with PyJWT in [test_jwt_verification.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_jwt_verification.py). |
| **Realtime WebSockets** | No | Yes (Supabase Realtime server) | Mocked in unit/frontend tests; verified schema-level via `REPLICA IDENTITY FULL` and publications. |
| **AI LLM Extraction** | No | Yes (External provider) | Mocked provider responses in [test_phase5_ai_invoices.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_phase5_ai_invoices.py) to avoid external paid API calls. |

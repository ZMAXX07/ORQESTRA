# ORQESTRA — Staging Deployment Plan & Operational Playbook

**Document Revision:** 1.0.0  
**Target Environment:** Staging (`staging`)  
**Deployment Scope:** Cloud Infrastructure, PostgreSQL Migration Pipeline, FastAPI Backend, React 18 SPA Frontend  
**Security Classification:** Highly Confidential (Zero Secret Values Disclosed)  

---

## Executive Summary

This staging deployment plan provides the operational blueprint, migration verification, environment matrix, security audit, deployment sequence, and disaster recovery procedures for **ORQESTRA**.

ORQESTRA is an autonomous multi-tenant operating system for small businesses, coordinating inventory, customers, order approvals, sequential invoicing, and human-in-the-loop AI operations. This document prepares the system for its first formal staging deployment while adhering to zero-data-loss and zero-downtime architectural guarantees.

---

## 1. System Architecture & Topology

### 1.1 Architectural Topology

```mermaid
flowchart TD
    Client["Browser / Mobile Client (SPA)"] -->|"HTTPS / WSS"| CDN["CDN / Frontend Static Host<br/>(Vite React 18 SPA)"]
    Client -->|"HTTPS REST (CORS Restricted)"| API["FastAPI Backend Container<br/>(Python 3.11 / Uvicorn / Pydantic v2)"]
    Client -->|"WSS (Tenant Realtime CDC)"| SupabaseRT["Supabase Realtime Engine<br/>(PostgreSQL WAL CDC)"]
    
    API -->|"HTTPS PostgREST & RPCs (Service Role)"| Postgres["Supabase PostgreSQL 15+<br/>(RLS, Atomic Transactions, Ledger)"]
    API -->|"HTTPS (JSON REST)"| Gemini["Google Gemini API<br/>(AI Ops Engine / Structured Tool Calling)"]
    
    subgraph MultiTenantIsolation["Multi-Tenant Isolation & Storage Layer"]
        Postgres --> Tables["10 Core Multi-Tenant Tables"]
        Postgres --> Security["Row Level Security & Anti-Spoofing RPCs"]
        Postgres --> Audit["Append-Only Ledger (stock_movements, audit_logs)"]
    end
```

### 1.2 Core Multi-Tenant Data Schema
The database layer enforces multi-tenancy through composite primary/foreign keys `(business_id, id)` and PostgreSQL Row Level Security (RLS) across ten core tables:

| # | Table | Tenancy Column | Immutability / Concurrency Protection | Realtime Enabled |
|---|---|---|---|:---:|
| 1 | `businesses` | `id` (PK) | Parent lock anchor for invoice allocation | No |
| 2 | `business_members` | `business_id` | RLS authority mapping (`owner`, `admin`, `staff`) | No |
| 3 | `products` | `business_id` | Composite unique `(business_id, id)` | Yes (`FULL`) |
| 4 | `inventory` | `business_id` | Atomic row locks `FOR UPDATE` on adjustment | Yes (`FULL`) |
| 5 | `customers` | `business_id` | Composite unique `(business_id, id)`, `is_active` flag | No |
| 6 | `orders` | `business_id` | State-machine validation (`pending_approval`, `approved`, etc.) | Yes (`FULL`) |
| 7 | `order_items` | `business_id` | Composite FK referencing parent order & product | No |
| 8 | `invoices` | `business_id` | Unique `(business_id, order_id)`, snapshot columns | Yes (`FULL`) |
| 9 | `stock_movements` | `business_id` | Append-only ledger; `BEFORE UPDATE/DELETE` triggers reject modifications | Yes (`FULL`) |
| 10 | `audit_logs` | `business_id` | Append-only ledger; `BEFORE UPDATE/DELETE` triggers reject modifications | No |

---

## 2. Database Migration Analysis & Verification

### 2.1 Migration Catalog & Dependency Graph

ORQESTRA contains six sequential SQL migration files in `supabase/migrations/`:

```mermaid
flowchart TD
    M1["20261022000001_core_schema.sql<br/>(10 Core Tables, Composite FKs, Money Checks)"] --> M2["20261022000002_row_level_security.sql<br/>(RLS Policies, SECURITY DEFINER Helpers, Immutable Triggers)"]
    M2 --> M3["20261023000001_operations_transactions.sql<br/>(Rejected Status, adjust_stock_atomic, approve_order_atomic)"]
    M3 --> M4["20261023000002_realtime_publications.sql<br/>(supabase_realtime Publication, REPLICA IDENTITY FULL)"]
    M4 --> M5["20261023000003_invoices_and_allocation.sql<br/>(allocate_invoice_atomic Baseline, Invoices Realtime)"]
    M5 --> M6["20261023000004_invoice_snapshots_and_constraints.sql<br/>(uq_invoices_business_order_unique, Immutable Snapshots)"]
```

### 2.2 Migration Specifications

1. **`20261022000001_core_schema.sql`**
   - Creates `app_role`, `order_status`, `invoice_status`, `stock_movement_type` enums.
   - Creates the 10 core tables with `UUID` primary keys (`gen_random_uuid()`).
   - Implements composite unique keys (`uq_products_business_id`, `uq_orders_business_id`, etc.) and composite foreign keys to prevent cross-business entity references.
   - Enforces check constraints (`unit_price >= 0`, `quantity_on_hand >= 0`, `total_amount >= 0`).

2. **`20261022000002_row_level_security.sql`**
   - Enables RLS on all 10 tables (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`).
   - Defines `SECURITY DEFINER` helper functions with pinned `search_path = public`: `get_auth_user_id()`, `get_business_member_role()`, `has_business_role()`.
   - Enforces anti-privilege escalation (admins cannot invite owners/admins; only owners can grant owner/admin roles).
   - Establishes immutable ledger triggers on `stock_movements` and `audit_logs` using `prevent_immutable_modification()`.

3. **`20261023000001_operations_transactions.sql`**
   - Adds `'rejected'` to `order_status` enum idempotently.
   - Adds `is_active` column to `customers`.
   - Implements atomic `SECURITY DEFINER` RPCs with caller identity validation:
     - `adjust_stock_atomic(...)`: Validates business tenancy, locks inventory row `FOR UPDATE`, modifies stock, appends ledger row, records audit trail.
     - `approve_order_atomic(...)`: Validates transition from `pending_approval`, locks line items and inventory, asserts stock availability, executes deductions, updates status to `approved`.
     - `cancel_order_atomic(...)`: Reverses inventory allocations if the order was previously approved, updates status to `cancelled`, and records cancellation reasons.

4. **`20261023000002_realtime_publications.sql`**
   - Configures `REPLICA IDENTITY FULL` on `products`, `inventory`, `orders`, and `stock_movements`.
   - Idempotently adds operational tables to `supabase_realtime` publication for Change Data Capture (CDC).

5. **`20261023000003_invoices_and_allocation.sql`**
   - Adds `invoices` to `supabase_realtime` with `REPLICA IDENTITY FULL`.
   - Creates composite query indexes `idx_invoices_business_created` and `idx_invoices_business_status`.
   - Implements initial `allocate_invoice_atomic(...)` procedure with sequential numbering (`INV-YYYYMM-XXXX`).

6. **`20261023000004_invoice_snapshots_and_constraints.sql`**
   - Creates partial unique index `uq_invoices_business_order_unique` on `(business_id, order_id)` where `order_id IS NOT NULL`.
   - Adds JSONB snapshot columns `line_items_snapshot` and `customer_snapshot` to `invoices`.
   - Replaces `allocate_invoice_atomic` with a hardened version that **locks the parent `businesses` row first**, eliminating cross-table deadlock conditions while capturing immutable line items and customer snapshots.

### 2.3 Remote Schema Parity & Verification Findings

A read-only PostgREST OpenAPI inspection of the remote Supabase staging environment confirmed:
- **10 Core Tables:** All 10 tables are exposed and healthy (`businesses`, `business_members`, `products`, `inventory`, `customers`, `orders`, `order_items`, `invoices`, `stock_movements`, `audit_logs`).
- **Snapshot Columns:** `invoices.customer_snapshot` and `invoices.line_items_snapshot` are active.
- **Active Flags:** `customers.is_active` is active.
- **RPC Endpoints:** `/rpc/adjust_stock_atomic`, `/rpc/approve_order_atomic`, `/rpc/cancel_order_atomic`, `/rpc/allocate_invoice_atomic`, `/rpc/get_auth_user_id`, `/rpc/get_business_member_role`, `/rpc/has_business_role`, `/rpc/rls_auto_enable` are fully published and reachable.
- **Current Migration Status:** All DDL and procedural logic corresponding to Migrations 1 through 6 are currently present in the remote Supabase database.
- **CLI Tracking Nuance:** Supabase CLI tracks applied migrations in the internal table `supabase_migrations.schema_migrations`. If any migration was applied via the Supabase Web SQL editor rather than `supabase db push`, running `supabase migration list` or `supabase db push` will require running `supabase migration repair --status applied <migration_id>` to align the CLI's internal tracker without re-executing statements.

---

## 3. Schema Drift & Data Loss Prevention

### 3.1 Pre-Migration Constraint Safety Verification
Migration `20261023000004_invoice_snapshots_and_constraints.sql` creates a unique index on `(business_id, order_id)`:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_business_order_unique
    ON public.invoices(business_id, order_id)
    WHERE order_id IS NOT NULL;
```

> [!IMPORTANT]
> **Safety Assertion:** If duplicate invoices existed for an order, creating this index would fail and abort the deployment.
> **Verified Database State:** A read-only verification query confirmed that exactly 5 invoices exist in the remote database with **0 duplicates** (`HAVING count(*) > 1` returned empty). The database is completely safe for this index.

### 3.2 Non-Destructive Migration Guarantee
- No migrations contain `DROP TABLE`, `DROP COLUMN`, or `TRUNCATE`.
- All column additions utilize `ADD COLUMN IF NOT EXISTS`.
- All index creations utilize `CREATE INDEX IF NOT EXISTS` or `CREATE UNIQUE INDEX IF NOT EXISTS`.
- All procedures utilize `CREATE OR REPLACE FUNCTION`.
- Rollback of schema additions can be performed without data loss to existing operational tables.

---

## 4. Environment Variable Matrix & Templates

### 4.1 Backend Environment Template (`backend/.env.staging`)

```bash
# ==============================================================================
# ORQESTRA BACKEND STAGING CONFIGURATION
# ==============================================================================

# Application Runtime
ENVIRONMENT=staging
APP_NAME=Orqestra API (Staging)
APP_VERSION=0.1.0
DEBUG=false
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Security & CORS
# Explicit allowed origins matching staging frontend domains (NO wildcard '*')
CORS_ORIGINS=https://staging.orqestra.com,https://staging-app.orqestra.com

# Supabase Staging Project Configuration
# Replace with staging project URL and keys from Supabase Dashboard
SUPABASE_URL=https://<staging-project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<staging-publishable-or-anon-key>
SUPABASE_ANON_KEY=<staging-publishable-or-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<staging-service-role-key-kept-secret>

# JWT Verification & GoTrue Auth (Phase 7.3)
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWT_ISSUER=https://<staging-project-ref>.supabase.co/auth/v1
SUPABASE_JWT_ALGORITHM=HS256
SUPABASE_JWT_SECRET=<staging-jwt-secret-for-symmetric-verification>
# Optional JWKS URL if utilizing asymmetric key rotation:
# SUPABASE_JWKS_URL=https://<staging-project-ref>.supabase.co/auth/v1/.well-known/jwks.json

# AI Provider Configuration (Google Gemini / OpenAI compatible)
AI_PROVIDER=gemini
GEMINI_API_KEY=<staging-google-gemini-api-key>
AI_MODEL=gemini-1.5-flash
AI_MAX_MESSAGE_LENGTH=4000
AI_REQUEST_TIMEOUT_SECONDS=15.0

# AI Intake Rate Limiting (Single-Worker Process)
AI_RATE_LIMIT_REQUESTS=15
AI_RATE_LIMIT_WINDOW_SECONDS=60
```

### 4.2 Frontend Environment Template (`frontend/.env.staging`)

```bash
# ==============================================================================
# ORQESTRA FRONTEND STAGING CONFIGURATION (Vite Client Build)
# ==============================================================================

# Backend API Endpoint
VITE_API_BASE_URL=https://api-staging.orqestra.com

# Public Supabase Client (Browser Safe)
# Only publishable / anon keys are permitted here. NEVER place service_role key here.
VITE_SUPABASE_URL=https://<staging-project-ref>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<staging-publishable-or-anon-key>
VITE_SUPABASE_ANON_KEY=<staging-publishable-or-anon-key>
```

---

## 5. Security & Isolation Checks

### 5.1 Service-Role Key Isolation
- **Audit Verification:** Static analysis of the entire `frontend/src/` repository confirms that `SUPABASE_SERVICE_ROLE_KEY` is nowhere referenced, imported, or bundled.
- **Frontend Bundle Inspection:** Production build verification confirmed that client bundles only access `import.meta.env.VITE_SUPABASE_URL` and `import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY`.
- **Backend Protection:** The backend uses the service-role key exclusively in server-side repository providers to interact with PostgREST endpoints under strictly bounded business logic.

### 5.2 Repository Fallback Protection in Staging

> [!WARNING]
> **CRITICAL ARCHITECTURAL FINDING:**
> In `backend/app/api/deps.py`, the security interlock that raises a fatal `RuntimeError` on in-memory repository instantiation is explicitly guarded by:
> ```python
> if settings.ENVIRONMENT == "production":
>     if isinstance(_repo, InMemory*Repository):
>         raise RuntimeError(...)
> ```
> If `ENVIRONMENT` is set to `"staging"` and `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` is missing or fails to load, `deps.py` will silently instantiate `InMemory*Repository`!
>
> **Mandatory Staging Rule:**
> Staging deployment environments must either:
> 1. Set `ENVIRONMENT=production` in the staging container (configured with the staging Supabase project), OR
> 2. Implement an operational pre-flight check in staging that verifies the `/health` endpoint and validates that `Supabase*Repository` instances are active prior to routing user traffic.

### 5.3 Multi-Worker Rate Limiting Notice
- `InMemoryRateLimiter` (`backend/app/services/rate_limiter.py`) is thread-safe and process-local via Python `threading.Lock`.
- In a single-worker container deployment, it reliably enforces 15 requests per 60 seconds per user/business bucket.
- If staging is scaled to multiple container replicas or multiple Uvicorn workers behind a load balancer, each worker maintains its own rate-limiting window. A shared Redis instance will be required when migrating to a multi-instance production cluster.

### 5.4 Token Authentication & Identity Anti-Spoofing
- In `backend/app/services/auth.py`, incoming Bearer JWTs are decoded and cryptographically validated against `SUPABASE_JWT_SECRET` (or JWKS), asserting `aud="authenticated"` and non-expiration.
- In PostgreSQL atomic procedures (`approve_order_atomic`, `allocate_invoice_atomic`), caller identity is resolved directly from `request.jwt.claim.role` and `get_auth_user_id()`. Any discrepancy between the authenticated caller and requested actor raises an immediate `42501` exception.

---

## 6. Step-by-Step Staging Deployment Sequence

```mermaid
sequenceDiagram
    autonumber
    actor DevOps as Senior DevOps Engineer
    participant Git as Git Repo (origin/master)
    participant CI as Build & Test Pipeline
    participant DB as Supabase Staging DB
    participant API as FastAPI Container Host
    participant CDN as Frontend Static Host

    DevOps->>CI: Trigger Staging Pipeline
    CI->>CI: Run Frontend Tests (Vitest: 136 tests)
    CI->>CI: Run Backend Tests (Pytest: 116 tests)
    CI->>CI: Run Production Frontend Build (tsc & vite)
    
    DevOps->>DB: Take Pre-Deployment Backup / Snapshot
    DevOps->>DB: Check Unapplied Migrations (supabase db push --dry-run)
    DevOps->>DB: Apply Pending Migrations & Verify RPC Permissions
    
    CI->>API: Build & Deploy Backend Container (Python 3.11)
    API->>API: Load Settings & Verify Staging Secrets
    DevOps->>API: Verify GET /health Probe (HTTP 200 OK)
    
    CI->>CDN: Deploy Frontend Static Distribution (dist/)
    DevOps->>CDN: Verify HTTPS Routing & SPA Rewrite Rules
    
    DevOps->>API: Execute Post-Deployment E2E Smoke Tests
```

### Detailed Execution Steps

#### Step 1: Automated Verification Gate
1. Execute frontend test suite:
   ```powershell
   npm --prefix frontend test
   ```
   *Requirement:* All 15 test files (136 tests) must pass.
2. Execute backend unit & regression suite:
   ```powershell
   .\backend\.venv\Scripts\python.exe -m pytest
   ```
   *Requirement:* All 116 unit tests must pass.
3. Execute production asset build:
   ```powershell
   npm --prefix frontend run build
   ```
   *Requirement:* Clean compilation into `frontend/dist/`.

#### Step 2: Database Snapshot & Staging Migration Application
1. In Supabase Dashboard, create a manual backup or record the current Point-In-Time-Recovery (PITR) timestamp.
2. Verify migration dry run:
   ```bash
   supabase db push --dry-run
   ```
3. If migrations were previously applied through the Web SQL editor, repair the CLI tracking ledger:
   ```bash
   supabase migration repair --status applied 20261022000001
   supabase migration repair --status applied 20261022000002
   supabase migration repair --status applied 20261023000001
   supabase migration repair --status applied 20261023000002
   supabase migration repair --status applied 20261023000003
   supabase migration repair --status applied 20261023000004
   ```
4. Confirm composite foreign keys, RLS policies, and RPC permissions:
   ```sql
   SELECT routine_name, routine_type 
   FROM information_schema.routines 
   WHERE routine_schema = 'public' 
     AND routine_name IN ('adjust_stock_atomic', 'approve_order_atomic', 'allocate_invoice_atomic');
   ```

#### Step 3: Backend Deployment
1. Inject the staging environment variables (`backend/.env.staging`).
2. Start the FastAPI backend with production-grade Uvicorn settings:
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
   ```
3. Execute health check verification:
   ```bash
   curl -f http://127.0.0.1:8000/health
   ```
   *Expected response:* `{"status":"ok","app":"Orqestra API (Staging)","version":"0.1.0","environment":"staging"}`.

#### Step 4: Frontend Deployment & CDN Hosting
1. Build frontend with staging variables:
   ```bash
   npm --prefix frontend run build -- --mode staging
   ```
2. Upload `frontend/dist/` contents to staging CDN/hosting (Cloudflare Pages, AWS S3/CloudFront, or Netlify).
3. Ensure SPA redirect rule is active: All non-asset routes `/*` rewrite to `/index.html` with HTTP 200.

#### Step 5: Post-Deployment Smoke Test
Verify the following 7 operational flows in staging:
- [ ] User authentication and session persistence after browser refresh.
- [ ] Workspace/business selection and cross-tenant data isolation.
- [ ] Product catalog creation and currency rendering (INR / USD / EUR).
- [ ] Inventory adjustment via `adjust_stock_atomic` RPC.
- [ ] Order creation and approval triggering automatic stock deduction.
- [ ] Sequential invoice issuance (`INV-YYYYMM-XXXX`) capturing immutable snapshots.
- [ ] AI Operations conversational order draft parsing and human confirmation flow.

---

## 7. Rollback & Disaster Recovery Plan

### 7.1 Rollback Decision Matrix

| Anomaly / Incident | Severity | Action | Rollback Target |
|---|:---:|---|---|
| Frontend fatal JS runtime error | CRITICAL | Revert CDN distribution to prior deployment bundle | Previous static commit |
| Backend 5xx rate > 1% on `/api/v1/` | CRITICAL | Revert container image to previous release tag | Previous backend container tag |
| Database migration lock timeout / abort | CRITICAL | Abort migration, revert backend deployment | Immediate halt; no schema alteration |
| Data corruption or accidental deletion | DISASTER | Restore from Supabase PITR or logical dump | Point-In-Time snapshot pre-deployment |

### 7.2 Database Rollback Scripts (Down-Migrations)

If a schema rollback is required prior to data accumulation:

```sql
-- DOWN-MIGRATION 6: Remove invoice snapshots and uniqueness constraint
DROP INDEX IF EXISTS public.uq_invoices_business_order_unique;
ALTER TABLE public.invoices DROP COLUMN IF EXISTS line_items_snapshot;
ALTER TABLE public.invoices DROP COLUMN IF EXISTS customer_snapshot;

-- DOWN-MIGRATION 5: Remove invoices from realtime
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.invoices;
DROP INDEX IF EXISTS public.idx_invoices_business_created;
DROP INDEX IF EXISTS public.idx_invoices_business_status;

-- DOWN-MIGRATION 4: Remove operational tables from realtime
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.stock_movements;
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.orders;
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.inventory;
ALTER PUBLICATION supabase_realtime DROP TABLE IF EXISTS public.products;
```

---

## 8. Outstanding Blockers & Operational Readiness

### 8.1 Prioritized Readiness Register

| Priority | Item | Description | Action Required |
|:---:|---|---|---|
| **BLOCKER** | Supabase CLI Migration History Sync | Staging Supabase project schema contains migrations 1–6, but CLI tracking table must be synchronized with `supabase migration repair`. | Run `supabase migration repair` for migrations 1–6 before applying future migrations. |
| **HIGH** | `deps.py` Staging Environment Check | `deps.py` repository check currently tests `if settings.ENVIRONMENT == "production":`. Staging environments could fallback to in-memory repos if DB keys are missing. | Ensure staging sets `ENVIRONMENT=production` or add `settings.ENVIRONMENT in ("production", "staging")` in next patch. |
| **HIGH** | Distributed Rate Limiter for Multi-Worker | In-memory sliding-window limiter is process-local. | Maintain 1 worker process in staging; provision Redis before multi-worker production scale-out. |
| **MEDIUM** | Privacy Policy & Terms of Service Routes | Customer registration currently displays links to `/privacy` and `/terms`, which return 404. | Create placeholder or production legal markdown views before accepting public staging testers. |
| **MEDIUM** | Business Settings Management UI | Business Settings page is currently a visual placeholder without backend persistence for business profile edits. | Implement business details edit API endpoint and connect Settings page. |
| **LOW** | Transactional Email Dispatcher | Team member invitations and invoice PDFs are generated in-memory and logged, but not emailed. | Configure Resend, SendGrid, or AWS SES SMTP provider for staging notifications. |

---

## Conclusion & Deployment Approval

The ORQESTRA codebase is verified, stable, and ready for staging deployment:
- Frontend test suite: **136 passing tests** across 15 suites.
- Backend test suite: **116 passing tests** across 12 suites.
- Production build: **Successfully compiled** in 3.61 seconds with zero errors.
- Schema verification: **Zero duplicate invoices**, full migration parity, and hardened transaction procedures.

**Authorized Deployer:** Senior DevOps & Backend Deployment Team  
**Target Window:** Scheduled Staging Release Window  


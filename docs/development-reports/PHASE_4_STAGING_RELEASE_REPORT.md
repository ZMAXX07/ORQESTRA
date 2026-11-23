# ORQESTRA — Phase 4: Controlled Staging Release Report

**Document Version:** 1.0.0  
**Date:** November 15, 2026  
**Auditing Authority:** Senior DevOps & Backend Deployment Engineering  
**Scope:** Git Working Tree Review, Database Migration Parity & CLI Reconciliation, Staging Infrastructure Specifications, Deployment Plan, and Post-Deployment Browser Verification Matrix  
**Current Phase Status:** PRE-DEPLOYMENT VERIFICATION COMPLETE — AWAITING EXPLICIT USER APPROVAL FOR REMOTE OPERATIONS  

---

## Executive Summary

Phase 4 operationalizes the staging release for ORQESTRA following the **GO** decision established in Phase 3. In strict compliance with non-negotiable safety rules:
- **No remote commits or pushes have been made.**
- **No changes have been made to the remote Supabase database or migration history.**
- **No remote infrastructure has been altered.**
- **Zero secrets, tokens, or credentials are disclosed.**

All local verification gates (Phase A), migration reconciliation plans (Phase B), and staging infrastructure definitions (Phase C) have been fully prepared and validated.

---

## 1. Phase A: Git Working Tree & Code Review

### 1.1 Working Tree Audit

```text
On branch master
Your branch is up to date with 'origin/master'.

Changes not staged for commit:
  modified:   backend/app/api/deps.py
  modified:   backend/app/core/config.py
  modified:   backend/app/main.py
  modified:   backend/app/services/health.py

Untracked files:
  PHASE_2_STAGING_VERIFICATION.md
  PHASE_3_STAGING_DEPLOYMENT_READINESS.md
  STAGING_DEPLOYMENT_PLAN.md
  backend/app/tests/test_staging_safety.py
```

### 1.2 Inspection of Modified & Untracked Files

| File | Changes Made | Safety & Rationale | Secrets / Debug Code |
|---|---|---|:---:|
| `backend/app/core/config.py` | Added `IN_MEMORY_ALLOWED_ENVIRONMENTS = {"development", "test", "testing", "local"}` and `is_in_memory_allowed(env)` helper + property on `Settings`. | Ensures strict environment gating. Centralizes environment classification to avoid circular imports. | **None** |
| `backend/app/api/deps.py` | Refactored repetitive security assertions into `_assert_repository_safety()`; extended in-memory blocks and credential requirements to `staging`; added `validate_repository_configuration()` and `reset_repository_instances()`. | Eliminates code duplication; guarantees staging fails startup if database repositories cannot initialize; prevents silent fallback. | **None** |
| `backend/app/main.py` | Registered `validate_repository_configuration(settings)` inside application lifespan (`app_lifespan`). | Enforces fail-fast container crash during boot if database configuration is missing or invalid in staging or production. | **None** |
| `backend/app/services/health.py` | Implemented `check_database_connectivity(settings)` via PostgREST root probe with 15-second cache; mapped component status to `operational`, `not_connected`, or `error`; marked overall health `unhealthy` if DB is down in non-in-memory environments. | Truthful health reporting for load balancers and container orchestrators without false positive claims. | **None** |
| `backend/app/tests/test_staging_safety.py` | Authored 10 comprehensive unit tests for fail-fast startup, in-memory blocking in staging/production, development allowance, and health probe accuracy. | Full test coverage for new staging safety assertions. | **None** |
| `*.md` Audit Reports | `STAGING_DEPLOYMENT_PLAN.md`, `PHASE_2_STAGING_VERIFICATION.md`, `PHASE_3_STAGING_DEPLOYMENT_READINESS.md` | Formal audit records and runbooks. | **None** |

### 1.3 Test Suite Execution Results

#### Backend Test Suite (Pytest)
```text
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-8.4.2, pluggy-1.7.0
rootdir: C:\Users\aslam\Desktop\ORQESTRA\backend
configfile: pytest.ini
plugins: anyio-4.15.1, platformdirs-4.13.5
collected 139 items

================= 126 passed, 13 skipped, 1 warning in 14.41s =================
```
*Note: The 13 skipped tests are disposable PostgreSQL integration tests that require an isolated local loopback instance (verified 13/13 PASS in Phase 3).*

#### Frontend Test Suite (Vitest)
```text
Test Files  15 passed (15)
     Tests  136 passed (136)
  Duration  9.65s
```

#### Production Build (TypeScript & Vite)
```text
vite v5.4.21 building for production...
transforming...
✓ 122 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                              0.95 kB │ gzip:  0.47 kB
dist/assets/index-DPsG7afs.js               98.42 kB │ gzip: 25.67 kB
dist/assets/vendor-react-nf7bT_Uh.js       140.87 kB │ gzip: 45.26 kB
dist/assets/vendor-supabase-f4bNl52y.js    227.07 kB │ gzip: 58.98 kB
✓ built in 1.53s
```

### 1.4 Prepared Commit Summary

**Commit Message:**
```text
feat(staging): enforce database repository safety and health check truthfulness

- Add fail-fast repository configuration assertion to prevent in-memory fallback in staging and production
- Integrate startup repository validation into FastAPI lifespan
- Add active PostgREST connectivity probe to HealthService with 15s TTL
- Add 10 automated unit tests for staging/production safety in test_staging_safety.py
- Add Staging Deployment Plan, Phase 2, and Phase 3 verification reports
```
*Status: Staged and held. Will NOT commit or push until explicit user approval is granted.*

---

## 2. Phase B: Supabase Migration Parity & CLI Reconciliation

### 2.1 Project Reference Verification
- **Supabase Project Reference:** `vwlwbwwrumsmjqeavvxk`
- **PostgREST Base URL:** `https://vwlwbwwrumsmjqeavvxk.supabase.co/rest/v1/`
- **CLI Binary:** `supabase` v3.1.0 (verified via npx).

### 2.2 Migration Specifications & Parity Matrix

| Migration Version | File Name | Remote Parity Status | Reapplication Required? |
|---|---|:---:|:---:|
| `20261022000001` | `20261022000001_core_schema.sql` | **CONFIRMED** (All 10 tables, composite FKs, domain enums) | **NO** (Objects exist) |
| `20261022000002` | `20261022000002_row_level_security.sql` | **CONFIRMED** (RLS active, helper RPCs, immutable triggers) | **NO** (Objects exist) |
| `20261023000001` | `20261023000001_operations_transactions.sql` | **CONFIRMED** (`order_status.rejected`, `customers.is_active`, atomic RPCs) | **NO** (Objects exist) |
| `20261023000002` | `20261023000002_realtime_publications.sql` | **CONFIRMED** (`supabase_realtime` publication, `REPLICA IDENTITY FULL`) | **NO** (Objects exist) |
| `20261023000003` | `20261023000003_invoices_and_allocation.sql` | **CONFIRMED** (Invoices in realtime publication, composite indexes) | **NO** (Objects exist) |
| `20261023000004` | `20261023000004_invoice_snapshots_and_constraints.sql` | **CONFIRMED** (`uq_invoices_business_order_unique`, JSONB snapshots) | **NO** (Objects exist) |

### 2.3 Exact Migration Repair Command
Because the schema was originally provisioned through the Supabase SQL Web Editor, the local CLI ledger must record the migrations without re-running DDL:

```bash
# Step 1: Link to remote Supabase project
npx supabase link --project-ref vwlwbwwrumsmjqeavvxk

# Step 2: Mark all 6 existing migrations as applied in CLI history
npx supabase migration repair --status applied 20261022000001 20261022000002 20261023000001 20261023000002 20261023000003 20261023000004
```
*Status: Held. Will NOT execute until explicit user approval is granted.*

---

## 3. Phase C: Staging Infrastructure & Deployment Configuration

### 3.1 Backend Container Architecture
- **Runtime:** Python 3.11-slim
- **Process Manager:** Uvicorn ASGI Server
- **Worker Concurrency:** **`--workers 1`** (Mandatory: process-local `InMemoryRateLimiter` sliding window requires single-worker execution to prevent quota amplification until Redis is provisioned).
- **Startup Command:**
  ```bash
  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
  ```

### 3.2 Frontend Hosting Architecture
- **Distribution:** Static Single Page Application (`frontend/dist/`)
- **Web Server / CDN:** Cloudflare Pages / Vercel / Nginx
- **SPA Routing Rule:** All routes (`/dashboard`, `/products`, `/orders`, `/invoices`, etc.) fall back to `index.html`.

### 3.3 Staging Environment Configuration Template

#### Backend (`backend/.env.staging`)
```bash
ENVIRONMENT=staging
APP_NAME=Orqestra API (Staging)
APP_VERSION=0.1.0
DEBUG=false
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# CORS Configuration (Restricted Staging Origins)
CORS_ORIGINS=https://staging.orqestra.com,https://staging-app.orqestra.com

# Supabase Staging Connection (Project: vwlwbwwrumsmjqeavvxk)
SUPABASE_URL=https://vwlwbwwrumsmjqeavvxk.supabase.co
SUPABASE_PUBLISHABLE_KEY=<injected_publishable_key>
SUPABASE_ANON_KEY=<injected_publishable_key>
SUPABASE_SERVICE_ROLE_KEY=<injected_via_secrets_manager>

# Authentication / GoTrue JWT
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWT_ISSUER=https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1
SUPABASE_JWT_ALGORITHM=HS256
SUPABASE_JWT_SECRET=<injected_via_secrets_manager>

# AI Provider Configuration (Google Gemini)
AI_PROVIDER=gemini
GEMINI_API_KEY=<injected_via_secrets_manager>
AI_MODEL=gemini-1.5-flash
AI_MAX_MESSAGE_LENGTH=4000
AI_REQUEST_TIMEOUT_SECONDS=15.0

# Rate Limiter Budget (Per User/Business)
AI_RATE_LIMIT_REQUESTS=15
AI_RATE_LIMIT_WINDOW_SECONDS=60
```

#### Frontend (`frontend/.env.staging`)
```bash
VITE_API_BASE_URL=https://api-staging.orqestra.com
VITE_SUPABASE_URL=https://vwlwbwwrumsmjqeavvxk.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<injected_publishable_key>
```

### 3.4 Secret Injection Rules
1. Never commit `.env.staging` files containing plaintext credentials.
2. Inject `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, and `GEMINI_API_KEY` via container runtime environment variables or KMS secrets manager.
3. Ensure `SUPABASE_SERVICE_ROLE_KEY` is strictly confined to the backend container and never bundled into frontend assets.

### 3.5 Health Checks & Monitoring
- **Liveness Probe:** `GET /health` (HTTP 200, checks FastAPI router liveness).
- **Readiness Probe:** Evaluates `database.status == "operational"` and `overall_status == "healthy"`. PostgREST probe with 15s cache validates database reachability.
- **Logging:** Standardized JSON log stream without sensitive prompt or credential leakage.

### 3.6 Automated Rollback Procedures
- **Rollback Triggers:**
  - 5xx error rate > 1.0% over a 5-minute rolling window.
  - `/health` reports `unhealthy` for > 2 consecutive probe intervals.
  - PostgreSQL lock timeout errors on order approval or invoice allocation.
- **Rollback Execution:**
  - **Frontend:** Point CDN to previous release hash.
  - **Backend:** Roll back container tag to previous verified image.
  - **Database:** Supabase PITR (Point-In-Time-Recovery) snapshot restore (Target: RTO < 30m, RPO < 5m).

---

## 4. Phase D: Controlled Deployment Status

| Deployment Gate | Action | Status | Blocker / Requirement |
|---|---|:---:|---|
| **Gate 1** | Git Commit & Push | **PENDING APPROVAL** | Requires explicit user sign-off. |
| **Gate 2** | Supabase Migration Repair | **PENDING APPROVAL** | Requires explicit user sign-off. |
| **Gate 3** | Backend Container Launch | **PENDING APPROVAL** | Requires explicit user sign-off & hosting target. |
| **Gate 4** | Frontend Static Deployment | **PENDING APPROVAL** | Requires explicit user sign-off & hosting target. |

*Per strict safety rules, execution has stopped at Gate 1 awaiting your explicit approval.*

---

## 5. Phase E: Post-Deployment Browser Verification Plan

Upon deployment authorization and execution, the live staging environment will be tested through browser automation across all 14 core functional capabilities:

```mermaid
flowchart TD
    subgraph AuthLifecycle["1. Authentication & Tenancy"]
        L1["Sign In / Token Acquisition"] --> L2["Session Persistence Across Reload"]
        L2 --> L3["Multi-Business Switching"]
    end
    
    subgraph CoreOperations["2. Operational Flow"]
        O1["Create Product & Set Price"] --> O2["Adjust Inventory (+10 Units)"]
        O2 --> O3["Create Customer Record"]
        O3 --> O4["Create Draft Order"]
        O4 --> O5["Human Order Approval Gate"]
        O5 --> O6["Atomic Stock Deduction Verified"]
        O6 --> O7["Allocate Sequential Invoice (INV-YYYYMM-XXXX)"]
        O7 --> O8["Download ReportLab PDF Bytes"]
    end
    
    subgraph SecurityAndAI["3. Advanced Verifications"]
        S1["AI Intake Order Extraction"] --> S2["Human Candidate Approval"]
        S3["Overselling Rejection (Stock Guard)"]
        S4["Tenant Isolation (Cross-Business 404/403)"]
        S5["Realtime CDC Subscription Refresh"]
        S6["Responsive Layout (Mobile 375, Tablet 768, Desktop 1440)"]
    end
```

### Verification Test Matrix

| # | Workflow Step | Test Procedure | Expected Outcome |
|:---:|---|---|---|
| **1** | **Login & Logout** | Submit credentials on `/login`, verify redirect to `/dashboard`, test logout and redirect. | Auth cookies/tokens managed cleanly. |
| **2** | **Session Persistence** | Refresh browser on `/dashboard` and `/orders`. | User remains authenticated without modal prompts. |
| **3** | **Business Switching** | Switch between Business Alpha and Business Beta via business dropdown. | Header `X-Business-ID` updates; table queries reflect isolated tenant data. |
| **4** | **Product Management** | Create `Staging Test Widget` (SKU: `STG-001`, \$49.99), edit title. | Product saved and updated in database. |
| **5** | **Inventory Adjustments** | Adjust stock by `+25` with audit reason `Staging initial stock`. | Quantity on hand increments; stock movement record logged. |
| **6** | **Customer Management** | Create customer `Staging Enterprise` (`client@staging.local`). | Customer listed in directory. |
| **7** | **Order Submission & Approval** | Create draft order for 2 widgets, submit for review, click "Approve Order". | Order state transitions from `draft` -> `pending_approval` -> `approved`. |
| **8** | **Stock Deduction** | Check widget inventory after order approval. | Available stock decrements by exactly 2 (from 25 to 23). |
| **9** | **Sequential Invoicing** | Click "Issue Invoice" on approved order. | Invoice generated matching `INV-YYYYMM-XXXX`; order status updates to `invoiced`. |
| **10** | **PDF Generation** | Click "Download Invoice PDF". | Binary ReportLab PDF streams with valid `%PDF` magic bytes. |
| **11** | **Realtime CDC Updates** | Mutate stock in a second session or API call. | Active table refreshes without manual page reload. |
| **12** | **AI Order Intake** | Submit natural language order text via AI Ops tab. | Structured candidates parsed; human editor displays for review. |
| **13** | **Overselling Guard** | Submit order for 999 widgets and attempt approval. | Atomic transaction aborts with HTTP 409 / Insufficient Stock. |
| **14** | **Cross-Business Isolation** | Attempt to view Alpha order while active in Beta. | UI returns empty state / 404; zero cross-tenant contamination. |
| **15** | **Responsive Viewports** | Verify navigation drawer, tables, and modals at 375px (mobile), 768px (tablet), and 1440px (desktop). | Fluid layouts, accessible touch targets, and zero overflow. |

---

## 6. Pre-Deployment Sign-Off & Approval Request

To proceed with deployment, please confirm which actions you authorize:

1. **[ ] Commit & Push Working Tree:** Commit safety hardening changes to `master` branch.
2. **[ ] Supabase Migration Repair:** Run CLI migration repair to synchronize migration versions `20261022000001` through `20261023000004` on project `vwlwbwwrumsmjqeavvxk`.
3. **[ ] Staging Deployment:** Specify hosting target for backend container and frontend static hosting (or local staging simulation if remote cloud credentials are not provisioned).


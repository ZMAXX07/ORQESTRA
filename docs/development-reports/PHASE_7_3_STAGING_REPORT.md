# ORQESTRA | Phase 7.3 Supabase Staging Integration Preparation Report

**Date:** 2026-10-23  
**Target Staging Project:** `https://vwlwbwwrumsmjqeavvxk.supabase.co`  
**Phase Status:** Integration Preparation Complete — Safety Gate Engaged (Waiting for User Approval)

---

## 1. Executive Summary & Existing Architecture Verification

Prior to modifying configuration, a comprehensive inspection of the existing codebase, architecture, test harness, and migration files was conducted:

- **Frontend:** React 18, TypeScript 5.4, Vite 5.2. Single Supabase client initialization in [frontend/src/services/supabase.ts](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/src/services/supabase.ts) with full session persistence, reactive auth state subscriptions, and token management in [frontend/src/context/AuthContext.tsx](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/src/context/AuthContext.tsx).
- **Backend:** FastAPI with modular repositories ([backend/app/repositories](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/repositories)). Authentication uses [TokenVerificationService](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/services/auth.py) supporting both symmetric HMAC (`HS256`) and asymmetric JWKS rotation (`RS256`, `ES256`). Authorization uses [AuthorizationService](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/services/authorization.py) with hierarchical roles (`owner` > `admin` > `staff`) and strict tenant isolation.
- **Database Connection Strategy:** The backend interacts with Supabase via the PostgREST REST API over `httpx.AsyncClient` using `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. Direct SQL connections are reserved for migration runners and local integration testing harnesses via `psycopg`.
- **Database Migrations:** Six sequential SQL migrations reside in [supabase/migrations](file:///c:/Users/aslam/Desktop/ORQESTRA/supabase/migrations), implementing 10 core tables with composite foreign keys, RLS policies, trigger-level immutability for audit logs and stock movements, atomic operations, and invoice snapshots.
- **Realtime:** Implemented via [RealtimeContext.tsx](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/src/context/RealtimeContext.tsx) with table filtering, message deduplication, reconnection handlers, and tenant isolation.

---

## 2. Summary of Changes Made in Phase 7.3

All modifications were targeted, minimal, non-destructive, and strictly backward-compatible:

| File | Change Description | Rationale |
|---|---|---|
| [.gitignore](file:///c:/Users/aslam/Desktop/ORQESTRA/.gitignore) | Added explicit entries for `backend/.env*` and `frontend/.env*` | Guarantees that local environment files containing real credentials can never be accidentally committed to Git. |
| [frontend/src/vite-env.d.ts](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/src/vite-env.d.ts) | Added `readonly VITE_SUPABASE_PUBLISHABLE_KEY?: string;` | Provides full TypeScript compiler support for the modern Vite publishable key naming convention. |
| [frontend/src/services/supabase.ts](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/src/services/supabase.ts) | Added support for `VITE_SUPABASE_PUBLISHABLE_KEY` with seamless fallback to `VITE_SUPABASE_ANON_KEY` | Adheres to modern Supabase terminology while preserving complete backward compatibility with existing tests. |
| [frontend/src/components/auth/SignInModal.tsx](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/src/components/auth/SignInModal.tsx) | Updated configuration warning message | References `VITE_SUPABASE_PUBLISHABLE_KEY` in the operator alert banner. |
| [frontend/.env.example](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/.env.example) | Pre-configured staging URL `https://vwlwbwwrumsmjqeavvxk.supabase.co` and added key placeholders | Provides clear documentation for frontend staging setup without exposing secrets. |
| [backend/app/core/config.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/core/config.py) | Added `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_JWT_ISSUER`, `effective_jwt_issuer`, `effective_anon_key`, multi-path `.env` loading, and `settings_customise_sources` | Enforces JWT issuer verification when configured, supports root and backend `.env` files, and prevents developer `.env` files from contaminating isolated unit test runs. |
| [backend/app/services/auth.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/services/auth.py) | Imported `InvalidIssuerError` and added issuer verification check in `jwt.decode` | Enforces that when `SUPABASE_JWT_ISSUER` is set, tokens with mismatched or forged issuers are rejected with `INVALID_ISSUER`. |
| [backend/.env.example](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/.env.example) & [.env.example](file:///c:/Users/aslam/Desktop/ORQESTRA/.env.example) | Added staging URL, `SUPABASE_JWT_ISSUER`, and `SUPABASE_PUBLISHABLE_KEY` placeholders | Establishes standard templates for backend staging configuration. |
| [backend/app/tests/test_jwt_verification.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_jwt_verification.py) | Added issuer validation tests (`test_valid_token_with_matching_issuer`, `test_token_with_mismatched_issuer_rejected`) | Validates server-side issuer verification against forged and matching tokens. |
| [backend/app/tests/test_config.py](file:///c:/Users/aslam/Desktop/ORQESTRA/backend/app/tests/test_config.py) | Added `test_supabase_publishable_key_and_issuer_properties` | Validates settings property derivations for publishable keys, issuers, and JWKS URLs. |
| [frontend/tests/SupabaseConfig.test.ts](file:///c:/Users/aslam/Desktop/ORQESTRA/frontend/tests/SupabaseConfig.test.ts) | Created unit test suite for frontend client configuration | Validates client initialization with publishable key, fallback with anon key, and clean unconfigured state. |

---

## 3. Environment Variables Specification

### 3.1 Frontend (`frontend/.env`)
| Variable | Value / Format | Security Classification | Notes |
|---|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Public | Backend API endpoint URL. |
| `VITE_SUPABASE_URL` | `https://vwlwbwwrumsmjqeavvxk.supabase.co` | Public | Staging Supabase project URL. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | `<user_publishable_key>` | Browser-Safe Public Key | Staging publishable (anon) API key. Safe for browser distribution. |
| `VITE_SUPABASE_ANON_KEY` | *(Optional alias)* | Browser-Safe Public Key | Supported as fallback if used instead of publishable key. |

> [!CAUTION]
> Never place database passwords, `SUPABASE_SERVICE_ROLE_KEY`, or `AI_API_KEY` in `frontend/.env` or any `VITE_` prefixed variable.

### 3.2 Backend (`backend/.env`)
| Variable | Value / Format | Security Classification | Notes |
|---|---|---|---|
| `ENVIRONMENT` | `development` (or `staging`) | Non-Secret | Active environment profile. |
| `SUPABASE_URL` | `https://vwlwbwwrumsmjqeavvxk.supabase.co` | Non-Secret | Staging project base URL. |
| `SUPABASE_SERVICE_ROLE_KEY` | `<user_entered_locally>` | **CONFIDENTIAL SERVER-SIDE SECRET** | Required for server-to-database PostgREST operations. Never expose to client. |
| `SUPABASE_JWT_SECRET` | `<user_entered_locally>` | **CONFIDENTIAL SERVER-SIDE SECRET** | Required only if project uses symmetric HS256 tokens. |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Non-Secret | Expected JWT audience claim. |
| `SUPABASE_JWT_ISSUER` | `https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1` | Non-Secret | Expected JWT issuer claim. |
| `SUPABASE_JWT_ALGORITHM` | `HS256` (or `RS256` for JWKS) | Non-Secret | Default JWT signature algorithm. |

---

## 4. Manual Actions Required by the User

To enable live staging interaction once approved:

1. **Enter Publishable Key in Frontend Environment:**
   Open `frontend/.env` and paste the Supabase publishable/anon key:
   ```env
   VITE_SUPABASE_PUBLISHABLE_KEY=<paste_publishable_key_here>
   ```
2. **Enter Backend Service Role Key (When Backend Staging is Activated):**
   Open `backend/.env` and paste the Supabase `service_role` key:
   ```env
   SUPABASE_SERVICE_ROLE_KEY=<paste_service_role_key_here>
   ```
   *(If your project uses HS256 legacy secrets, also paste `SUPABASE_JWT_SECRET`)*.
3. **Supabase Cloud Dashboard Settings Verification:**
   - **Redirect URLs:** Verify that `http://localhost:5173` and `http://127.0.0.1:5173` are listed under **Authentication -> URL Configuration -> Redirect URLs**.
   - **Email Confirmation:** Review whether email confirmation is required under **Authentication -> Providers -> Email**. In staging, auto-confirm can be enabled if automated testing without an inbox is desired.
   - **JWT Expiry:** Confirm JWT access token expiry is configured as expected (default: 3600 seconds).

---

## 5. Verification & Test Execution Results

All available safe tests were executed with verifiable results:

### 5.1 Backend Unit, Security, and Migration Tests (Pytest)
- **Command:** `backend\.venv\Scripts\python -m pytest backend\app\tests\test_authorization.py backend\app\tests\test_config.py backend\app\tests\test_errors.py backend\app\tests\test_health.py backend\app\tests\test_jwt_verification.py backend\app\tests\test_migrations.py backend\app\tests\test_operations.py backend\app\tests\test_phase5_ai_invoices.py backend\app\tests\test_phase6_hardening.py -v`
- **Result:** **74 Passed, 0 Failed, 1 Deprecation Warning** in 5.35s
  - `test_authorization.py`: 8 passed (multi-tenant boundary, role hierarchy, anti-escalation)
  - `test_config.py`: 4 passed (parsing, publishable key fallback, issuer derivation)
  - `test_errors.py`: 2 passed (structured responses, stack-trace shielding)
  - `test_health.py`: 4 passed (component honesty, OpenAPI accessible)
  - `test_jwt_verification.py`: 15 passed (HS256, RS256 JWKS rotation, algorithm confusion rejection, audience and issuer verification)
  - `test_migrations.py`: 12 passed (static audit of all 6 migrations, composite FKs, RLS, triggers, atomic functions)
  - `test_operations.py`: 8 passed (product lifecycle, stock deduction, atomic approval/cancellation)
  - `test_phase5_ai_invoices.py`: 18 passed (AI message boundaries, prompt injection guard, snapshot immutability, invoice allocation)
  - `test_phase6_hardening.py`: 3 passed (metrics consistency, repeated approval rejection, cross-tenant operational isolation)

### 5.2 Local PostgreSQL Staging Tests
- **Command:** `backend\.venv\Scripts\python -m pytest backend\app\tests\test_postgres_staging.py -v`
- **Result:** **12 Skipped** (as designed when local disposable staging database is inactive).
- **Clean State:** Cleaned up ephemeral temporary connection tokens via `manage_staging_db.py cleanup`.

### 5.3 Frontend Unit and Component Tests (Vitest)
- **Command:** `npm test`
- **Result:** **8 Test Files Passed, 40 Tests Passed, 0 Failed** in 8.55s
  - `tests/SupabaseConfig.test.ts`: 3 passed (publishable key, anon key fallback, unconfigured state)
  - `tests/SignInModal.test.tsx`: 2 passed (operator authentication, unconfigured alert)
  - `tests/Realtime.test.tsx`: 8 passed (lifecycle, channels, table dispatch, deduplication, tenant filtering)
  - `tests/Phase5.test.tsx`: 7 passed (AI operations, invoice generation, streaming PDF download)
  - `tests/FoundationDashboard.test.tsx`: 3 passed (metrics, architecture overview, health status)
  - `tests/Operations.test.tsx`: 7 passed (catalog, inventory, customer, order approval)
  - `tests/Phase6.test.tsx`: 6 passed (dashboard KPI calculation, activity log filtering)
  - `tests/App.test.tsx`: 4 passed (routing, navigation, layout)

### 5.4 Frontend Production Build
- **Command:** `npm run build` (`tsc && vite build`)
- **Result:** **Success (Exit Code 0)**. Output generated to `frontend/dist/` in 3.72s. 113 modules transformed, 0 TypeScript errors.

---

## 6. Features Verified Locally vs. Live Supabase Status

| Feature / Capability | Local Verification Status | Live Supabase Staging Status |
|---|---|---|
| Frontend Client Initialization | Verified (Vitest: 40/40 passed) | Configured with staging URL; awaiting publishable key entry |
| Session Restoration & Sign Out | Verified with mocked GoTrue client | Pending user sign-in test against live Supabase Auth |
| Backend JWT Verification (HS256/RS256) | Verified with PyJWT & cryptography | Ready to verify live tokens signed by Supabase Auth |
| JWT Issuer Enforcement | Verified locally with PyJWT | Ready to enforce `https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1` |
| Business Role Authorization & Tenancy | Verified (74 backend unit tests passed) | Ready; database-backed membership requires remote schema |
| SQL Schema Migrations (1 to 6) | Verified statically (12 migration tests passed) | **NOT APPLIED** (Safety gate engaged; waiting for approval) |
| Supabase Realtime Subscriptions | Verified client logic & tenant filter | **PENDING** (Requires remote table publications to be live) |
| PostgREST Operations | Verified via repository contracts | **PENDING** (Requires remote tables and service_role key) |

---

## 7. Migration-Readiness Assessment & Safety Gate

### 7.1 Readiness Assessment
All six migration files are verified and structurally complete:
1. `20261022000001_core_schema.sql`: Ready. Uses idempotent `DO` blocks for enums and `IF NOT EXISTS` for all 10 tables and triggers.
2. `20261022000002_row_level_security.sql`: Ready. Pinned search paths, non-recursive helper functions, execution grants, anti-escalation policies.
3. `20261023000001_operations_transactions.sql`: Ready. Idempotent `ALTER TYPE ... ADD VALUE IF NOT EXISTS`, atomic operations functions with independent caller auth.
4. `20261023000002_realtime_publications.sql`: Ready. Idempotent check for `supabase_realtime` publication and idempotent `ADD TABLE`.
5. `20261023000003_invoices_and_allocation.sql`: Ready. Adds invoices to Realtime, creates `allocate_invoice_atomic`.
6. `20261023000004_invoice_snapshots_and_constraints.sql`: Ready. Contains pre-migration safety check, partial unique index, and immutable snapshot columns.

### 7.2 Proposed Remote Migration Execution Plan (FOR FUTURE APPROVAL ONLY)
When explicit user approval is granted to apply migrations to the remote Supabase project, the proposed runbook is:

```bash
# Step 1: Login and link project using Supabase CLI
supabase login
supabase link --project-ref vwlwbwwrumsmjqeavvxk

# Step 2: Verify diff between local migrations and remote database
supabase db diff

# Step 3: Apply migrations sequentially to remote project
supabase db push

# Step 4: Verify remote migration status
supabase migration list
```

**What these commands will change:**
- Creates 10 application tables in `public` schema.
- Enables Row Level Security on all 10 tables.
- Creates 5 helper functions, 4 atomic stored procedures (`adjust_stock_atomic`, `approve_order_atomic`, `cancel_order_atomic`, `allocate_invoice_atomic`), and 2 immutability triggers.
- Configures `REPLICA IDENTITY FULL` on operational tables and registers them with `supabase_realtime` publication.

**Verification & Recovery Strategy:**
- *Verification:* Execute read-only introspection queries against `information_schema.tables`, `pg_proc`, and `pg_publication_tables` to confirm all 10 tables, 4 RPCs, and publication memberships exist.
- *Recovery:* In the event of an unrecoverable schema discrepancy, Supabase CLI allows rolling back via migration scripts or restoring from point-in-time database backups available in the Supabase Cloud dashboard.

---

## 8. Missing Configuration & Remaining Steps for Full Staging Readiness

The following items remain before staging is fully operational:

1. **User Publishable Key Entry:** User enters publishable key in `frontend/.env`.
2. **Explicit Approval for Remote Migrations:** User reviews the migration-readiness report and explicitly approves applying the 6 migrations to `vwlwbwwrumsmjqeavvxk.supabase.co`.
3. **Server-Side Credentials:** User configures `SUPABASE_SERVICE_ROLE_KEY` in `backend/.env` once remote schema is provisioned.
4. **Live Auth & Realtime End-to-End Test:** Create an initial test user and business membership to verify end-to-end browser sign-in, JWT exchange, and WebSocket Realtime synchronization against the live Supabase project.

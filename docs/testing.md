# Orqestra Testing Strategy & Verification Guide

## 1. Testing Strategy

Orqestra maintains rigorous automated test suites across both backend and frontend layers to verify runtime behavior, configuration, security token validation, multi-tenant isolation, database migrations, and UI states.

Testing taxonomy & discipline:
- **Unit Tests**: Pure function & local logic tests (configuration parsing, error envelope structures).
- **Mocked Tests**: Subsystem isolation tests using simulated cryptographic tokens and mock dependencies (JWT verification, mock JWKS rotation, in-memory RBAC repository).
- **Static SQL Checks**: Migration AST and structural checks validating composite foreign keys, RLS policies, trigger registrations, and function privileges.
- **Real Database Integration Tests**: Tests executing against a live PostgreSQL / Supabase instance.
  - *Current Status*: Because no local PostgreSQL daemon or remote Supabase credentials are configured on this machine, live RLS integration tests remain **unverified** and must be performed when connecting to the target Supabase project.

---

## 2. Backend Automated Tests (pytest)

### 2.1 Test Suite Organization
Located in `backend/app/tests/`:

- `test_config.py` (Unit Tests):
  - `test_default_settings`: Fallback configuration values.
  - `test_cors_origins_string_parsing`: Comma-separated string parsing.
  - `test_cors_origins_list_parsing`: Origin list sanitization.
- `test_errors.py` (Unit Tests):
  - `test_404_not_found_structure`: Standard error envelope on invalid routes.
  - `test_no_stack_trace_leakage`: Confirms traceback and server file path disclosures are prevented.
- `test_health.py` (Unit / Route Tests):
  - `test_root_health_endpoint`: Probes `GET /health` verifying 200 response, UTC timestamp, uptime, and component diagnostics.
  - `test_api_v1_health_endpoint`: Probes `GET /api/v1/health` verifying versioned route parity.
  - `test_openapi_documentation_accessible`: Ensures OpenAPI schema is served at `/openapi.json`.
  - `test_cors_headers`: Confirms CORS preflight OPTIONS requests return valid access-control headers.
- `test_jwt_verification.py` (Mocked Cryptographic & Auth Tests):
  - `test_valid_token_verification`: Valid token signature decodes subject and claims.
  - `test_expired_token_rejected`: Expired JWT is rejected with `TOKEN_EXPIRED`.
  - `test_invalid_signature_rejected`: Tampered signature is rejected with `INVALID_SIGNATURE`.
  - `test_algorithm_confusion_attack_rejected`: Rejection of `none` or mismatched algorithm headers.
  - `test_audience_mismatch_rejected`: Mismatched audience claim rejection.
  - `test_missing_subject_rejected`: Token missing `sub` claim is rejected with `MISSING_SUBJECT`.
  - `test_blank_subject_rejected`: Token with whitespace-only `sub` claim is rejected.
  - `test_malformed_token_rejected`: Malformed / corrupted token string rejected with `INVALID_TOKEN`.
  - `test_empty_token_rejected`: Empty string bearer token rejected with `UNAUTHENTICATED`.
  - `test_unconfigured_auth_rejected`: Rejection with `AUTH_UNCONFIGURED` if server secrets/JWKS are unset.
  - `test_asymmetric_token_with_jwks_rotation`: Asymmetric RS256 token verification using mock JWKS key lookup.
  - `test_asymmetric_token_with_unknown_kid_rejected`: Rejection with `INVALID_KEY_ID` when kid is unknown.
  - `test_auth_me_endpoint_requires_token`: `GET /api/v1/auth/me` returns 401 without token.
- `test_authorization.py` (Mocked Multi-Tenancy & Authorization Tests):
  - `test_auth_me_returns_profile_and_memberships`: Returns user profile and confirmed business memberships.
  - `test_cross_business_access_denied`: User from Business Beta attempting to access Business Alpha is rejected with HTTP 403.
  - `test_forged_random_business_id_denied`: User attempting to access arbitrary non-member UUID is rejected with HTTP 403.
  - `test_inactive_membership_denied`: Deactivated membership rejected with HTTP 403.
  - `test_authorized_business_access`: Verified member can access their own business context.
  - `test_role_enforcement_admin_endpoint`: Staff user is rejected on admin endpoint (403); Admin and Owner are permitted (200).
  - `test_missing_business_id_header`: Missing `X-Business-ID` header on business endpoint returns HTTP 400.
  - `test_production_environment_blocks_in_memory_repository`: Proves `ENVIRONMENT="production"` strictly forbids `InMemoryBusinessRepository` and all other in-memory repositories across all 6 dependencies (`get_business_repository`, `get_audit_repository`, `get_product_repository`, `get_inventory_repository`, `get_customer_repository`, `get_order_repository`), enforcing real database repository configuration.
- `test_migrations.py` (Static SQL Analysis & Hardening Checks):
  - `test_migrations_directory_and_files_exist`: Verifies ordered migration files exist in `supabase/migrations/`.
  - `test_core_schema_declares_all_ten_tables`: Verifies all 10 core tables are created with UUIDs, numeric currency, and check constraints.
  - `test_composite_foreign_keys_prevent_cross_business_references`: Verifies composite FKs on child tables prevent cross-tenant referencing.
  - `test_row_level_security_enabled_on_all_tables`: Verifies RLS is enabled on all tables and security definer functions exist.
  - `test_security_definer_execution_permissions_restricted`: Verifies `REVOKE EXECUTE FROM PUBLIC` on all security definer functions and search path pinning.
  - `test_anti_privilege_escalation_enforced_in_policies`: Verifies admins can only invite `staff`, and cannot assign `admin` or `owner` roles.
  - `test_ledger_immutability_enforced_by_triggers_and_omitted_policies`: Verifies immutability triggers and omission of UPDATE/DELETE policies on `stock_movements` and `audit_logs`.
  - `test_phase3_migration_operations_and_atomic_functions`: Validates `20261023000001_operations_transactions.sql`, verifying the addition of `'rejected'` to `order_status` enum, `is_active` to `customers`, performance composite indexes, and atomic PostgreSQL functions (`adjust_stock_atomic`, `approve_order_atomic`, `cancel_order_atomic`) with `SECURITY DEFINER` and search path pinning.
  - `test_phase3_atomic_functions_independent_authorization_and_actor_verification`: Verifies that `adjust_stock_atomic`, `approve_order_atomic`, and `cancel_order_atomic` independently verify authenticated callers, forbid impersonation (`p_user_id != v_auth_uid`), enforce `has_business_role(..., 'admin')`, validate inputs, and attribute audit logs to the verified actor.
  - `test_phase4_realtime_publications_and_replica_identity`: Verifies that `20261023000002_realtime_publications.sql` creates/verifies the `supabase_realtime` publication, sets `REPLICA IDENTITY FULL` on all four operational tables (`products`, `inventory`, `orders`, `stock_movements`), and adds them idempotently to the publication.
  - `test_phase5_invoice_allocation_atomic_and_publication`: Verifies `20261023000003_invoices_and_allocation.sql`, confirming `invoices` table replica identity, registration in `supabase_realtime`, and the creation of `allocate_invoice_atomic` with `SECURITY DEFINER`, pinned search path, and revoked PUBLIC execution.
  - `test_phase5_1_invoice_snapshots_and_order_uniqueness`: Verifies `20261023000004_invoice_snapshots_and_constraints.sql`, confirming `uq_invoices_business_order_unique` partial unique index, `line_items_snapshot` and `customer_snapshot` columns, hardened tenant-first row locking, and execution restrictions.
- `test_phase5_ai_invoices.py` (Phase 5 & 5.1 AI Intake, Catalog Matching & Invoices):
  - `test_ai_intake_unconfigured_credentials_rejected`: Verifies HTTP 503 error with `code="AI_NOT_CONFIGURED"` when `AI_API_KEY` is unset.
  - `test_ai_intake_unsupported_provider_rejected`: Verifies that unsupported `AI_PROVIDER` values (e.g. anthropic, claude) return HTTP 503 with an explicit configuration error.
  - `test_ai_intake_message_length_boundaries`: Verifies rejection of messages shorter than 5 chars or longer than 4000 chars.
  - `test_ai_intake_valid_structured_extraction_and_catalog_match`: Verifies candidate extraction against active catalog with authoritative database unit prices and exact Decimal arithmetic (with zero invented tax).
  - `test_ai_intake_ambiguous_and_unmatched_products`: Verifies ambiguous products are flagged for operator resolution and unmatched items block draft order creation.
  - `test_ai_intake_malformed_model_output_handled_safely`: Verifies safe handling of non-JSON model output without crashing.
  - `test_ai_intake_prompt_injection_safety`: Verifies system instruction boundaries isolate prompt injection payloads.
  - `test_ai_intake_provider_timeout_handled`: Verifies provider timeouts raise clean `AIExtractionError`.
  - `test_order_creation_from_ai_proposal_does_not_deduct_stock`: Verifies creating a draft order from an AI proposal does NOT deduct stock; stock remains unchanged until atomic approval.
  - `test_invoice_allocation_atomic_and_idempotent`: Verifies sequential number generation (`INV-YYYYMM-XXXX`) and idempotent returns for repeated calls on the same order.
  - `test_invoice_allocation_rejected_for_unapproved_order`: Verifies invoices cannot be issued for draft or pending review orders.
  - `test_invoice_cross_business_isolation`: Verifies cross-tenant isolation on invoice retrieval and allocation.
  - `test_invoice_pdf_generation_content_and_headers`: Verifies ReportLab streaming binary PDF generation, safe attachment headers, and exact Decimal sums.
  - `test_concurrent_invoice_allocation_unique_numbering`: Verifies unique sequential numbering without collisions.
  - `test_invoice_historical_snapshot_preserves_pdf_accuracy`: Verifies `line_items_snapshot` and `customer_snapshot` insulate invoice PDFs from downstream mutations to underlying order or product records.
  - `test_invoice_month_boundary_numbering`: Verifies month transitions reset invoice numbering sequence back to 0001 for each month prefix.
  - `test_invoice_missing_customer_details_safe_fallback`: Verifies invoices without phone or address render cleanly without fabricating unverified data.
  - `test_invoice_concurrent_allocation_idempotency_and_uniqueness`: Verifies simultaneous concurrent allocations for the same order return identical invoice records with zero duplicates.
- `test_operations.py` (Phase 3 Core Business Operations & Transaction Tests):
  - `test_product_lifecycle`: Catalog item creation, search query filtering, detail retrieval, updates, and soft deactivation.
  - `test_inventory_and_stock_adjustments`: Inventory listing, low-stock alerts, manual stock adjustments requiring audit reason, and movement ledger generation.
  - `test_customer_lifecycle`: Customer directory creation, search filtering, profile updates, and soft deactivation.
  - `test_order_creation_exact_decimal_totals`: Server-side exact decimal pricing, tax, and total calculations discarding client assertions.
  - `test_order_approval_deducts_stock_atomically`: Transition from `draft` to `pending_approval` to `approved`, verifying atomic stock reservation and ledger entry creation.
  - `test_insufficient_stock_prevents_order_approval_and_rolls_back`: Insufficient warehouse stock aborts approval with HTTP 409, ensuring zero partial deductions and rolling back all changes.
  - `test_cross_business_product_in_order_rejected`: Cross-tenant product injection attempts are rejected with HTTP 400.
  - `test_order_cancellation_restores_approved_stock`: Cancelling an approved order atomically restores deducted stock and logs `return` movements.

### 2.2 Execution Commands (Windows PowerShell)

From workspace root:
```powershell
backend\.venv\Scripts\python -m pytest backend/app/tests/ -v
```

Verification status: **62 passed, 0 failed in 4.47s across 8 test suites (100% pass rate).**

---

## 3. Frontend Automated Tests (Vitest & Testing Library)

### 3.1 Test Suite Organization
Located in `frontend/tests/`:

- `tests/Phase5.test.tsx` (Phase 5 AI Intake & Invoices Tests):
  - `AIOpsPage`: Message length validation, unconfigured AI provider error with manual fallback link, structured extraction with candidate items, authoritative database prices, exact Decimal sums, catalog resolution for ambiguous/unmatched items, and draft order creation without stock deduction.
  - `InvoicesPage`: Lists allocated invoices, status badge rendering, and PDF streaming download via Blob trigger.
  - `OrdersPage`: Invoice allocation and PDF download button on approved orders.
- `tests/Realtime.test.tsx` (Phase 4 Realtime Lifecycle & Security Tests):
  - Verifies that no subscription or websocket channel is created before user authentication or in the absence of an active business context.
  - Verifies that upon authentication with an active business, the session token is applied via `supabase.realtime.setAuth(token)`, channel is scoped to `realtime:business:${businessId}`, and table subscriptions use `business_id=eq.${businessId}`.
  - Verifies that on `SUBSCRIBED`, status transitions to `connected`.
  - Verifies that on sign-out or unmount, the active channel is removed (`supabase.removeChannel`).
  - Verifies that when switching active businesses, the previous channel is torn down and a new channel is established for the target business.
  - Verifies strict tenant isolation: events carrying a foreign `business_id` are dropped by the dispatcher and never delivered to listeners.
  - Verifies event deduplication: repeated events with identical commit timestamp, table, and ID are ignored.
  - Verifies error states (`CHANNEL_ERROR`, `TIMED_OUT`) and recovery via `reconnect()`, notifying listeners to reconcile stale data.
  - Verifies `RealtimeStatusBadge` UI rendering across connection states and retry interaction.
- `tests/App.test.tsx`:
  - Verifies header branding, title, and Phase status indicator.
  - Verifies system navigation with all Phase 5 modules enabled (`Products Catalog`, `Inventory Management`, `Customer Directory`, `Order Processing`, `Invoices & Billing`, `AI Order Extraction`).
  - Verifies switching navigation tabs to render operation pages with authentication boundary feedback.
  - Verifies opening and closing the operator authentication modal.
- `tests/Operations.test.tsx` (Phase 3 Operations & Form Tests):
  - `ProductsPage`: Tests catalog listing, empty state, modal open, form input validation, and submission.
  - `InventoryPage`: Tests stock on hand, low-stock threshold badges, and manual adjustment modal requiring mandatory audit reason.
  - `CustomersPage`: Tests customer directory listing, contact information rendering, and customer creation modal.
  - `OrdersPage`: Tests order listing, status badges (`Review Required`), formatted monetary prices, and order detail management.
- `tests/FoundationDashboard.test.tsx`:
  - Verifies live runtime diagnostics and component status table rendering.
  - Verifies error state presentation and retry button interaction.
  - Verifies manual diagnostic refresh trigger.
- `tests/SignInModal.test.tsx`:
  - Verifies form input rendering, email/password labels, and empty submission validation.
  - Verifies modal visibility toggles correctly based on `isOpen`.

### 3.2 Execution Commands (Windows PowerShell)

From `frontend/` directory:
```powershell
npm test
```

Verification status: **31 passed, 0 failed in 7.62s across 6 test files (100% pass rate).**

---

## 4. Frontend Type Checking & Production Build

### 4.1 TypeScript & Build Verification
```powershell
npm run build
```
Executes `tsc && vite build`, confirming zero type errors, strict unused variable checks, and clean bundle emission.
Verification status: **Built in 4.07s (dist/assets/index-*.js, dist/assets/index-*.css).**

---

## 5. Unverified Integration Requirements

As required by Orqestra security discipline:
1. **Live OpenAI API Communication**: The AI extraction service uses mock/stubbed LLM provider responses in automated tests. Live inference against OpenAI (`https://api.openai.com/v1/chat/completions`) remains **unverified** until an active `AI_API_KEY` is provided in `backend/.env`.
2. **Live Supabase PostgreSQL RLS Execution**: While static SQL checks verify table structures, triggers, composite foreign keys, and RLS policies in migrations, live multi-tenant concurrency and RLS tests against a real remote Supabase instance remain **unverified** until live credentials and network access to the target Supabase project are configured.
3. **Real PostgREST Operations**: The application contains both test-isolated in-memory repositories and production `Supabase...Repository` classes. In production mode (`ENVIRONMENT="production"`), dependencies enforce real database repositories and reject in-memory instances with a fatal `RuntimeError`. Live PostgREST queries cannot be tested without valid Supabase URL and service role keys.
4. **Live Supabase Realtime WebSocket Connection**: Frontend Realtime lifecycle tests use mock client abstractions to verify channel creation, token passing, tenant isolation, and deduplication. Live WebSocket communication against Supabase's hosted Realtime servers remains **unverified** until the project is deployed to a live Supabase environment with `supabase_realtime` publication active.

---

## 6. Applying Migrations to Supabase

### 6.1 Using the Supabase CLI
If using the local Supabase development environment:
```powershell
supabase db reset
# or
supabase migration up
```

### 6.2 Using the Supabase Dashboard SQL Editor
1. Navigate to your Supabase project dashboard: `https://supabase.com/dashboard/project/<your-project-ref>`.
2. Open the **SQL Editor**.
3. Execute `supabase/migrations/20261022000001_core_schema.sql` to establish tables, composite unique keys, composite foreign keys, and triggers.
4. Execute `supabase/migrations/20261022000002_row_level_security.sql` to establish security definer functions, execution restrictions, immutability triggers, and RLS policies.
5. Execute `supabase/migrations/20261023000001_operations_transactions.sql` to add `rejected` order status, customer active state, performance indexes, and atomic stock RPC functions.
6. Execute `supabase/migrations/20261023000002_realtime_publications.sql` to create `supabase_realtime` publication and configure `REPLICA IDENTITY FULL` on operational tables.
7. Execute `supabase/migrations/20261023000003_invoices_and_allocation.sql` to configure `invoices` replica identity and publication, and deploy the atomic sequential invoice allocation RPC function.

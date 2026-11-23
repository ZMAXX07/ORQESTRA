# Orqestra Security Architecture & Controls

## 1. Security Architecture Principles

Security is built into Orqestra from the foundation:
- Defense in depth across network, application, and database tiers.
- Zero trust for client assertions: client-supplied business IDs or user roles are never accepted without server-side verification.
- Principle of least privilege for roles, service keys, and database operations.
- Deterministic backend enforcement over non-deterministic AI outputs.

---

## 2. Implemented Security Controls

### 2.1 Supabase JWT Token Verification (Phase 2 & 2.1 Hardened)
- **Signature Verification**: Validates Supabase JWT access tokens server-side in FastAPI using PyJWT.
- **Asymmetric JWKS Key Rotation Support**: Supports both legacy symmetric HMAC secrets (`HS256`) and modern asymmetric Supabase key rotation (`RS256`, `ES256`) via `jwt.PyJWKClient` fetching public keys by `kid` from `.well-known/jwks.json`.
- **Algorithm Confusion Mitigation**: Inspects unverified headers before decoding to ensure the algorithm strictly matches expected symmetric or asymmetric signing configurations. Tokens using `none` or unexpected algorithms are rejected.
- **Required Claims Enforcement**: Requires valid expiration (`exp`), audience (`aud` == `authenticated`), and subject UUID (`sub`).
- **Standardized Rejection Codes**: Returns HTTP 401 with specific, safe error codes (`UNAUTHENTICATED`, `TOKEN_EXPIRED`, `INVALID_SIGNATURE`, `INVALID_AUDIENCE`, `INVALID_ALGORITHM`, `MISSING_SUBJECT`, `INVALID_KEY_ID`).
- **Token Redaction**: Bearer tokens and credentials are never written to log files.

### 2.2 Database Multi-Tenancy & Row Level Security (Phase 2 & 2.1 Hardened)
- **Mandatory Tenancy Scoping**: All business-owned tables include an immutable `business_id UUID NOT NULL REFERENCES businesses(id)`.
- **Row Level Security (RLS)**: Enabled across all 10 core tables (`businesses`, `business_members`, `products`, `inventory`, `customers`, `orders`, `order_items`, `invoices`, `stock_movements`, `audit_logs`).
- **Non-Recursive Membership Evaluation**: Permission checks rely on `SECURITY DEFINER` functions (`has_business_role`, `get_business_member_role`) with pinned `search_path = public`.
- **Execution Privilege Lockdown**: Execution on all SECURITY DEFINER functions (`get_auth_user_id`, `has_business_role`, `get_business_member_role`, `handle_new_business`, `prevent_immutable_modification`) is explicitly revoked from `PUBLIC` and granted only to `authenticated` and `service_role`.
- **Cross-Tenant Foreign Key Immunity**: Composite unique constraints (`uq_products_business_id`, `uq_orders_business_id`, `uq_customers_business_id`) and composite foreign keys on child tables (`order_items`, `inventory`, `invoices`, `stock_movements`) prevent cross-tenant record linking at the PostgreSQL relational engine level.
- **Anti-Privilege Escalation**: `business_members` RLS policy restricts `admin` users to inviting only `staff`. Assigning `admin` or `owner` roles strictly requires an existing `owner`.
- **Owner Auto-Enrollment**: Database trigger `trg_on_business_created` automatically enrolls the authenticated creator as `owner` in `business_members`.

### 2.3 Role-Based Access Control (RBAC) (Phase 2 & 2.1 Hardened)
- **Role Hierarchy**: Enforces a strict 3-tier hierarchy (`owner` > `admin` > `staff`).
  - Owner: Complete administrative access, member management, business deletion.
  - Admin: Operational management, catalog and order approvals, staff invitations.
  - Staff: Daily operational entries; prohibited from approving consequential transactions or modifying member roles.
- **Production Repository Safeguard**: In `backend/app/api/deps.py`, selecting or running `InMemoryBusinessRepository` in a production environment (`ENVIRONMENT="production"`) raises a fatal `RuntimeError`, guaranteeing that test implementations cannot be accidentally used in live deployments.
- **Database-Backed Repository**: `SupabaseBusinessRepository` queries the live Supabase PostgREST endpoint using server-side service credentials.

### 2.4 Immutable Audit & Movement Ledgers (Phase 2 & 2.1 Hardened)
- **Engine-Level Trigger Enforcement**: `stock_movements` and `audit_logs` are protected by `BEFORE UPDATE OR DELETE` triggers (`trg_stock_movements_immutable`, `trg_audit_logs_immutable`) invoking `prevent_immutable_modification()`, raising a fatal PostgreSQL exception on any alteration attempt.
- **RLS Policy Omission**: No `UPDATE` or `DELETE` policies exist on `stock_movements` or `audit_logs`.

### 2.5 Secret & Credential Isolation (Phase 1 & 2)
- **Zero Secrets in Code or Bundles**: No private keys, database passwords, or service-role keys exist in source control or frontend browser bundles.
- **Environment Separation**: Public keys (`VITE_SUPABASE_ANON_KEY`) are permitted in the frontend; private service keys (`SUPABASE_SERVICE_ROLE_KEY`) are strictly confined to backend environments.
- **Git Exclusions**: Root `.gitignore` prevents tracking `.env`, `*.local`, virtual environments, and node modules.

---

### 2.6 Transaction Concurrency & Stock Integrity Controls (Phase 3)
- **Database-Level Row Locking**: Consequential operations execute inside PostgreSQL functions (`adjust_stock_atomic`, `approve_order_atomic`, `cancel_order_atomic`) utilizing `SELECT ... FOR UPDATE` row locks to serialize concurrent attempts on identical stock.
- **Race Condition Immunity**: Two concurrent order approvals cannot oversell stock. Stock verification and deduction cannot be separated by an interleaving transaction.
- **Atomic Rollback Guarantee**: If any single line item in an order lacks sufficient stock, the database transaction is aborted, raising an exception and rolling back all pending updates. No partial stock deductions or orphaned ledger entries can occur.
- **Double-Deduction Prevention**: State transitions strictly check that the order status is `pending_approval`. Repeated approval requests on an already-approved order fail immediately without deducting stock a second time.
- **Cross-Tenant Product Injection Mitigation**: Every line item is verified to ensure its `product_id` belongs to the requesting business. Mismatched or cross-business product IDs fail immediately.
- **Exact Decimal Arithmetic**: All financial amounts (`unit_price`, `subtotal`, `tax`, `total_amount`) use exact decimal arithmetic (`NUMERIC(12, 2)` in PostgreSQL, `Decimal` in Python with `.quantize(Decimal("0.01"))`). Floating-point arithmetic is strictly forbidden.
- **Client Assertion Discarding**: Client-supplied prices, totals, stock values, roles, or business IDs are never trusted. Product prices are looked up directly from verified database catalog items.
- **Mandatory Adjustment Auditing**: Manual stock adjustments require a non-empty audit reason (minimum 3 characters) and are permanently recorded in both `stock_movements` and `audit_logs`.

### 2.7 Atomic RPC Security Definer Independent Authorization (Phase 3 Security Gate Hardened)
- **Zero-Trust Caller Resolution**: Direct RPC invocations via Supabase PostgREST bypass FastAPI middleware. All `SECURITY DEFINER` atomic functions (`adjust_stock_atomic`, `approve_order_atomic`, `cancel_order_atomic`) independently authenticate the database caller:
  - Resolves execution role via `current_setting('request.jwt.claim.role', true)` and `auth.role()`.
  - Rejects unauthorized roles (`anon` or untrusted roles) with SQLSTATE `42501`.
  - For `authenticated` callers: extracts `auth.uid()` via `public.get_auth_user_id()`. If missing or empty, raises `42501`.
  - Prevents caller/actor spoofing: rejects any attempt where caller-provided `p_user_id` does not match the verified `v_auth_uid` (`Actor mismatch: caller cannot impersonate another user`).
  - For `service_role` callers: requires `p_user_id` to be explicitly provided.
  - Enforces role authorization at database level: verifies `public.has_business_role(p_business_id, v_actor_id, 'admin')` before any row locks or mutations occur. Callers without active `admin` or `owner` roles are rejected with SQLSTATE `42501`.
- **Function Execution Grants**: Execution privileges on atomic functions are explicitly revoked from `PUBLIC` and restricted solely to `authenticated` and `service_role`.
- **Search Path Pinning**: All atomic functions specify `SET search_path = public, pg_temp` to prevent search_path hijacking in `SECURITY DEFINER` mode.
- **Defensive Input Validation**: Enforces parameter sanity checks: non-null UUIDs, `p_delta != 0`, `length(trim(p_reason)) >= 3`, orders must contain at least one line item (`v_item_count > 0`), and products/orders must match `p_business_id`.
- **Tamper-Proof Audit Attribution**: Movement ledgers (`stock_movements.created_by`) and audit records (`audit_logs.user_id`, `orders.approved_by`) are assigned strictly to the verified `v_actor_id`, preventing attribution tampering.
- **Production Repository Isolation**: All 6 repository dependency providers (`get_business_repository`, `get_audit_repository`, `get_product_repository`, `get_inventory_repository`, `get_customer_repository`, `get_order_repository`) in `backend/app/api/deps.py` verify that in `ENVIRONMENT="production"`, in-memory implementations are forbidden and database credentials are required, raising a fatal `RuntimeError` if violated.

### 2.8 Secure Realtime Business Updates & Tenant Boundary Controls (Phase 4)
- **Zero-Trust Client Identity & Realtime WebSockets**:
  - Subscriptions are initiated strictly after session authentication and server-verified active business membership (`serverAuth.active_business.business_id`).
  - Client-supplied business IDs are never accepted as proof of membership; they must be verified via the server `/api/v1/auth/me` endpoint before subscription.
  - The current session JWT bearer token is synchronized to the Realtime socket connection via `supabase.realtime.setAuth(token)`.
- **Database RLS Enforcement on WAL Broadcasts**:
  - Operational tables (`products`, `inventory`, `orders`, `stock_movements`) are registered with `supabase_realtime` in migration `20261023000002_realtime_publications.sql`.
  - `REPLICA IDENTITY FULL` is applied to all subscribed tables, ensuring WAL events include `business_id` on `UPDATE` and `DELETE` actions so PostgreSQL RLS policies can evaluate caller tenancy.
  - Supabase Realtime evaluates the table's `SELECT` RLS policy (`public.has_business_role(business_id, auth.uid(), 'staff')`), ensuring unprivileged or foreign users receive zero events.
- **Channel Scoping & Tenant Payload Verification**:
  - Channels are scoped deterministically to `realtime:business:${businessId}`.
  - Table subscriptions specify `filter: business_id=eq.${businessId}`.
  - Incoming payloads are verified against the active business ID, immediately discarding any mismatched or cross-tenant event.
- **Deterministic Teardown on Context Switch or Sign-Out**:
  - Unmounting, user sign-out, or switching active businesses immediately invokes `supabase.removeChannel(channel)`, flushes event deduplication caches, and resets connection status to `disconnected`.
  - Prevents events from a previous business from appearing after a business switch.
- **Service Role Key Isolation**:
  - The frontend operates strictly with the public `VITE_SUPABASE_ANON_KEY`. The `SUPABASE_SERVICE_ROLE_KEY` is never referenced or bundled in frontend code.
- **Non-Authoritative Realtime Semantics**:
  - Realtime events are strictly non-authoritative signals for UI refresh. No business operations (approvals, cancellations, adjustments) can be initiated or authorized by Realtime payloads.
  - All consequential actions must continue through authenticated FastAPI endpoints and atomic database stored procedures.
- **Zero Token & Secret Logging**:
  - Bearer tokens, secrets, and customer PII are strictly excluded from console logs and Realtime event trace logs.

---

## 3. Phase 5 Security Controls (Implemented)

### 3.1 AI Safety, Prompt Injection Defense & Untrusted Ingress
- **Untrusted Message Ingress**: Customer order messages from external sources (WhatsApp, email, paste) are treated as untrusted input. Messages are bounded between 5 and 4000 characters to prevent denial-of-service or token exhaustion attacks.
- **Prompt Injection Defense**: Customer messages are isolated within delimited instruction tags (`CUSTOMER MESSAGE START` / `CUSTOMER MESSAGE END`). Prompts enforce that user messages can never override system instructions, execute code/SQL, request secrets, or bypass validation.
- **Strict JSON Schema Enforcement**: Models are constrained with `response_format={"type": "json_object"}`. Responses are validated against the strict Pydantic model `AIOrderExtractionOutput`. Malformed, truncated, or non-JSON responses are rejected safely via `AIExtractionError`.
- **Zero Tool Execution / Zero Autonomous Actions**: The AI provider has no tools, functions, SQL access, or network capabilities. The model cannot create, approve, cancel, or modify orders directly.

### 3.2 Non-Authoritative Extraction & Human Confirmation Gate
- **Proposal Semantics**: AI output is strictly a proposed draft. It never mutates persisted orders or stock balances.
- **Deterministic Catalog Resolution**: Product candidates are matched against the authenticated business's real catalog. Ambiguous or unmatched items are explicitly flagged and require human operator resolution.
- **Authoritative Database Pricing**: Prices and inventory quantities are retrieved exclusively from the active business product catalog in PostgreSQL, never from the model output. Client-supplied totals are rejected.
- **Stock Deduction Independence**: Confirming an AI proposal creates a draft order only. Draft order creation does NOT reserve or decrement inventory stock. Stock deduction is strictly confined to the atomic approval workflow (`POST /api/v1/orders/{order_id}/approve`).
- **Server-Side Credential Isolation**: `AI_API_KEY` is loaded from server environment variables only and is never exposed in client bundles. If credentials are missing, the endpoint returns HTTP 503 with an explicit error code (`AI_NOT_CONFIGURED`) and does not simulate or fabricate AI results.

### 3.3 Transaction-Safe Invoice Allocation & Authorization (Hardened in Phase 5.1)
- **Caller Anti-Spoofing & Role Enforcement**: `allocate_invoice_atomic` independently verifies that `p_user_id = auth.uid()` and `public.has_business_role(p_business_id, auth.uid(), 'admin')`. Direct RPC invocations cannot forge actor IDs or business affiliations.
- **Order State Verification**: Invoices can only be allocated for orders in `approved` or `fulfilled` status. Draft, pending review, and cancelled orders are rejected.
- **Deterministic Lock Ordering**: Locks `public.businesses` row FIRST with `FOR UPDATE`, followed by `public.orders` row lock, serializing invoice generation per tenant and completely eliminating cross-order deadlocks.
- **Order Uniqueness Constraint**: Database unique index `uq_invoices_business_order_unique` enforces that an order can have at most one invoice per business, preventing race condition duplication.
- **Historical Snapshot Immutability**: Persists immutable JSONB snapshots (`line_items_snapshot` and `customer_snapshot`) at allocation time. PDF rendering prioritizes these snapshots over live mutable tables, guaranteeing that historical invoices never drift if product prices, names, or customer addresses are updated later.
- **Idempotency Guarantee**: If an order already has an allocated invoice, repeated allocation requests safely return the existing invoice record without incrementing sequence numbers.
- **Immutable Audit Logging**: Records an immutable audit log entry (`invoice.issued`) attributing the allocation to the verified caller.

### 3.4 PDF Document Generation & Download Protection
- **Authoritative Snapshot Source**: PDF invoices are generated strictly from persisted immutable snapshots (falling back to authoritative order records for legacy rows). Arbitrary client-supplied HTML/JSON invoice data is rejected.
- **Exact Decimal Arithmetic & Truthful Tax**: Subtotals, tax, and totals are computed using Decimal precision. Tax is never invented or silently recalculated at an unsupported rate (candidate preview and orders agree at 0.00 tax).
- **No Fabricated Business Details**: If business address, tax number, or customer details are missing, verified fallback text is displayed. No mock tax registration numbers or legal details are invented.
- **Zero Disk Exposure / Zero Public Storage**: PDFs are rendered entirely in memory (`io.BytesIO`) using ReportLab and streamed directly over HTTP. Sensitive invoice documents are never written to the local server disk or public object storage buckets.
- **Safe Response Headers**: Responses are served with:
  - `Content-Type: application/pdf`
  - `Content-Disposition: attachment; filename="invoice-{invoice_number}.pdf"`
  - `Cache-Control: no-cache, no-store, must-revalidate`
  - `X-Content-Type-Options: nosniff`

### 3.5 AI Intake Operational Safeguards & Abuse Protection
- **Provider Restrictions**: `AI_PROVIDER` configuration is strictly validated; only `"openai"` and `"openai-compatible"` endpoints are accepted. Unsupported provider configurations are rejected with HTTP 503 (`AI_NOT_CONFIGURED`).
- **Socket-Level Timeout Enforcement**: `AI_REQUEST_TIMEOUT_SECONDS` (15.0s default) is enforced at the network socket layer using `httpx.AsyncClient(timeout=...)`.
- **Abuse Limitation & Verification Gap**: While input length is strictly bounded (5 to 4000 chars), in-process rate limiting (e.g. token bucket/Redis) is currently not implemented in application code; production deployment MUST enforce rate limits at the API Gateway or reverse proxy level (e.g., Cloudflare / Envoy / Nginx) to protect against credit exhaustion.

---

## 4. Strict Boundaries & Deferred Capabilities (Phase 6+)

The following controls and integrations are deferred:
- Payment processor webhook signature verification (Stripe, Square).
- WhatsApp webhook HMAC validation.
- External accounting system token management (OAuth 2.0 PKCE).
- Autonomous order fulfillment (operator approval remains mandatory).


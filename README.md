# Orqestra

> AI-assisted business operations platform for small businesses.

---

## 1. Product Overview & Current Phase

**Current Phase**: Phase 6: Operational Dashboard, Workflow Completion, and Quality Hardening.

Orqestra helps small businesses coordinate essential operations including product and inventory tracking, customer directory management, order review and approval workflows, transaction-safe inventory fulfillment, stock movement ledgers, auditable operations, secure business-scoped Realtime synchronization, AI-assisted order intake, sequential invoice allocation, verifiable PDF generation, and an authoritative operational dashboard.

### Core Philosophy: AI as Assistant, Not Final Authority
- Backend business rules deterministically validate products, prices, quantities, stock, permissions, and financial calculations using exact decimal arithmetic (`NUMERIC(12, 2)`).
- AI never directly modifies inventory or approves consequential business transactions without human oversight.
- Realtime events never authorize business actions or substitute for database transactions; they trigger safe UI reconciliations against authoritative backend endpoints.
- Operational dashboards query authoritative API endpoints exclusively with zero fabricated metrics, fake customer counts, or simulated activity.

---

## 2. Current Scope & Implemented Workflows (Phases 1 through 6)

### 2.1 Operational Dashboard (Phase 6)
- **Authoritative Metrics**: Real-time inventory tracking, low-stock count, order pipeline counts, and registered product counts sourced exclusively from active backend endpoints.
- **Urgent Action Alerts**:
  - Low-Stock Table: Lists products at or below their reorder threshold with direct "Adjust Stock" actions.
  - Pending Approval Table: Lists unreviewed orders requiring operator review with direct "Review Order" actions.
  - Optimal Alert: Displays confirmation when all inventory is healthy and no orders await review.
- **Live Activity Feeds**:
  - Recent Orders table with order reference, customer, exact total, status badges, and date.
  - Recent Stock Movements table displaying signed quantity changes (`+`/`-`), movement types, audit reasons, and timestamps.
- **Quick Actions Strip**: One-click navigation to Orders, Inventory, Products, AI Intake, Invoices, and Customers.
- **Runtime Health & Diagnostics**: Live uptime, API status, ISO UTC timestamp probe, and 5 subsystem diagnostics.

### 2.2 Reusable Pagination & Mutation Safety (Phase 6)
- **Accessible Pagination Component**: Integrated across `ProductsPage`, `InventoryPage`, `CustomersPage`, `OrdersPage`, and `InvoicesPage` with accessible focus indicators, page boundaries, and disabled states.
- **In-Flight Mutation Protection**: Order lifecycle actions (`submitOrder`, `approveOrder`, `rejectOrder`, `cancelOrder`) utilize an `isActionPending` guard, preventing duplicate submissions, showing clear pending states (`Approving...`, `Cancelling...`), and disabling buttons while mutations execute.
- **Snapshot Inspection**: `InvoicesPage` includes an inspection modal allowing operators to view immutable customer snapshot records and line item snapshots persisted at allocation time.

### 2.3 AI-Assisted Order Intake (Phase 5)
- **Input Boundaries & Defense**: Validated raw message intake (5 to 4000 characters), prompt injection defense, timeout protection, and unconfigured provider graceful fallbacks.
- **Deterministic Catalog Matching**: Sourced against active business catalog products with candidate match confidence scoring (`matched`, `ambiguous`, `unmatched`).
- **Human Approval Gate**: Interactive line-item editor, quantity adjustments, catalog product selectors, and exact decimal total calculation. Draft order creation does **not** deduct stock; stock deduction is strictly confined to atomic approval.

### 2.4 Invoices & Document Generation (Phases 5 & 5.1 & 5.2)
- **Atomic Sequential Allocation**: Database-enforced sequence format `INV-YYYYMM-XXXX` resetting per business per month.
- **Row-Level Concurrency Locks**: Business-first lock order (`businesses FOR UPDATE` then `orders FOR UPDATE`) eliminating race conditions and deadlocks.
- **Immutable Snapshots**: Captures `customer_snapshot` and `line_items_snapshot` in `JSONB` columns atomically with invoice issuance.
- **Verifiable PDF Streaming**: Deterministic ReportLab PDF byte streaming with secure download headers and zero path exposure.

### 2.5 Core Operations & Realtime (Phases 3 & 4)
- **Transaction-Safe Stock Operations**: `adjust_stock_atomic`, `approve_order_atomic`, and `cancel_order_atomic` PostgreSQL functions.
- **Supabase Realtime Sync**: Scoped strictly to `realtime:business:${businessId}` with client token authentication, multi-tenant isolation, and background refetching.

---

## 3. Project Structure

```text
Orqestra/
├── backend/
│   ├── app/
│   │   ├── api/                 # API routing and dependencies
│   │   │   ├── deps.py          # Auth and repository injection providers
│   │   │   └── v1/
│   │   │       ├── router.py    # V1 router aggregation
│   │   │       └── endpoints/
│   │   │           ├── ai_intake.py  # AI intake endpoints
│   │   │           ├── auth.py       # Auth verification endpoints
│   │   │           ├── customers.py  # Customer directory endpoints
│   │   │           ├── health.py     # System health probe
│   │   │           ├── inventory.py  # Stock & movement endpoints
│   │   │           ├── invoices.py   # Invoice & PDF endpoints
│   │   │           ├── orders.py     # Order lifecycle endpoints
│   │   │           └── products.py   # Catalog endpoints
│   │   ├── core/                # Configuration, logging, errors
│   │   │   ├── config.py
│   │   │   ├── errors.py
│   │   │   └── logging.py
│   │   ├── repositories/        # Repository layer (Supabase + InMemory)
│   │   │   ├── audit_repository.py
│   │   │   ├── business_repository.py
│   │   │   ├── customer_repository.py
│   │   │   ├── inventory_repository.py
│   │   │   ├── invoice_repository.py
│   │   │   ├── order_repository.py
│   │   │   └── product_repository.py
│   │   ├── schemas/             # Pydantic domain models
│   │   │   ├── ai_intake.py
│   │   │   ├── auth.py
│   │   │   ├── customers.py
│   │   │   ├── health.py
│   │   │   ├── inventory.py
│   │   │   ├── invoices.py
│   │   │   ├── orders.py
│   │   │   └── products.py
│   │   ├── services/            # Domain logic services
│   │   │   ├── ai_intake.py     # AI text extractor
│   │   │   ├── auth.py          # Supabase JWT verification
│   │   │   ├── authorization.py # Role and tenant enforcement
│   │   │   ├── health.py        # System health inspection
│   │   │   └── invoice_pdf.py   # ReportLab PDF generator
│   │   ├── tests/               # Backend pytest test suite (71 tests)
│   │   │   ├── test_authorization.py
│   │   │   ├── test_config.py
│   │   │   ├── test_errors.py
│   │   │   ├── test_health.py
│   │   │   ├── test_jwt_verification.py
│   │   │   ├── test_migrations.py
│   │   │   ├── test_operations.py
│   │   │   ├── test_phase5_ai_invoices.py
│   │   │   └── test_phase6_hardening.py
│   │   └── main.py              # Application entry point
│   ├── pytest.ini               # Backend test runner config
│   ├── requirements.txt         # Pinned backend dependencies
│   └── .env.example             # Backend environment template
├── frontend/
│   ├── public/                  # Assets (favicon.svg)
│   ├── src/
│   │   ├── app/                 # Root component with Providers
│   │   ├── components/          # Reusable UI components
│   │   │   ├── auth/            # SignInModal
│   │   │   ├── common/          # Button, Card, Badge, Alert, Pagination
│   │   │   ├── feedback/        # LoadingSpinner, EmptyState, ErrorState
│   │   │   ├── icons/           # Accessible vector SVG icons
│   │   │   ├── navigation/      # Header, NavigationShell
│   │   │   └── realtime/        # RealtimeStatusBadge
│   │   ├── context/             # AuthContext, RealtimeContext
│   │   ├── hooks/               # useRealtimeTable, useDebounce
│   │   ├── layouts/             # Responsive layout shells
│   │   ├── pages/               # Operational pages
│   │   │   ├── AIOpsPage.tsx
│   │   │   ├── CustomersPage.tsx
│   │   │   ├── FoundationDashboard.tsx
│   │   │   ├── InventoryPage.tsx
│   │   │   ├── InvoicesPage.tsx
│   │   │   ├── OrdersPage.tsx
│   │   │   └── ProductsPage.tsx
│   │   ├── services/            # API clients (api.ts, operations.ts, supabase.ts)
│   │   ├── styles/              # Design tokens and global rules
│   │   ├── types/               # TypeScript interfaces
│   │   └── utils/               # Formatting utilities
│   ├── tests/                   # Vitest test suite (37 tests across 7 files)
│   │   ├── App.test.tsx
│   │   ├── FoundationDashboard.test.tsx
│   │   ├── Operations.test.tsx
│   │   ├── Phase5.test.tsx
│   │   ├── Phase6.test.tsx
│   │   ├── Realtime.test.tsx
│   │   ├── SignInModal.test.tsx
│   │   └── setup.ts
│   ├── package.json             # Frontend dependencies
│   ├── tsconfig.json            # TypeScript configuration
│   └── vite.config.ts           # Bundler and Vitest configuration
├── supabase/
│   ├── migrations/              # Version-controlled SQL migrations
│   │   ├── 20261022000001_core_schema.sql
│   │   ├── 20261022000002_row_level_security.sql
│   │   ├── 20261023000001_operations_transactions.sql
│   │   ├── 20261023000002_realtime_publications.sql
│   │   ├── 20261023000003_invoices_and_allocation.sql
│   │   ├── 20261023000004_invoice_snapshots_and_constraints.sql
│   │   ├── 20261115000001_remediate_adjust_stock_atomic.sql
│   │   └── 20261122000001_harden_trigger_function_acls.sql
│   └── seed.sql                 # Reference development seed notes
├── docs/                        # Architecture, runbooks, and audit documentation
│   ├── architecture.md          # Architecture and database design
│   ├── testing.md               # Testing guide and verification status
│   ├── database/                # Schema reconciliation and migration guides
│   ├── deployment/              # Production & staging runbooks and onboarding guides
│   ├── development-reports/     # Historical phase release reports and trackers
│   └── security/                # Security audits, RLS integrity, and access controls
├── scripts/                     # Staging test runners, verification suites, and hash manifests
│   ├── README.md                # Scripts documentation and security invariants
│   ├── run_phase_4t_remote.py   # Dedicated remote/local staging functional runner
│   ├── test_runner_phase_4t.py  # Comprehensive runner security verification suite
│   ├── run_staging_diagnostic.py# Staging catalog and schema diagnostic runner
│   ├── PHASE_4T_HARDENED_FUNCTIONAL_TEST.sql # Approved transactional functional SQL
│   ├── PHASE_4T_APPROVED_HASHES.json         # Cryptographic hash manifest
│   └── PHASE_4L_CANONICAL_DIAGNOSTIC_1.sql   # Canonical diagnostic queries
├── .env.example                 # Root environment template
├── .gitignore                   # Git exclusion rules
├── Procfile                     # Process start configuration
├── pytest.ini                   # Root pytest configuration
├── README.md                    # Project documentation
├── render.yaml                  # Render deployment blueprint (FastAPI backend)
└── vercel.json                  # Vercel deployment blueprint (React frontend)
```

---

## 4. Prerequisites & Environment

- **Operating System**: Windows 10/11 (PowerShell).
- **Python**: Version 3.11.0 (compatible with 3.11+).
- **Node.js**: Version 20.x or higher (tested on Node v25.2.1).
- **Package Manager**: npm 10.x or higher (tested on npm 11.11.0).

---

## 5. Local Setup & Configuration

### 5.1 Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

### 5.2 Frontend Setup

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

### 5.3 Configuring Supabase Credentials in `.env`

In `backend/.env`:
```env
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
SUPABASE_JWT_SECRET=<your-jwt-secret>
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWT_ALGORITHM=HS256

# AI Configuration (Backend-only)
AI_PROVIDER=openai
AI_API_KEY=<your-openai-or-compatible-api-key>
AI_MODEL=gpt-4o-mini
AI_MAX_MESSAGE_LENGTH=4000
AI_REQUEST_TIMEOUT_SECONDS=15.0
```

In `frontend/.env`:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-anon-key>
```

> **Security Note**: Never expose `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, or `AI_API_KEY` in frontend code.

---

## 6. Running the Applications Locally

### 6.1 Start FastAPI Backend
```powershell
backend\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Endpoints:
- Operational Dashboard & Health: `http://127.0.0.1:8000/api/v1/health`
- Auth Verification: `http://127.0.0.1:8000/api/v1/auth/me`
- Products Catalog: `http://127.0.0.1:8000/api/v1/products`
- Inventory & Ledger: `http://127.0.0.1:8000/api/v1/inventory`
- Orders & Lifecycle: `http://127.0.0.1:8000/api/v1/orders`
- AI Order Extraction: `http://127.0.0.1:8000/api/v1/orders/ai-intake`
- Invoices & PDF Streaming: `http://127.0.0.1:8000/api/v1/invoices`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

### 6.2 Start React Frontend
```powershell
cd frontend
npm run dev
```
UI: `http://localhost:5173`

---

## 7. Automated Test Execution

### 7.1 Backend Automated Tests (pytest)
```powershell
backend\.venv\Scripts\pytest
```
Result: **71 passed in 2.14s (100% pass rate).**

### 7.2 Frontend Automated Tests (Vitest)
```powershell
cd frontend
npm test -- --run
```
Result: **37 passed in 4.68s across 7 test suites (100% pass rate).**

### 7.3 Frontend Production Build
```powershell
cd frontend
npm run build
```
Result: **113 modules transformed, 0 TypeScript errors, built successfully in 1.63s.**

---

## 8. Known Limitations & Production Blockers

1. **Remote Supabase Migrations**: Unapplied on remote Supabase per strict gate policy. Awaiting explicit user approval before running migrations `20261023000003` and `20261023000004`.
2. **Local PostgreSQL/Docker Infrastructure**: Local PostgreSQL and Docker daemons were not installed on this Windows host. Unit, component, and repository integration tests run against verified test harnesses; live PostgreSQL concurrency test suites are prepared for staging/containerized execution.
3. **Deployment Gateway Rate Limiting**: Production rate limiting should be enforced at the API gateway or reverse proxy layer (e.g. Cloudflare / Nginx / Traefik) rather than simulated in-memory.

# ORQESTRA: Production Deployment Runbook & Architecture Specification

> **Target Platforms:** FastAPI Backend on **Render** · React Frontend on **Vercel** · Database on **Supabase PostgreSQL**  
> **Security Baseline:** Row Level Security (RLS) · TLS 1.3 `sslmode=verify-full` · JWT Bearer Verification · Zero Secret Leakage  
> **Status:** Pre-Deployment Verified Locally · Awaiting Operator Manual Deployment

---

## 1. Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT BROWSER                                 │
│                                                                             │
│  React 18 + TypeScript + Vite SPA (Hosted on Vercel)                        │
│  - Public Browser Config: VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY  │
│  - API Endpoint Target: VITE_API_BASE_URL (points to Render Backend)        │
│  - Auth: Supabase GoTrue Client (stores session token in localStorage)      │
│  - Realtime: WebSocket direct to Supabase w/ tenant topic scoping           │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │                               │
       API Requests    │                               │  Direct Auth &
     (Bearer Token)    │                               │  Realtime Events
                       ▼                               ▼
┌─────────────────────────────────┐     ┌─────────────────────────────────────┐
│         FASTAPI BACKEND         │     │         SUPABASE PLATFORM           │
│       (Hosted on Render)        │     │                                     │
│                                 │     │ 1. Supabase Auth (GoTrue)           │
│ - Runtime: Python 3.11          │     │    - Issues JWT (HS256/ES256)       │
│ - Workers: 4 (Uvicorn ASGI)     │     │    - JWKS: /auth/v1/.well-known/    │
│ - Health Probe: GET /health     │     │ 2. PostgreSQL 15 Engine             │
│ - Auth: TokenVerificationService│     │    - 10 Application Tables          │
│   (Derives JWKS or verifies     │     │    - RLS Tenant Isolation Policies  │
│    HMAC JWT secret)             │     │    - Atomic RPC Functions           │
│ - AuthorizationService          │     │      (adjust_stock_atomic, etc.)    │
│   (Role hierarchy & X-Business) │     │    - Realtime Publication           │
│ - Invoice PDF: In-memory stream │     │ 3. Strict TLS (verify-full)         │
│ - AI Intake: Gemini 1.5 Flash   │     └──────────────────▲──────────────────┘
└────────────────┬────────────────┘                        │
                 │                                         │
                 │ SQL Queries & Atomic RPC (SCRAM-SHA-256)│
                 └─────────────────────────────────────────┘
```

### 1.1 Core Components
1. **Frontend (Vercel):** Single Page Application built with React 18, TypeScript, and Vite. Handles operator onboarding, catalog management, inventory tracking, order approvals, invoice generation, legal document inspection, and real-time operational feeds.
2. **Backend (Render):** FastAPI asynchronous service running on Python 3.11. Coordinates business operations, enforces role hierarchies (`owner` > `admin` > `staff`), verifies JWT tokens against Supabase JWKS / HMAC secrets, executes atomic database RPC functions, generates verifiable in-memory PDFs, and interfaces with Google Gemini for structured order extraction.
3. **Database (Supabase PostgreSQL):** Cloud PostgreSQL engine enforcing multi-tenant isolation via cryptographic Row Level Security (RLS), immutable audit ledgers, sequence-locked invoice generation, and atomic stock updates.

---

## 2. Local Development Setup

### 2.1 Backend Local Setup
```powershell
# Navigate to project root
cd c:\Users\aslam\Desktop\ORQESTRA

# Activate virtual environment
backend\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r backend/requirements.txt

# Configure environment
Copy-Item backend/.env.example backend/.env

# Run FastAPI backend in development mode
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Health Probe: `http://127.0.0.1:8000/health`
- OpenAPI Documentation: `http://127.0.0.1:8000/docs`

### 2.2 Frontend Local Setup
```powershell
# Navigate to frontend package
cd frontend

# Install dependencies
npm install

# Configure environment
Copy-Item .env.example .env

# Run Vite development server
npm run dev
```
- Development UI: `http://localhost:5173`
- Dev server proxy: Automatically forwards `/api/*` to `http://127.0.0.1:8000` to prevent loopback CORS and preflight overhead.

---

## 3. Required Environment Variables Specification

> **Security Rule:** Never commit real secrets to source control. Never place `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, or `GEMINI_API_KEY` in frontend configuration.

### 3.1 Backend Environment Variables (Render)

| Variable Name | Required | Default / Example Value | Description |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` | **Yes** | `production` | Deployment environment. Setting to `production` strictly forbids in-memory repository fallbacks and enforces database connectivity. |
| `DEBUG` | **Yes** | `false` | Disables debug mode and verbose stack traces. |
| `LOG_LEVEL` | **Yes** | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `HOST` | **Yes** | `0.0.0.0` | Bind host for ASGI server. |
| `PORT` | **Yes** | `10000` (injected by Render) | Bind port for Uvicorn ASGI server. |
| `CORS_ORIGINS` | **Yes** | `https://<your-frontend>.vercel.app` | Comma-separated list of allowed frontend origins for CORS. |
| `SUPABASE_URL` | **Yes** | `https://<project-ref>.supabase.co` | HTTPS endpoint of the target Supabase project. |
| `SUPABASE_PUBLISHABLE_KEY` | Optional | `sbp_...` | Supabase publishable client key. |
| `SUPABASE_ANON_KEY` | Optional | `eyJhb...` | Supabase anonymous client key. |
| `SUPABASE_SERVICE_ROLE_KEY` | **Yes** | `eyJhb...` | Supabase service-role administrative key. Used strictly server-side by backend repositories. |
| `SUPABASE_JWT_SECRET` | Optional | `<jwt-secret>` | Secret for verifying symmetric HMAC `HS256` tokens. If omitted, backend derives keys automatically from `SUPABASE_JWKS_URL`. |
| `SUPABASE_JWKS_URL` | Optional | `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` | Explicit JWKS endpoint for asymmetric `ES256`/`RS256` token verification. Auto-derived from `SUPABASE_URL` if omitted. |
| `SUPABASE_JWT_AUDIENCE` | **Yes** | `authenticated` | Standard JWT audience claim for Supabase authenticated users. |
| `SUPABASE_JWT_ISSUER` | Optional | `https://<project-ref>.supabase.co/auth/v1` | Standard JWT issuer claim. Auto-derived from `SUPABASE_URL` if omitted. |
| `SUPABASE_JWT_ALGORITHM` | **Yes** | `auto` (or `HS256` / `ES256`) | Algorithm for verifying Supabase access tokens. Set to `auto` (default) to safely accept either symmetric `HS256` or asymmetric `ES256` tokens from Supabase without rejecting valid sessions. If set explicitly to `HS256` or `ES256`, only tokens with that matching algorithm are accepted. |
| `AI_PROVIDER` | **Yes** | `gemini` | Primary AI provider for structured intake (`gemini` or `openai`). |
| `GEMINI_API_KEY` | Optional | `<gemini-api-key>` | Google Gemini API key for order extraction. |
| `AI_API_KEY` | Optional | `<api-key>` | Alternative API key parameter (falls back to `GEMINI_API_KEY`). |
| `AI_MODEL` | **Yes** | `gemini-3.5-flash-lite` | Model identifier for AI extraction. Uses modern `gemini-3.5-flash-lite` supported by Google's API. |
| `AI_MAX_MESSAGE_LENGTH` | Optional | `4000` | Maximum character length for customer message intake. |
| `AI_REQUEST_TIMEOUT_SECONDS`| Optional | `15.0` | Timeout threshold for AI provider network requests. |
| `AI_RATE_LIMIT_REQUESTS` | Optional | `15` | Maximum AI requests allowed per rate limit window. |
| `AI_RATE_LIMIT_WINDOW_SECONDS`| Optional | `60` | Rate limiting sliding window duration in seconds. |

### 3.2 Frontend Environment Variables (Vercel)

| Variable Name | Required | Default / Example Value | Description |
| :--- | :---: | :--- | :--- |
| `VITE_API_BASE_URL` | **Yes** | `https://<your-backend>.onrender.com` | Base URL of the deployed FastAPI backend. Must NOT include a trailing slash. |
| `VITE_SUPABASE_URL` | **Yes** | `https://<project-ref>.supabase.co` | Public Supabase endpoint for browser auth and realtime. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | **Yes** | `sbp_...` | Supabase public key. Safe to expose in client browser bundle. |
| `VITE_SUPABASE_ANON_KEY` | Optional | `eyJhb...` | Accepted alias if publishable key is not set. |

---

## 4. Render Backend Deployment Configuration

The repository includes a verified Infrastructure-as-Code blueprint (`render.yaml`) and Docker configuration.

### 4.1 Native Python Service (Recommended)
- **Service Name:** `orqestra-backend-api`
- **Environment:** `Python 3.11`
- **Plan:** `starter` (or `free`)
- **Region:** `singapore` (or closest to your Supabase PostgreSQL region)
- **Build Command:**
  ```bash
  pip install -r backend/requirements.txt
  ```
- **Start Command:**
  ```bash
  uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 4
  ```
- **Health Check Path:** `/health`
- **Auto Deploy:** Set to `false` for manual release control.

### 4.2 Blueprint Deployment via Render Dashboard
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New** → **Blueprint**.
3. Connect repository `https://github.com/ZMAXX07/ORQESTRA`.
4. Render will parse `render.yaml` and prompt for sensitive environment variables (`CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, etc.).
5. Fill in the required production environment variables.
6. Click **Apply**.

---

## 5. Vercel Frontend Deployment Configuration

The repository includes root `vercel.json` and `frontend/vercel.json` configured for SPA routing and security headers.

### 5.1 Project Setup on Vercel
1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** → **Project**.
3. Import the `ORQESTRA` GitHub repository.
4. Configure Project Settings:
   - **Framework Preset:** `Vite`
   - **Root Directory:** `frontend` (or leave as root `.`; both `vercel.json` files support either setup)
   - **Build Command:** `npm run build` (runs `tsc && vite build`)
   - **Output Directory:** `dist` (or `frontend/dist` if root was selected)
5. Configure Environment Variables in Vercel:
   - `VITE_API_BASE_URL` = `https://<your-render-service-name>.onrender.com`
   - `VITE_SUPABASE_URL` = `https://<project-ref>.supabase.co`
   - `VITE_SUPABASE_PUBLISHABLE_KEY` = `<your-supabase-publishable-or-anon-key>`
6. Click **Deploy**.

### 5.2 SPA Routing & Security Headers
Both `vercel.json` files enforce:
- Single Page Application fallback rewrite (`/(.*) -> /index.html`).
- HTTP headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`

---

## 6. Connecting Frontend to Backend (CORS & Communication)

1. Once the Vercel frontend is deployed, copy its production domain (e.g., `https://orqestra-web.vercel.app`).
2. Go to the Render backend service settings:
   - Update `CORS_ORIGINS` to: `https://orqestra-web.vercel.app` (if custom domain is also configured, comma-separate: `https://orqestra-web.vercel.app,https://app.orqestra.io`).
3. In Vercel frontend settings:
   - Ensure `VITE_API_BASE_URL` matches the Render backend URL (e.g., `https://orqestra-backend-api.onrender.com`).
4. Trigger a redeploy of the Vercel frontend if `VITE_API_BASE_URL` was modified after the initial build.

---

## 7. Production Supabase Configuration & Migration Status

> **CRITICAL WARNING:** Do NOT execute production migrations automatically. Production migrations require separate, explicit review and authorization.

### 7.1 Production Migrations Status
Staging project (`vclkeubwpiyhuvprvngx`) has all 8 migrations applied and passed full remote Phase 4T validation.

For the production project (`vwlwbwwrumsmjqeavvxk`):
- Migrations 1 through 6 were previously applied.
- **Pending Migration 7:** `20261115000001_remediate_adjust_stock_atomic.sql`
  - *Purpose:* Hardens the `adjust_stock_atomic` database function with explicit business scoping, strict parameter validation, caller role enforcement (`authenticated` vs `service_role`), and returns updated inventory state.
- **Pending Migration 8:** `20261122000001_harden_trigger_function_acls.sql`
  - *Purpose:* Revokes execute privileges from `PUBLIC` on sensitive triggers and helper functions, granting access strictly to `authenticated` and `service_role`.

### 7.2 Pre-Migration Safety Checklist for Production
Before applying pending migrations to production Supabase:
1. Export a full schema and data backup via Supabase CLI:
   ```bash
   npx supabase db dump --project-ref vwlwbwwrumsmjqeavvxk -f production_backup_pre_migration.sql
   ```
2. Verify zero active table locks on `inventory`, `stock_movements`, and `products`.
3. Apply migration 7 in an atomic transaction:
   ```bash
   npx supabase db push --project-ref vwlwbwwrumsmjqeavvxk
   ```
4. Verify function privileges:
   ```sql
   SELECT routine_name, routine_type, security_type
   FROM information_schema.routines
   WHERE routine_schema = 'public' AND routine_name = 'adjust_stock_atomic';
   ```

---

## 8. Post-Deployment Verification Runbook

Follow this checklist once Render, Vercel, and Supabase are configured:

1. **Backend Health Check:**
   - Execute: `curl -s https://<your-backend>.onrender.com/health`
   - Expect: HTTP 200 with JSON payload:
     ```json
     {
       "status": "healthy",
       "version": "0.1.0",
       "environment": "production",
       "services": {
         "database": {"status": "ok"},
         "auth": {"status": "ok"}
       }
     }
     ```
2. **Frontend Loading & Asset Delivery:**
   - Open `https://<your-frontend>.vercel.app` in a browser.
   - Verify page title is `Orqestra | Business Operations Platform`.
   - Verify favicon and logo render correctly.
   - Verify browser console has zero network failures or CORS errors.
3. **Authentication Verification:**
   - Click **Sign In** and authenticate with a valid operator account.
   - Verify JWT session token is received and authenticated state updates.
   - Verify `/api/v1/auth/me` responds with HTTP 200 and operator membership details.
4. **Tenant Isolation:**
   - Open a business workspace.
   - Inspect the network payload to confirm `X-Business-ID` header is attached to all business-scoped calls.
5. **Realtime Feed:**
   - Verify the bottom status indicator shows connected Realtime sync.
6. **PDF Generation:**
   - Navigate to Invoices, select an existing invoice, and click **Download PDF**.
   - Verify the PDF downloads promptly with correct line totals, formatted numbers, and proper filename (`invoice-INV-YYYYMM-XXXX.pdf`).
7. **Legal Modals:**
   - Click **Terms of Service** and **Privacy Policy** in the footer.
   - Confirm modal dialogs open, tabs switch smoothly, and document contents display properly.

---

## 9. Completed Work vs. Required Manual Actions

### 9.1 Completed Local Work (Verified & Pushed to GitHub)
- [x] All application source code for Frontend (React 18) and Backend (FastAPI).
- [x] Full test isolation and 100% pass rate:
  - Frontend: 16 test files, 143 passed, 0 failed.
  - Backend: 128 passed, 14 skipped, 0 failed.
- [x] Production build clean: `tsc && vite build` built in 3.67s with 0 errors.
- [x] Production configurations prepared and verified:
  - `render.yaml` configured with `sync: false` for `SUPABASE_JWT_ALGORITHM` and `gemini-3.5-flash-lite` for `AI_MODEL`.
  - `vercel.json` (root) and `frontend/vercel.json` configured with SPA routing and security headers.
  - `Procfile` and `backend/Dockerfile` configured with `backend.app.main:app`.
  - `.gitignore` hardened to protect `.env`, secrets, and connection files.
- [x] Legal modals for Terms of Service and Privacy Policy fully accessible from footer.
- [x] Commit history pushed cleanly to GitHub repository (`master` branch).

### 9.2 Manual Actions Required from Operator
- [ ] **Render Deployment:** Create Web Service or Blueprint on Render pointing to GitHub repository `ZMAXX07/ORQESTRA`.
- [ ] **Render Environment Configuration:** Set secret environment variables on Render (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CORS_ORIGINS`, `GEMINI_API_KEY`, etc.).
- [ ] **Vercel Deployment:** Create project on Vercel importing `ZMAXX07/ORQESTRA`.
- [ ] **Vercel Environment Configuration:** Set `VITE_API_BASE_URL` (Render URL), `VITE_SUPABASE_URL`, and `VITE_SUPABASE_PUBLISHABLE_KEY`.
- [ ] **Production Supabase Migrations:** Review, authorize, and apply pending migrations 7 and 8 to production project `vwlwbwwrumsmjqeavvxk`.
- [ ] **Legal Contact Customization:** Update placeholder contact addresses (`support@orqestra.io` and `privacy@orqestra.io`) in `frontend/src/components/legal/LegalModal.tsx` if a different operational support domain is desired.
- [ ] **Post-Deployment Verification:** Execute the verification runbook (Section 8) against the live production URLs.

# Orqestra: Supabase Authentication, Tenant Isolation & Onboarding Configuration Guide

## 1. Overview & Architecture

Orqestra implements a secure, multi-tenant B2B operating environment where:
- Every business has strict tenant isolation enforced at the database layer (Supabase PostgreSQL Row Level Security) and application layer (FastAPI JWT claims + `X-Business-ID` validation).
- Public registration allows new operators to create personal accounts without accessing existing business workspaces (such as the initial `demoshop` workspace).
- When a newly registered operator signs in, they are guided through **Create Your Business** workspace registration.
- A PostgreSQL database trigger (`trg_on_business_created`) securely provisions an authoritative `owner` membership for the creator. Clients cannot grant themselves arbitrary roles.

---

## 2. Supabase Authentication Settings Verification

Inspection of the remote Supabase Auth configuration (`GET /auth/v1/settings`) confirmed the current live settings:

| Setting | Value | Description |
| :--- | :--- | :--- |
| `disable_signup` | `false` | Public user registration is **enabled** on Supabase. |
| `mailer_autoconfirm` | `false` | Email verification is **required**. Newly registered accounts require confirmation before a full session is granted. |
| `external.email` | `true` | Email/password authentication provider is enabled. |
| `minimum_password_length` | `6` (Supabase) | Supabase baseline minimum length. Orqestra frontend enforces **8+ characters, with at least 1 letter and 1 number**. |

---

## 3. Required Supabase Dashboard Manual Settings

To ensure smooth public registration and recovery in production, verify the following in the **Supabase Dashboard**:

### A. Authentication > URL Configuration
1. **Site URL**:
   - Local development: `http://localhost:5173`
   - Staging/Production: `https://your-orqestra-domain.com`
2. **Redirect URLs** (Allow List):
   Add the following redirect URIs:
   - `http://localhost:5173/`
   - `http://localhost:5173/**`
   - `http://127.0.0.1:5173/`
   - `https://your-orqestra-domain.com/`
   - `https://your-orqestra-domain.com/**`

*Why*: After clicking an email confirmation link or a password reset link, Supabase redirects the user to the URL specified in `redirectTo` or the Site URL. The frontend catches hash fragment `#access_token=...&type=recovery` and automatically switches into the recovery/set-new-password modal.

### B. Authentication > Email Templates
Customize the email templates to use Orqestra branding:
1. **Confirm signup template**:
   - Subject: `Verify your Orqestra account`
   - Content: Direct user to verify and sign in to create their workspace.
2. **Reset password template**:
   - Subject: `Reset your Orqestra password`
   - Content: Direct user to reset password flow.

### C. Authentication > Email Settings (SMTP Delivery)
By default, Supabase applies rate limits (e.g., 3-4 emails per hour) on its shared development email service. For production:
1. Enable **Custom SMTP**.
2. Recommended providers: **Resend**, **SendGrid**, **Amazon SES**, or **Postmark**.
3. Sender Email: `noreply@yourdomain.com` or `auth@yourdomain.com`.
4. Sender Name: `Orqestra Platform`.

---

## 4. Tenant Isolation & Database Security

### A. Trigger-Enforced Ownership
When a user creates a business workspace:
1. Client issues: `INSERT INTO businesses (name, slug, currency) VALUES (...)`.
2. Row Level Security policy `businesses_insert_authenticated` allows any authenticated user to create a business row.
3. Database trigger `trg_on_business_created` executes with `SECURITY DEFINER`:
   ```sql
   INSERT INTO business_members (business_id, user_id, role, is_active)
   VALUES (NEW.id, auth.uid(), 'owner', true);
   ```
4. Client role assignment is prevented because `business_members` table does not allow arbitrary client insertions.
5. Frontend polls for membership creation confirmation before unlocking the workspace.

### B. Row Level Security (RLS) On All Tenant Tables
All operational tables enforce tenant isolation:
- `businesses`
- `business_members`
- `products`
- `inventory_levels`
- `stock_ledger`
- `customers`
- `orders`
- `order_items`
- `invoices`
- `audit_logs`

Every tenant table uses the `has_business_role(business_id, auth.uid(), 'staff' | 'admin' | 'owner')` security function:
```sql
CREATE POLICY products_select ON products
FOR SELECT TO authenticated
USING (has_business_role(business_id, auth.uid(), 'staff'));
```
No tenant can read, modify, or insert data into another tenant's workspace. Newly registered users have **zero access** to existing businesses (including `demoshop`) unless explicitly invited as a member.

### C. Backend API Authorization
FastAPI enforces tenant isolation on all `/api/v1/operations/*` and `/api/v1/auth/*` endpoints:
- Verifies Supabase JWT using the cryptographic secret.
- Extracts `X-Business-ID` header.
- Validates that the token's `sub` (user ID) has an active membership for `X-Business-ID`.
- Enforces role hierarchy: `owner > admin > staff`.
- Cross-tenant requests return `403 Forbidden` (`INSUFFICIENT_PERMISSIONS`).

---

## 5. Automated Test Suite Results

### Frontend Tests (Vitest)
- **Total Test Files**: 14 passed (14/14)
- **Total Tests**: 122 passed (122/122)
- **Key Test Suites**:
  - `PublicRegistration.test.tsx` (13 tests):
    - Sign Up and Sign In view switching
    - Form field validation (name, email format, password criteria)
    - Live password requirement indicators
    - Show/hide password toggles
    - Email verification pending state handling (`mailer_autoconfirm: false`)
    - Duplicate email error handling
    - Password reset and recovery flows
    - Empty workspace onboarding modal auto-display
    - Country auto-syncing primary currency (India -> INR, US -> USD, UK -> GBP, EU -> EUR, etc.)
    - Existing user skipping onboarding
    - Sign-in and sign-out flows
  - `SignInModal.test.tsx` (2 tests)
  - `Onboarding.test.tsx` (18 tests)
  - `Currencies.test.tsx` (16 tests)
  - `SystemStatusPage.test.tsx` (10 tests)
  - `ResponsiveLayout.test.tsx` (15 tests)
  - `Operations.test.tsx` (14 tests)
  - `App.test.tsx` (6 tests)
  - `Realtime.test.tsx` (12 tests)
  - `FormInputAlignment.test.tsx` (3 tests)
  - `SupabaseConfig.test.ts` (3 tests)
  - `FoundationDashboard.test.tsx` (3 tests)
  - `Phase5.test.tsx` (4 tests)
  - `Phase6.test.tsx` (3 tests)

### Backend Tests (Pytest)
- **Total Tests**: 112 passed (112/112)
- **Key Test Suites**:
  - `test_authorization.py`: Multi-tenant isolation, cross-business access denied (403), forged business ID rejection, role hierarchy enforcement.
  - `test_privileged_access_security.py`: Owner and admin permission boundaries.
  - `test_jwt_verification.py`: Token authenticity, signature validation, expiration, and algorithm safety.
  - `test_operations.py`: Tenant-scoped CRUD on products, inventory, orders, customers, and invoices.
  - `test_postgres_staging.py` & `test_migrations.py`: Schema constraints, trigger integrity, and RLS policies.

### Frontend Production Build
- `npm run build` completed successfully (`tsc && vite build`).
- Dist files generated with clean chunking and zero typecheck errors.

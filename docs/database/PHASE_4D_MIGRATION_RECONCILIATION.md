# ORQESTRA — Phase 4D: Migration History Reconciliation Audit

**Audit Date:** November 15, 2026  
**Auditor:** Senior DevOps & Database Reliability Engineer  
**Target Repository:** ORQESTRA (`master` branch, commit `976446de`)  
**Scope:** Migration Version Discrepancy Investigation, Git Archaeology, Remote Schema Parity vs. CLI Ledger, and Dependency Analysis  
**Final Status:** **GO FOR CONTROLLED STAGING RELEASE (SUBJECT TO EXPLICIT OPERATOR APPROVAL)**

---

## 1. Executive Summary & The Discrepancy Investigation

### 1.1 The Identified Discrepancy
In earlier documentation, an explicit discrepancy appeared between two reports:
- **Phase 4A Report (`PHASE_4A_LOCAL_STAGING_REPORT.md` §6.2):** Listed six sequential daily migrations:
  `20261021000001`, `20261022000001`, `20261023000001`, `20261024000001`, `20261025000001`, `20261026000001`
- **Phase 4C Report (`PHASE_4C_FINAL_CODE_REVIEW.md` §4.1):** Listed the actual on-disk migration files:
  `20261022000001`, `20261022000002`, `20261023000001`, `20261023000002`, `20261023000003`, `20261023000004` (plus new patch `20261115000001`)

### 1.2 Root Cause of the Discrepancy
A rigorous forensic audit of Git history, file systems, and past phase reports confirms:
1. **The Phase 4A Table Was a Documentation Transcription Error:**
   - Git history confirms that files named `20261021000001_multi_business_core.sql`, `20261024000001_ai_orchestration.sql`, `20261025000001_reporting_analytics.sql`, and `20261026000001_indexes_hardening.sql` **never existed in the Git repository at any point in time**.
   - The tables described in that Phase 4A table (e.g. `ai_conversations`, `ai_messages`, materialized views) do not exist anywhere in the ORQESTRA codebase, models, tests, or database.
   - The author of Phase 4A erroneously transcribed a hypothetical/conceptual schema progression instead of referencing the actual files on disk.
2. **The True Historical Migrations Are Defined by Git Commit `d0b64b7`:**
   - All six original migration files were committed simultaneously on November 5, 2026, in commit `d0b64b7`.
   - Their exact timestamps, file names, SHA256 checksums, and schema objects correspond precisely to the Phase 1 (`STAGING_DEPLOYMENT_PLAN.md`), Phase 2 (`PHASE_2_STAGING_VERIFICATION.md`), Phase 3 (`PHASE_3_STAGING_DEPLOYMENT_READINESS.md`), and Phase 4C reports.

---

## 2. On-Disk Migration Inventory & Checksums

Every file currently in `supabase/migrations/` was verified with SHA-256 cryptographic hashing and exact byte lengths:

| Timestamp ID | Filename | Size | SHA-256 Checksum | Git Status |
|---|---|:---:|---|:---:|
| `20261022000001` | `20261022000001_core_schema.sql` | 13,873 B | `eb990b8dbaeb6636f93430725e5022756ae14257e046ec41fb33114a31aed01f` | Tracked (`d0b64b7`) |
| `20261022000002` | `20261022000002_row_level_security.sql` | 15,224 B | `8f8decddfac63ce8a9ef45891b87c18f2f05ab2045a69053292756ca4491342a` | Tracked (`d0b64b7`) |
| `20261023000001` | `20261023000001_operations_transactions.sql` | 19,449 B | `c4e98ac9539942e70570e4e9b95a2d42b911b2f5356f7ff4f061c48dee68fe6b` | Tracked (`d0b64b7`) |
| `20261023000002` | `20261023000002_realtime_publications.sql` | 2,311 B | `3ba2196300a6da28a74bf8ab93eeac991267fabf3c6f31f01fecf427bcf3eb87` | Tracked (`d0b64b7`) |
| `20261023000003` | `20261023000003_invoices_and_allocation.sql` | 8,307 B | `36d5a1bd81c36b998b18060dc644dcd635d97f1d4fc8a33e0b36f7354d9e391c` | Tracked (`d0b64b7`) |
| `20261023000004` | `20261023000004_invoice_snapshots_and_constraints.sql` | 10,790 B | `a5e5d6dd39874e1370b60181105e970d0993de08c4089a566b55416f25fdd48b` | Tracked (`d0b64b7`) |
| `20261115000001` | `20261115000001_remediate_adjust_stock_atomic.sql` | 5,714 B | `ad50a60dea36a2ebaeddb1fbc97499b23dfc93ede1561c2bce9dc30d3bfd3cfe` | Untracked (New Patch) |

---

## 3. Git History Forensic Inspection

An inspection of all Git log events, reflogs, and commit trees was conducted:
1. **Commit `d0b64b7` (Initial Migration Baseline):**
   - Author: Initial Setup
   - Date: November 5, 2026
   - Files added: Exactly the six historical files listed above.
2. **Rename and Deletion Check:**
   - `git log --all --full-history -- "**/20261021*"` returned 0 commits.
   - `git log --all --full-history -- "**/20261024*"` returned 0 commits.
   - `git log --all --full-history -- "**/20261025*"` returned 0 commits.
   - `git log --all --full-history -- "**/20261026*"` returned 0 commits.
   - **Conclusion:** No migration files were ever renamed, moved, or deleted.

---

## 4. Cross-Report Analysis: Phase 1 Through Phase 4C

| Document | Section | Migration IDs Cited | Source of Truth Checked | Verdict |
|---|---|---|:---:|:---:|
| `STAGING_DEPLOYMENT_PLAN.md` (Phase 1) | §2.2 | `20261022000001`, `20261022000002`, `20261023000001`, `20261023000002`, `20261023000003`, `20261023000004` | Disk Inspection | **Accurate** |
| `PHASE_2_STAGING_VERIFICATION.md` (Phase 2) | §1.2 | `20261022000001`, `20261022000002`, `20261023000001`, `20261023000002`, `20261023000003`, `20261023000004` | PostgREST OpenAPI Probe | **Accurate** |
| `PHASE_3_STAGING_DEPLOYMENT_READINESS.md` (Phase 3) | §3.1 | `20261022000001`, `20261022000002`, `20261023000001`, `20261023000002`, `20261023000003`, `20261023000004` | Real PostgreSQL Runner | **Accurate** |
| `PHASE_4_STAGING_RELEASE_REPORT.md` (Phase 4) | §2.2 | `20261022000001`, `20261022000002`, `20261023000001`, `20261023000002`, `20261023000003`, `20261023000004` | Reconciled Table | **Accurate** |
| `PHASE_4A_LOCAL_STAGING_REPORT.md` (Phase 4A) | §6.2 | `20261021000001`, `20261022000001`, `20261023000001`, `20261024000001`, `20261025000001`, `20261026000001` | **None (Fictitious Text)** | **TRANSCRIPTION ERROR** |
| `PHASE_4C_FINAL_CODE_REVIEW.md` (Phase 4C) | §4.1 | `20261022000001`, `20261022000002`, `20261023000001`, `20261023000002`, `20261023000003`, `20261023000004`, `20261115000001` | Disk & Git Check | **Accurate** |

---

## 5. Remote Schema State vs. Migration CLI Ledger State

To guarantee safe deployment without database errors, we must strictly separate the two distinct layers of state in Supabase:

```mermaid
flowchart TD
    subgraph Remote Supabase Instance (vwlwbwwrumsmjqeavvxk)
        subgraph Layer 1: Actual PostgreSQL Schema (public)
            T1["10 Core Tables<br/>(businesses, orders, etc.)"]
            R1["RPC Functions<br/>(adjust_stock_atomic, etc.)"]
            P1["Realtime Publications<br/>(supabase_realtime)"]
            RLS1["Row Level Security<br/>(All 10 tables protected)"]
        end
        subgraph Layer 2: CLI Migration Metadata (supabase_migrations)
            MTable["schema_migrations Table<br/>(Managed by Supabase CLI)"]
            MState["Current State: UNRECORDED<br/>(Applied via Web SQL Editor)"]
        end
    end
    
    T1 -.->|"Interacted with by"| App["FastAPI Backend & React Frontend<br/>(Operational & Functional)"]
    MTable -.->|"Checked by"| CLI["Supabase CLI (supabase db push)<br/>(Fails if ledger is out of sync)"]
```

1. **Layer 1: Actual Remote Schema State (`public`):**
   - Verified via PostgREST OpenAPI and Phoenix WebSocket probes in Phase 2.
   - All 10 tables, 4 enums, composite foreign keys, RLS policies, append-only triggers, Realtime publication channels, and RPCs are **100% active and present**.
   - The application runtime operates against this layer; it has zero dependency on the CLI ledger table.
2. **Layer 2: CLI Migration Ledger State (`supabase_migrations.schema_migrations`):**
   - The Supabase CLI tracks applied migrations in `supabase_migrations.schema_migrations`.
   - Because migrations 1 through 6 were applied via the Supabase Web SQL Editor during project initialization, their version timestamps are **unrecorded** in this table.
   - **Critical Operational Implication:** If an operator runs `supabase db push` without first running `supabase migration repair`, the CLI will attempt to run `20261022000001_core_schema.sql` from the beginning. PostgreSQL will return `relation "businesses" already exists` and abort the deployment.
   - Therefore, the 6 historical migrations must be registered in the CLI ledger using `supabase migration repair --status applied` prior to executing `supabase db push`.

---

## 6. Dependency Analysis of the New Patch Migration

The new patch migration `20261115000001_remediate_adjust_stock_atomic.sql` was audited against remote schema objects to ensure it does not depend on any missing table, column, type, or function:

| Referenced Database Object | Object Type | Declaring Migration | Remote Verification Status | Dependency Risk |
|---|---|---|:---:|:---:|
| `stock_movement_type` | Enum Type | `20261022000001` | Active in Remote OpenAPI | **None** |
| `public.get_auth_user_id()` | Helper Function | `20261022000002` | Active in Remote RPCs | **None** |
| `auth.role()` | Supabase Function | Supabase Core | Active in Remote Supabase | **None** |
| `public.has_business_role(UUID, UUID, TEXT)` | Security Function | `20261022000002` | Active in Remote RPCs | **None** |
| `public.products` (`id`, `business_id`) | Table & Columns | `20261022000001` | Active in Remote OpenAPI | **None** |
| `public.inventory` (`id`, `business_id`, `product_id`, `quantity_on_hand`, `updated_at`) | Table & Columns | `20261022000001` | Active in Remote OpenAPI | **None** |
| `public.stock_movements` (7 columns) | Table & Columns | `20261022000001` | Active in Remote OpenAPI | **None** |
| `public.audit_logs` (8 columns) | Table & Columns | `20261022000002` | Active in Remote OpenAPI | **None** |
| `authenticated`, `service_role` | Roles | Supabase Core | Active in Remote Engine | **None** |

**Conclusion:** The patch migration has **zero unresolved dependencies**. All referenced prerequisite objects exist and are operational in the remote database.

---

## 7. Definitive Migration Reconciliation Table

| Version ID | Full Filename on Disk | Declared Schema Objects | Remote Verification Evidence | CLI Ledger Status | Confidence Level | Safe Operator Action |
|---|---|---|---|:---:|:---:|---|
| **`20261022000001`** | `20261022000001_core_schema.sql` | 10 tables, 4 enums, composite keys, check constraints | OpenAPI `/rest/v1/` shows all 10 tables, PKs, FKs | Unrecorded | **100% (High)** | `supabase migration repair --status applied 20261022000001` |
| **`20261022000002`** | `20261022000002_row_level_security.sql` | RLS on 10 tables, `has_business_role`, immutable triggers | Anon requests return 0 rows; helper RPCs callable | Unrecorded | **100% (High)** | `supabase migration repair --status applied 20261022000002` |
| **`20261023000001`** | `20261023000001_operations_transactions.sql` | `adjust_stock_atomic`, `approve_order_atomic`, `cancel_order_atomic`, `is_active` | `/rpc/approve_order_atomic` operational; 42702 defect noted in `adjust_stock_atomic` | Unrecorded | **100% (High)** | `supabase migration repair --status applied 20261023000001` |
| **`20261023000002`** | `20261023000002_realtime_publications.sql` | Publication `supabase_realtime`, `REPLICA IDENTITY FULL` on 4 tables | Phoenix WS channels `products`, `inventory`, `orders`, `stock_movements` acknowledge OK | Unrecorded | **100% (High)** | `supabase migration repair --status applied 20261023000002` |
| **`20261023000003`** | `20261023000003_invoices_and_allocation.sql` | `invoices` added to realtime, initial `allocate_invoice_atomic` | Phoenix WS channel `invoices` acknowledges OK; index confirmed | Unrecorded | **100% (High)** | `supabase migration repair --status applied 20261023000003` |
| **`20261023000004`** | `20261023000004_invoice_snapshots_and_constraints.sql` | `line_items_snapshot`, `customer_snapshot`, partial unique index | JSONB snapshot columns verified in OpenAPI; 0 duplicate invoices | Unrecorded | **100% (High)** | `supabase migration repair --status applied 20261023000004` |
| **`20261115000001`** | `20261115000001_remediate_adjust_stock_atomic.sql` | Remediated `adjust_stock_atomic` with qualified column references | Tested locally on PG 16: 10/10 checks PASS | Pending Apply | **100% (High)** | `supabase db push` (cleanly applies patch) |

---

## 8. Safe Staging Deployment Protocol

When the operator receives explicit authorization to execute the remote deployment, the following commands must be run in sequence:

```powershell
# ------------------------------------------------------------------------------
# STEP 1: Verify Supabase Connection & Linked Project
# ------------------------------------------------------------------------------
npx supabase status

# ------------------------------------------------------------------------------
# STEP 2: Record Pre-Existing Migrations in the Remote CLI Ledger
# (Does NOT modify schema or data; prevents "table already exists" collisions)
# ------------------------------------------------------------------------------
npx supabase migration repair --status applied 20261022000001
npx supabase migration repair --status applied 20261022000002
npx supabase migration repair --status applied 20261023000001
npx supabase migration repair --status applied 20261023000002
npx supabase migration repair --status applied 20261023000003
npx supabase migration repair --status applied 20261023000004

# ------------------------------------------------------------------------------
# STEP 3: Verify Ledger Parity
# (Must report 20261022000001 - 20261023000004 as applied, 20261115000001 as pending)
# ------------------------------------------------------------------------------
npx supabase migration list

# ------------------------------------------------------------------------------
# STEP 4: Apply Remediated Patch Migration
# ------------------------------------------------------------------------------
npx supabase db push

# ------------------------------------------------------------------------------
# STEP 5: Verify Remote RPC Remediation
# (Execute manual stock adjustment in frontend; assert HTTP 200 and zero 42702 errors)
# ------------------------------------------------------------------------------
```

---

## 9. Final Decision & Recommendation

### **RECOMMENDATION: GO FOR CONTROLLED STAGING RELEASE**

1. **Discrepancy Fully Resolved:** The Phase 4A migration table was a documentation error; the real, immutable on-disk and Git history baseline has been conclusively established as `20261022000001` through `20261023000004`.
2. **Remote Schema Parity Verified:** All objects declared across migrations 1 through 6 exist and are operational in remote Supabase.
3. **Patch Migration Verified:** Migration `20261115000001` has zero unresolved dependencies and passed all 10 real PostgreSQL regression scenarios.
4. **Safety Protocol Defined:** The exact migration repair commands have been formulated to prevent CLI collision errors.
5. **Strict Safety Compliance:** No remote operations, ledger modifications, commits, pushes, or deployments have been executed.

**Next Action:** Awaiting explicit operator direction to initiate the remote migration repair and release sequence.

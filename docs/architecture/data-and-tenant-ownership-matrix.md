# Data & Tenant Ownership Matrix, Index & Constraint Rationale

**Project:** Multi-Tenant Learning & Coaching Management SaaS  
**Version:** 1.0  
**Date:** 2026-11-05  

---

## 1. Data Ownership Matrix

This matrix defines the lifecycle ownership, creation permissions, read scope, and update boundaries across user roles for every entity in the database.

| Entity | Primary Owner | Created By | Read Scope | Update Scope | Deletion / Archive Policy |
|---|---|---|---|---|---|
| `organizations` | Platform / Org Admin | Self-Registration / SuperAdmin | Org Admin, Platform | Org Admin (settings), Platform | Soft delete via `deleted_at`; data retained for organization |
| `users` | Organization | Org Admin / Self-Registration (code) | Org Admin, Self (own record) | Org Admin, Self (own profile) | Soft delete (`deleted_at`); 1-day purge queue per Decision Q12 |
| `organization_memberships` | Organization | System (on user register/invite) | Org Admin, Self | Org Admin | State transition to `'left'` or `'transferred'` |
| `student_profiles` | Student / Organization | System / Student | Org Admin, Assigned Teachers, Self | Student (bio), Admin | Cascade with user or soft-deleted |
| `teacher_profiles` | Teacher / Organization | System / Teacher | Org Admin, All Students in Org, Self | Teacher (bio, spec), Admin | Cascade with user or soft-deleted |
| `batches` | Organization | Org Admin, Primary Teacher | Org Admin, Assigned Teachers, Enrolled Students | Org Admin, Primary Teacher | Soft delete via `deleted_at` / status `'archived'` |
| `batch_memberships` | Organization / Student | Org Admin, Primary Teacher | Org Admin, Assigned Teachers, Self | Org Admin | Status `'transferred'` with destination batch pointer (Decision Q4) |
| `batch_teacher_assignments` | Organization / Batch | Org Admin | Org Admin, Assigned Teachers | Org Admin | Status `'inactive'` |
| `attendance` | Batch / Organization | Teacher, Org Admin | Org Admin, Assigned Teachers, Student (own only) | Teacher, Admin (corrections tracked via `corrected_at`) | Permanent record; corrections logged in audit trail |
| `assignments` | Batch / Teacher | Teacher, Org Admin | Org Admin, Assigned Teachers, Enrolled Students | Teacher, Admin | Status `'closed'` after due date; revisions create new version |
| `assignment_versions` | Assignment | Teacher, Org Admin (on edit) | Org Admin, Assigned Teachers, Enrolled Students | **Immutable** (no updates allowed) | Never deleted; preserves integrity of historical submissions |
| `assignment_submissions` | Student | Student | Org Admin, Assigned Teachers, Self (own only) | Student (prior to grading / resubmit), Teacher (score/feedback) | Retained per organization data lifecycle |
| `coding_tasks` | Assignment | Teacher, Org Admin | Org Admin, Assigned Teachers, Enrolled Students | Teacher, Admin | Cascade with assignment |
| `files` | User / Organization | Any authenticated user | Enrolled/Authorized users in Org via presigned URLs | Uploader | Status `'deleted'` in registry, purged from bucket |
| `announcements` | Organization / Batch | Org Admin, Teacher | Org members (or batch members if scoped) | Author, Org Admin | Status `'archived'` |
| `notifications` | Recipient User | System / Background Workers | Recipient (Self only) | Recipient (`read_at` timestamp) | Retained until user dismissal or archive window |
| `audit_logs` | Platform Security | System / Services automatically | Org Admin (scoped to Org), SuperAdmin (global) | **Append-only** (No updates or deletes permitted) | Immutable permanent audit trail |

---

## 2. Tenant Ownership Matrix

Every entity in the database belongs to a specific tenant boundary. This matrix explicitly defines the isolation key, foreign key cascade behaviors, and cross-tenant rules.

| Entity | Tenant Isolation Key (`organization_id`) | Nullable? | Foreign Key Reference | On Delete Behavior | Cross-Tenant Query Rule |
|---|---|---|---|---|---|
| `organizations` | `id` (is tenant anchor) | No | Root anchor | N/A | Accessible only by organization members |
| `users` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Cannot query or reference users from another org |
| `files` | `organization_id` | No | `organizations(id)` | `RESTRICT` | File presigned URLs scoped strictly to tenant files |
| `organization_memberships` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Scoped to tenant |
| `student_profiles` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Profile never visible across organizations |
| `teacher_profiles` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Profile never visible across organizations |
| `batches` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Batches isolated per tenant; slugs unique per org |
| `batch_memberships` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Transfer allowed only within the same organization |
| `batch_teacher_assignments` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Teachers assigned only to batches in their org |
| `attendance` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Attendance records completely tenant-isolated |
| `assignments` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Assignments isolated per tenant |
| `assignment_versions` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Versions isolated per tenant |
| `assignment_submissions` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Submissions never accessible cross-tenant |
| `coding_tasks` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Coding task isolated per tenant |
| `announcements` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Announcements never broadcast cross-tenant |
| `notifications` | `organization_id` | No | `organizations(id)` | `RESTRICT` | Notifications never delivered cross-tenant |
| `audit_logs` | `organization_id` | **Yes** (Nullable) | `organizations(id)` | `SET NULL` | Tenant Admin views logs where `org_id = :org_id`. SuperAdmin views all. |

---

## 3. Index Rationale

Indexes are designed to guarantee high query throughput, prevent table locks during foreign key operations, and support multi-tenant query performance.

| Index Name | Table | Columns | Rationale |
|---|---|---|---|
| `idx_organizations_slug` | `organizations` | `slug` | Fast tenant lookup during subdomain / slug resolution. |
| `idx_organizations_code` | `organizations` | `code` | Fast validation during user self-registration join flow (Decision Q2-C). |
| `idx_users_org_id` | `users` | `organization_id` | Primary tenant filter applied on every user query. |
| `idx_users_org_role` | `users` | `organization_id, role` | Fast filtering for teacher directory and student listings. |
| `idx_files_org_id` | `files` | `organization_id` | Fast file listing and quota calculations. |
| `idx_files_uploaded_by` | `files` | `uploaded_by` | Prevents table locks during user deletion or audit lookups. |
| `idx_batches_org_status` | `batches` | `organization_id, status` | Primary dashboard query (e.g. "active batches in this organization"). |
| `idx_batch_memberships_org_batch` | `batch_memberships` | `organization_id, batch_id` | Retrieval of all students enrolled in a specific batch. |
| `idx_batch_memberships_student` | `batch_memberships` | `organization_id, student_id` | Retrieval of all batches a student is currently taking. |
| `idx_attendance_org_batch_date` | `attendance` | `organization_id, batch_id, attendance_date` | Primary attendance sheet lookup for a specific class date. |
| `idx_assignments_due_date` | `assignments` | `organization_id, due_date` | Upcoming assignment deadlines and auto-close worker queries. |
| `idx_submissions_org_assignment` | `assignment_submissions` | `organization_id, assignment_id` | Teacher grading queue fetching all submissions for an assignment. |
| `idx_notifications_user_unread` | `notifications` | `user_id` WHERE `read_at IS NULL` | **Partial Index**: Zero-cost query for unread notification count badge in navigation bar. |
| `idx_audit_logs_org_created` | `audit_logs` | `organization_id, created_at DESC` | Reverse-chronological security audit log stream per organization. |

---

## 4. Constraint Rationale

Integrity rules are enforced at the database level by PostgreSQL to ensure no race conditions, application bugs, or direct queries can corrupt multi-tenant invariants.

### 4.1 Tenant-Scoped Composite Uniqueness
1. **`uq_users_org_email` (`organization_id, email`)**:
   - Allows a user with email `john@example.com` to exist in Organization A and Organization B independently without collision, while preventing duplicate accounts in the same organization.
2. **`uq_batches_org_slug` (`organization_id, slug`)**:
   - Ensures distinct, clean URL paths for batches within a tenant while allowing identical slugs (e.g., `/batches/spring-2026`) across different organizations.
3. **`uq_files_org_path` (`organization_id, storage_bucket, storage_path`)**:
   - Prevents collision of storage paths within an organization's bucket allocation.

### 4.2 Idempotent Attendance
- **`uq_attendance_idempotent` (`organization_id, batch_id, student_id, attendance_date`)**:
   - Strictly enforces that a student has at most ONE attendance record in a batch on a given day.
   - Enables atomic, idempotent batch updates using:
     ```sql
     INSERT INTO attendance (...) VALUES (...)
     ON CONFLICT (organization_id, batch_id, student_id, attendance_date)
     DO UPDATE SET status = EXCLUDED.status, remarks = EXCLUDED.remarks, corrected_at = now();
     ```

### 4.3 Immutable Assignment Revision Protection
- **`uq_assignment_versions` (`assignment_id, version_number`)**:
   - Guarantees sequential, non-colliding revision numbers.
   - When a teacher updates an assignment description or max score, the original version remains untouched, ensuring existing student submissions remain linked to the exact assignment rubric they followed.

### 4.4 PostgreSQL Enforced Storage Quota
- **`chk_files_max_size_4mb` (`size_bytes > 0 AND size_bytes <= 4194304`)**:
   - Hard database constraint ensuring no record can reference an asset exceeding the 4 MiB limit agreed upon in Decision Q11.

---

## 5. Row-Level Security (RLS) Evaluation

### Current Decision: Application-Layer Scoping First (No Database RLS in Phase 1)
As formally accepted in **ADR-0001**, PostgreSQL Row-Level Security (RLS) is intentionally **deferred**.

### Why RLS is not used in Phase 1:
1. **Single Security Boundary**: FastAPI acts as the strict security boundary. All queries use explicit `WHERE organization_id = :org_id` parameterized clauses.
2. **Operational Simplicity**: Avoids complexity in Alembic migrations, connection poolers (PgBouncer in transaction mode wipes session-level configuration variables like `SET LOCAL app.current_org_id`), and simplifies debugging.
3. **Testability**: Application-level scoping is verifiable via deterministic, fast pytest integration tests.

### Proposed Architecture if RLS is Introduced in a Future Phase:
If compliance or regulatory requirements mandate database-level RLS in Phase 8+, the following runtime model must be used:

1. **PostgreSQL Role**: A dedicated application role `app_user` with restricted table privileges.
2. **Session Claim Flow**:
   - On checking out an async connection from the SQLAlchemy pool, the application executes:
     ```sql
     SELECT set_config('request.jwt.claim.org_id', :org_id_from_jwt, true);
     SELECT set_config('request.jwt.claim.role', :role_from_jwt, true);
     ```
3. **Policy Definition**:
   ```sql
   ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
   CREATE POLICY tenant_isolation_policy ON batches
       FOR ALL
       TO app_user
       USING (organization_id = NULLIF(current_setting('request.jwt.claim.org_id', true), '')::uuid);
   ```
4. **SuperAdmin Bypass**: Internal maintenance and audit worker connections connect via a `platform_admin` role with `BYPASSRLS`.


-- =============================================================================
-- Multi-Tenant Learning & Coaching SaaS — Initial Database Migration
-- Version: 20261105000000
-- =============================================================================
-- Migration strictly adheres to:
-- 1. UUID primary keys (gen_random_uuid())
-- 2. Organization / tenant scoping on all tenant-owned entities
-- 3. Composite unique constraints including organization_id
-- 4. Explicit status CHECK constraints
-- 5. Foreign key integrity enforcement (RESTRICT / CASCADE / SET NULL)
-- 6. Storage file size constraint (4 MiB max per Decision Q11)
-- 7. Idempotent attendance constraint on (organization_id, batch_id, student_id, attendance_date)
-- 8. Immutable assignment version snapshots for trustworthy submission history
-- =============================================================================

-- Enable pgcrypto for gen_random_uuid if not already present
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- 1. Organizations (Root Tenant Entity)
-- -----------------------------------------------------------------------------
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(50) NOT NULL UNIQUE, -- Join code for student/teacher onboarding (Decision Q2-C)
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'archived')),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_code ON organizations(code);
CREATE INDEX idx_organizations_status ON organizations(status);

-- -----------------------------------------------------------------------------
-- 2. Files (Registry for all tenant file assets with 4MB hard limit)
-- -----------------------------------------------------------------------------
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    storage_bucket VARCHAR(100) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    -- Enforce 4 MiB (4,194,304 bytes) upper bound in PostgreSQL (Decision Q11)
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 4194304),
    uploaded_by UUID NULL, -- Forward referenced to users(id), constraint added below
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT uq_files_org_path UNIQUE (organization_id, storage_bucket, storage_path)
);

CREATE INDEX idx_files_org_id ON files(organization_id);
CREATE INDEX idx_files_status ON files(organization_id, status);

-- -----------------------------------------------------------------------------
-- 3. Users (Platform Identities Scoped to Tenant)
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    email VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended', 'deleted')),
    avatar_file_id UUID NULL REFERENCES files(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL, -- Soft-delete retention per Decision Q12
    created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_users_org_email UNIQUE (organization_id, email)
);

CREATE INDEX idx_users_org_id ON users(organization_id);
CREATE INDEX idx_users_org_role ON users(organization_id, role);
CREATE INDEX idx_users_org_status ON users(organization_id, status);

-- Now add foreign key for files.uploaded_by -> users.id
ALTER TABLE files ADD CONSTRAINT fk_files_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX idx_files_uploaded_by ON files(uploaded_by);

-- -----------------------------------------------------------------------------
-- 4. Organization Memberships (Historical & Lifecycle Ledger)
-- -----------------------------------------------------------------------------
CREATE TABLE organization_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended', 'left', 'transferred')),
    joined_via VARCHAR(50) NOT NULL DEFAULT 'code' CHECK (joined_via IN ('code', 'admin_invite', 'system')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_org_memberships_org_user UNIQUE (organization_id, user_id)
);

CREATE INDEX idx_org_memberships_org_user ON organization_memberships(organization_id, user_id);
CREATE INDEX idx_org_memberships_user ON organization_memberships(user_id);

-- -----------------------------------------------------------------------------
-- 5. Student Profiles
-- -----------------------------------------------------------------------------
CREATE TABLE student_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    enrollment_number VARCHAR(100) NULL,
    guardian_name VARCHAR(200) NULL,
    guardian_contact VARCHAR(100) NULL,
    date_of_birth DATE NULL,
    bio TEXT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'graduated', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_student_profiles_org_user UNIQUE (organization_id, user_id),
    CONSTRAINT uq_student_profiles_org_enrollment UNIQUE (organization_id, enrollment_number)
);

CREATE INDEX idx_student_profiles_org_id ON student_profiles(organization_id);

-- -----------------------------------------------------------------------------
-- 6. Teacher Profiles
-- -----------------------------------------------------------------------------
CREATE TABLE teacher_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    employee_id VARCHAR(100) NULL,
    specialization VARCHAR(255) NULL,
    qualification VARCHAR(255) NULL,
    bio TEXT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'on_leave', 'terminated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_teacher_profiles_org_user UNIQUE (organization_id, user_id),
    CONSTRAINT uq_teacher_profiles_org_employee UNIQUE (organization_id, employee_id)
);

CREATE INDEX idx_teacher_profiles_org_id ON teacher_profiles(organization_id);

-- -----------------------------------------------------------------------------
-- 7. Batches (Classes / Cohorts)
-- -----------------------------------------------------------------------------
CREATE TABLE batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT NULL,
    -- Online & offline modes supported (Decision Q17)
    mode VARCHAR(50) NOT NULL DEFAULT 'offline' CHECK (mode IN ('offline', 'online', 'hybrid')),
    location VARCHAR(255) NULL,
    meeting_link TEXT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    max_capacity INT NULL CHECK (max_capacity IS NULL OR max_capacity > 0),
    status VARCHAR(50) NOT NULL DEFAULT 'upcoming' CHECK (status IN ('upcoming', 'active', 'completed', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT uq_batches_org_slug UNIQUE (organization_id, slug)
);

CREATE INDEX idx_batches_org_id ON batches(organization_id);
CREATE INDEX idx_batches_org_status ON batches(organization_id, status);

-- -----------------------------------------------------------------------------
-- 8. Batch Memberships (Student Batch Enrollment with Transfer History)
-- -----------------------------------------------------------------------------
CREATE TABLE batch_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'transferred', 'dropped')),
    -- Destination batch reference for transfers (Decision Q4)
    transferred_to_batch_id UUID NULL REFERENCES batches(id) ON DELETE SET NULL,
    transferred_at TIMESTAMPTZ NULL,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_batch_memberships_org_batch_student UNIQUE (organization_id, batch_id, student_id)
);

CREATE INDEX idx_batch_memberships_org_batch ON batch_memberships(organization_id, batch_id);
CREATE INDEX idx_batch_memberships_student ON batch_memberships(organization_id, student_id);

-- -----------------------------------------------------------------------------
-- 9. Batch Teacher Assignments (Teachers Assigned to Batches)
-- -----------------------------------------------------------------------------
CREATE TABLE batch_teacher_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assignment_role VARCHAR(50) NOT NULL DEFAULT 'primary' CHECK (assignment_role IN ('primary', 'assistant', 'substitute')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_batch_teacher_assignments UNIQUE (organization_id, batch_id, teacher_id)
);

CREATE INDEX idx_batch_teacher_assignments_batch ON batch_teacher_assignments(organization_id, batch_id);
CREATE INDEX idx_batch_teacher_assignments_teacher ON batch_teacher_assignments(organization_id, teacher_id);

-- -----------------------------------------------------------------------------
-- 10. Attendance (Idempotent Daily Attendance Records)
-- -----------------------------------------------------------------------------
CREATE TABLE attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    attendance_date DATE NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('present', 'absent', 'late', 'excused')),
    remarks TEXT NULL,
    marked_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    corrected_at TIMESTAMPTZ NULL, -- Attendance backdating/correction support (Decision Q5)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Guarantees exactly one attendance record per student per batch per date (Idempotent upserts)
    CONSTRAINT uq_attendance_idempotent UNIQUE (organization_id, batch_id, student_id, attendance_date)
);

CREATE INDEX idx_attendance_org_batch_date ON attendance(organization_id, batch_id, attendance_date);
CREATE INDEX idx_attendance_student ON attendance(organization_id, student_id);

-- -----------------------------------------------------------------------------
-- 11. Assignments (Assignment Header and Lifecycle)
-- -----------------------------------------------------------------------------
CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    current_version INT NOT NULL DEFAULT 1,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    max_score NUMERIC(6, 2) NOT NULL CHECK (max_score > 0),
    due_date TIMESTAMPTZ NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'closed', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    updated_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    deleted_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_assignments_org_batch ON assignments(organization_id, batch_id);
CREATE INDEX idx_assignments_org_status ON assignments(organization_id, status);
CREATE INDEX idx_assignments_due_date ON assignments(organization_id, due_date);

-- -----------------------------------------------------------------------------
-- 12. Assignment Versions (Immutable Version Snapshots)
-- -----------------------------------------------------------------------------
-- Edits create a new version snapshot. Prior submissions preserve the version
-- they were submitted against (Decision Q7).
CREATE TABLE assignment_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    max_score NUMERIC(6, 2) NOT NULL CHECK (max_score > 0),
    due_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT uq_assignment_versions UNIQUE (assignment_id, version_number)
);

CREATE INDEX idx_assignment_versions_assignment ON assignment_versions(assignment_id);

-- -----------------------------------------------------------------------------
-- 13. Assignment Submissions (Trustworthy Submission & Grading History)
-- -----------------------------------------------------------------------------
CREATE TABLE assignment_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE RESTRICT,
    assignment_version_id UUID NOT NULL REFERENCES assignment_versions(id) ON DELETE RESTRICT,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    submission_number INT NOT NULL DEFAULT 1,
    file_id UUID NULL REFERENCES files(id) ON DELETE RESTRICT,
    content_text TEXT NULL,
    score NUMERIC(6, 2) NULL CHECK (score IS NULL OR score >= 0),
    feedback TEXT NULL,
    -- Only teachers can grade submissions (Decision Q8)
    graded_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    graded_at TIMESTAMPTZ NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'graded', 'returned', 'resubmitted')),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_assignment_submissions UNIQUE (organization_id, assignment_id, student_id, submission_number)
);

CREATE INDEX idx_submissions_org_assignment ON assignment_submissions(organization_id, assignment_id);
CREATE INDEX idx_submissions_student ON assignment_submissions(organization_id, student_id);

-- -----------------------------------------------------------------------------
-- 14. Coding Tasks (Optional Coding Assignment Extension)
-- -----------------------------------------------------------------------------
CREATE TABLE coding_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    language VARCHAR(50) NOT NULL,
    starter_code TEXT NOT NULL,
    solution_template TEXT NULL,
    test_cases JSONB NOT NULL DEFAULT '[]'::jsonb,
    memory_limit_mb INT NOT NULL DEFAULT 128 CHECK (memory_limit_mb > 0),
    timeout_seconds INT NOT NULL DEFAULT 5 CHECK (timeout_seconds > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_coding_tasks_assignment UNIQUE (organization_id, assignment_id)
);

CREATE INDEX idx_coding_tasks_assignment ON coding_tasks(organization_id, assignment_id);

-- -----------------------------------------------------------------------------
-- 15. Announcements
-- -----------------------------------------------------------------------------
CREATE TABLE announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    batch_id UUID NULL REFERENCES batches(id) ON DELETE CASCADE, -- NULL = organization-wide
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    published_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(50) NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'published', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_announcements_org_batch ON announcements(organization_id, batch_id);
CREATE INDEX idx_announcements_status ON announcements(organization_id, status);

-- -----------------------------------------------------------------------------
-- 16. Notifications (In-App Notifications)
-- -----------------------------------------------------------------------------
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    -- Priority on progress notifications per Decision Q10
    type VARCHAR(50) NOT NULL CHECK (type IN ('progress', 'assignment', 'attendance', 'announcement', 'system')),
    read_at TIMESTAMPTZ NULL,
    action_url VARCHAR(500) NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user_all ON notifications(organization_id, user_id, created_at DESC);
-- Partial index for fast query of unread notifications
CREATE INDEX idx_notifications_user_unread ON notifications(user_id) WHERE read_at IS NULL;

-- -----------------------------------------------------------------------------
-- 17. Audit Logs (Global Append-Only Security Ledger)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID NOT NULL,
    actor_role VARCHAR(50) NOT NULL,
    organization_id UUID NULL REFERENCES organizations(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_org_created ON audit_logs(organization_id, created_at DESC);
CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);


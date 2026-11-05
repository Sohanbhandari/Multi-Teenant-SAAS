"""initial multi tenant schema

Revision ID: 20261105_000001
Revises: 
Create Date: 2026-11-05 14:30:00.000000

MANDATORY ARCHITECTURE REMINDERS:
- If this migration creates a tenant-owned table, verify it includes:
    * id (UUID PK)
    * organization_id (UUID FK NOT NULL, indexed)
    * created_at (TIMESTAMPTZ NOT NULL DEFAULT now())
    * updated_at (TIMESTAMPTZ NOT NULL DEFAULT now())
    * created_by (UUID FK -> users.id)
    * updated_by (UUID FK -> users.id)
    * status (VARCHAR(50) NOT NULL DEFAULT 'active', indexed)
- Tenant uniqueness must be composite: UniqueConstraint('organization_id', 'slug', ...)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261105_000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'suspended', 'archived')", name="chk_organizations_status"),
    )
    op.create_index("idx_organizations_slug", "organizations", ["slug"])
    op.create_index("idx_organizations_code", "organizations", ["code"])
    op.create_index("idx_organizations_status", "organizations", ["status"])

    # 2. files (pre-created for user avatar reference)
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("storage_bucket", sa.String(100), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'archived', 'deleted')", name="chk_files_status"),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 4194304", name="chk_files_max_size_4mb"),
        sa.UniqueConstraint("organization_id", "storage_bucket", "storage_path", name="uq_files_org_path"),
    )
    op.create_index("idx_files_org_id", "files", ["organization_id"])
    op.create_index("idx_files_status", "files", ["organization_id", "status"])

    # 3. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("avatar_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'teacher', 'student')", name="chk_users_role"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'suspended', 'deleted')", name="chk_users_status"),
        sa.UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
    )
    op.create_index("idx_users_org_id", "users", ["organization_id"])
    op.create_index("idx_users_org_role", "users", ["organization_id", "role"])
    op.create_index("idx_users_org_status", "users", ["organization_id", "status"])

    # Add deferred FK on files.uploaded_by -> users.id
    op.create_foreign_key("fk_files_uploaded_by", "files", "users", ["uploaded_by"], ["id"], ondelete="SET NULL")
    op.create_index("idx_files_uploaded_by", "files", ["uploaded_by"])

    # 4. organization_memberships
    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("joined_via", sa.String(50), server_default="code", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'teacher', 'student')", name="chk_memberships_role"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'suspended', 'left', 'transferred')", name="chk_memberships_status"),
        sa.CheckConstraint("joined_via IN ('code', 'admin_invite', 'system')", name="chk_memberships_joined_via"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
    )
    op.create_index("idx_org_memberships_org_user", "organization_memberships", ["organization_id", "user_id"])
    op.create_index("idx_org_memberships_user", "organization_memberships", ["user_id"])

    # 5. student_profiles
    op.create_table(
        "student_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_number", sa.String(100), nullable=True),
        sa.Column("guardian_name", sa.String(200), nullable=True),
        sa.Column("guardian_contact", sa.String(100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive', 'graduated', 'suspended')", name="chk_student_profiles_status"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_student_profiles_org_user"),
        sa.UniqueConstraint("organization_id", "enrollment_number", name="uq_student_profiles_org_enrollment"),
    )
    op.create_index("idx_student_profiles_org_id", "student_profiles", ["organization_id"])

    # 6. teacher_profiles
    op.create_table(
        "teacher_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(100), nullable=True),
        sa.Column("specialization", sa.String(255), nullable=True),
        sa.Column("qualification", sa.String(255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive', 'on_leave', 'terminated')", name="chk_teacher_profiles_status"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_teacher_profiles_org_user"),
        sa.UniqueConstraint("organization_id", "employee_id", name="uq_teacher_profiles_org_employee"),
    )
    op.create_index("idx_teacher_profiles_org_id", "teacher_profiles", ["organization_id"])

    # 7. batches
    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(50), server_default="offline", nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("meeting_link", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("max_capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), server_default="upcoming", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("mode IN ('offline', 'online', 'hybrid')", name="chk_batches_mode"),
        sa.CheckConstraint("max_capacity IS NULL OR max_capacity > 0", name="chk_batches_max_capacity"),
        sa.CheckConstraint("status IN ('upcoming', 'active', 'completed', 'archived')", name="chk_batches_status"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_batches_org_slug"),
    )
    op.create_index("idx_batches_org_id", "batches", ["organization_id"])
    op.create_index("idx_batches_org_status", "batches", ["organization_id", "status"])

    # 8. batch_memberships
    op.create_table(
        "batch_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("transferred_to_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("status IN ('active', 'completed', 'transferred', 'dropped')", name="chk_batch_memberships_status"),
        sa.UniqueConstraint("organization_id", "batch_id", "student_id", name="uq_batch_memberships_org_batch_student"),
    )
    op.create_index("idx_batch_memberships_org_batch", "batch_memberships", ["organization_id", "batch_id"])
    op.create_index("idx_batch_memberships_student", "batch_memberships", ["organization_id", "student_id"])

    # 9. batch_teacher_assignments
    op.create_table(
        "batch_teacher_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignment_role", sa.String(50), server_default="primary", nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("assignment_role IN ('primary', 'assistant', 'substitute')", name="chk_batch_teacher_role"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="chk_batch_teacher_status"),
        sa.UniqueConstraint("organization_id", "batch_id", "teacher_id", name="uq_batch_teacher_assignments"),
    )
    op.create_index("idx_batch_teacher_assignments_batch", "batch_teacher_assignments", ["organization_id", "batch_id"])
    op.create_index("idx_batch_teacher_assignments_teacher", "batch_teacher_assignments", ["organization_id", "teacher_id"])

    # 10. attendance
    op.create_table(
        "attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("marked_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('present', 'absent', 'late', 'excused')", name="chk_attendance_status"),
        sa.UniqueConstraint("organization_id", "batch_id", "student_id", "attendance_date", name="uq_attendance_idempotent"),
    )
    op.create_index("idx_attendance_org_batch_date", "attendance", ["organization_id", "batch_id", "attendance_date"])
    op.create_index("idx_attendance_student", "attendance", ["organization_id", "student_id"])

    # 11. assignments
    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(50), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("max_score > 0", name="chk_assignments_max_score"),
        sa.CheckConstraint("status IN ('draft', 'published', 'closed', 'archived')", name="chk_assignments_status"),
    )
    op.create_index("idx_assignments_org_batch", "assignments", ["organization_id", "batch_id"])
    op.create_index("idx_assignments_org_status", "assignments", ["organization_id", "status"])
    op.create_index("idx_assignments_due_date", "assignments", ["organization_id", "due_date"])

    # 12. assignment_versions
    op.create_table(
        "assignment_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("max_score > 0", name="chk_assignment_versions_max_score"),
        sa.UniqueConstraint("assignment_id", "version_number", name="uq_assignment_versions"),
    )
    op.create_index("idx_assignment_versions_assignment", "assignment_versions", ["assignment_id"])

    # 13. assignment_submissions
    op.create_table(
        "assignment_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignment_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignment_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submission_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("graded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="submitted", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("score IS NULL OR score >= 0", name="chk_submissions_score"),
        sa.CheckConstraint("status IN ('submitted', 'graded', 'returned', 'resubmitted')", name="chk_submissions_status"),
        sa.UniqueConstraint("organization_id", "assignment_id", "student_id", "submission_number", name="uq_assignment_submissions"),
    )
    op.create_index("idx_submissions_org_assignment", "assignment_submissions", ["organization_id", "assignment_id"])
    op.create_index("idx_submissions_student", "assignment_submissions", ["organization_id", "student_id"])

    # 14. coding_tasks
    op.create_table(
        "coding_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("starter_code", sa.Text(), nullable=False),
        sa.Column("solution_template", sa.Text(), nullable=True),
        sa.Column("test_cases", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("memory_limit_mb", sa.Integer(), server_default="128", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="5", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("memory_limit_mb > 0", name="chk_coding_tasks_memory"),
        sa.CheckConstraint("timeout_seconds > 0", name="chk_coding_tasks_timeout"),
        sa.UniqueConstraint("organization_id", "assignment_id", name="uq_coding_tasks_assignment"),
    )
    op.create_index("idx_coding_tasks_assignment", "coding_tasks", ["organization_id", "assignment_id"])

    # 15. announcements
    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(50), server_default="published", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="chk_announcements_status"),
    )
    op.create_index("idx_announcements_org_batch", "announcements", ["organization_id", "batch_id"])
    op.create_index("idx_announcements_status", "announcements", ["organization_id", "status"])

    # 16. notifications
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('progress', 'assignment', 'attendance', 'announcement', 'system')", name="chk_notifications_type"),
    )
    op.create_index("idx_notifications_user_all", "notifications", ["organization_id", "user_id", sa.text("created_at DESC")])
    op.create_index("idx_notifications_user_unread", "notifications", ["user_id"], postgresql_where=sa.text("read_at IS NULL"))

    # 17. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", sa.String(50), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_logs_org_created", "audit_logs", ["organization_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("announcements")
    op.drop_table("coding_tasks")
    op.drop_table("assignment_submissions")
    op.drop_table("assignment_versions")
    op.drop_table("assignments")
    op.drop_table("attendance")
    op.drop_table("batch_teacher_assignments")
    op.drop_table("batch_memberships")
    op.drop_table("batches")
    op.drop_table("teacher_profiles")
    op.drop_table("student_profiles")
    op.drop_table("organization_memberships")
    op.drop_constraint("fk_files_uploaded_by", "files", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("files")
    op.drop_table("organizations")


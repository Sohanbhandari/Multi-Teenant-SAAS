"""
Assignment Submission and Coding Task ORM models.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("organization_id", "assignment_id", "student_id", "submission_number", name="uq_assignment_submissions"),
        CheckConstraint("score IS NULL OR score >= 0", name="chk_submissions_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assignments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignment_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assignment_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    submission_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="RESTRICT"),
        nullable=True,
    )
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="submitted")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CodingTask(Base):
    __tablename__ = "coding_tasks"
    __table_args__ = (
        UniqueConstraint("organization_id", "assignment_id", name="uq_coding_tasks_assignment"),
        CheckConstraint("memory_limit_mb > 0", name="chk_coding_tasks_memory"),
        CheckConstraint("timeout_seconds > 0", name="chk_coding_tasks_timeout"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    starter_code: Mapped[str] = mapped_column(Text, nullable=False)
    solution_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_cases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=128)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


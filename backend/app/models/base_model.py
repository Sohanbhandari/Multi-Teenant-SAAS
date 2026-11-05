"""
Tenant Audit Mixin for all tenant-owned SQLAlchemy models.

Per docs/architecture/multi-tenancy.md, EVERY tenant-owned table MUST include:
- id (UUID PK)
- organization_id (UUID FK, indexed, NOT NULL)
- created_at (TIMESTAMPTZ, server_default=now())
- updated_at (TIMESTAMPTZ, server_default=now(), onupdate=now())
- created_by (UUID FK → users.id, nullable=True for initial bootstrap)
- updated_by (UUID FK → users.id, nullable=True for initial bootstrap)
- status (VARCHAR(50), default='active', indexed)
"""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class TenantAuditMixin:
    """
    Mandatory mixin for all tenant-scoped database entities.
    Enforces audit columns and row-level tenant identification.
    """
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
    )


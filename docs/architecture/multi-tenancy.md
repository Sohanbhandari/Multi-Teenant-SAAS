# Multi-Tenancy Architecture

**Project:** Multi-Tenant Learning & Coaching Management SaaS  
**Version:** 1.0  
**Date:** 2026-11-03

---

## Table of Contents

1. [Chosen Model](#1-chosen-model)
2. [How Tenant Context Is Resolved](#2-how-tenant-context-is-resolved)
3. [Tenant Middleware Pattern in FastAPI](#3-tenant-middleware-pattern-in-fastapi)
4. [Mandatory Fields on Tenant-Owned Tables](#4-mandatory-fields-on-tenant-owned-tables)
5. [Query Scoping Pattern](#5-query-scoping-pattern)
6. [Tenant-Aware Uniqueness Constraints](#6-tenant-aware-uniqueness-constraints)
7. [Tables That Are NOT Tenant-Scoped](#7-tables-that-are-not-tenant-scoped)
8. [Cross-Tenant Access Prevention](#8-cross-tenant-access-prevention)
9. [Future Row-Level Security (RLS) Consideration](#9-future-row-level-security-rls-consideration)
10. [Test Strategy for Tenant Isolation](#10-test-strategy-for-tenant-isolation)

---

## 1. Chosen Model

**Model:** Shared Database, Shared Schema, Row-Level Tenant Isolation via `organization_id`

Every tenant's data lives in the same PostgreSQL database and the same tables as every other tenant's data. Tenants are separated **at the row level** by the `organization_id` column that appears on every tenant-owned table.

### Why this model?

| Criterion | Decision |
|---|---|
| **Operational simplicity** | One database to manage, back up, and migrate |
| **Cost efficiency** | No per-tenant database provisioning |
| **Scale target** | Suitable for hundreds to low thousands of tenants |
| **Isolation guarantee** | Application-enforced (strong if implemented correctly) |
| **Migration complexity** | Single Alembic migration applies to all tenants |

### What this means for developers

Every single query that touches a tenant-owned table **must** include a `WHERE organization_id = ?` clause. This is not a suggestion — it is a **security requirement**. Missing this filter would allow a user from Organization A to read or modify Organization B's data. This is classified as a **critical security vulnerability**.

---

## 2. How Tenant Context Is Resolved

**The tenant context (`organization_id`) is always resolved from the verified JWT token. It is never accepted from the client.**

The flow is:

```
1. Client sends HTTP request with access_token in httpOnly cookie
2. FastAPI auth dependency decodes and verifies the JWT
3. JWT payload contains { "sub": "<user_id>", "org_id": "<uuid>", "role": "teacher", "jti": "..." }
4. The org_id from the JWT is used as the tenant context for ALL queries in this request
5. The client CANNOT override this by sending a different org_id in the request body, query string, or headers
```

### Why not accept org_id from the client?

Because the client cannot be trusted. If we accepted `org_id` from the request, a malicious user could simply change the `org_id` in their request and read data from a different organization. The JWT is signed by the server and cannot be tampered with — it is the only trustworthy source of tenant context.

### What the JWT payload contains

```json
{
  "sub": "user-uuid-here",
  "org_id": "org-uuid-here",
  "role": "teacher",
  "jti": "unique-token-id-for-revocation",
  "iat": 1700000000,
  "exp": 1700000900
}
```

---

## 3. Tenant Middleware Pattern in FastAPI

Tenant context is injected into route handlers using FastAPI's dependency injection system.

### The Tenant Dependency

```python
# backend/app/dependencies/tenant.py

from uuid import UUID
from fastapi import Depends, HTTPException, status
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.organization_repo import OrganizationRepository
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """
    Resolves the tenant (Organization) from the current user's JWT.
    
    The org_id is embedded in the JWT by the auth service at login time.
    It is NEVER read from the request body or query params.
    
    Raises HTTP 403 if the organization is not found or is inactive.
    """
    org_repo = OrganizationRepository(db)
    org = await org_repo.get_by_id(current_user.organization_id)
    
    if not org or org.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization not found or inactive."
        )
    
    return org
```

### Using the Tenant Dependency in a Route

```python
# backend/app/api/v1/courses.py

from fastapi import APIRouter, Depends
from app.dependencies.tenant import get_current_tenant
from app.dependencies.rbac import require_role
from app.models.organization import Organization
from app.schemas.course import CourseResponse
from app.services.course_service import CourseService

router = APIRouter()


@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(
    tenant: Organization = Depends(get_current_tenant),
    _: None = Depends(require_role("admin", "teacher", "student")),
    service: CourseService = Depends(get_course_service),
):
    """
    Lists all courses for the current tenant.
    The tenant.id (organization_id) is passed to the service,
    which passes it to the repository for query scoping.
    """
    return await service.list_courses(org_id=tenant.id)
```

---

## 4. Mandatory Fields on Tenant-Owned Tables

Every table that stores tenant-owned data **must** have the following columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `UUID` PRIMARY KEY | Externally exposed identifier (never expose integer PKs) |
| `organization_id` | `UUID` NOT NULL FK → `organizations.id` | Tenant isolation key — indexed, never nullable |
| `created_at` | `TIMESTAMPTZ` NOT NULL DEFAULT now() | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` NOT NULL DEFAULT now() | Last modification timestamp (auto-updated via trigger or ORM event) |
| `created_by` | `UUID` NOT NULL FK → `users.id` | Who created this record |
| `updated_by` | `UUID` NOT NULL FK → `users.id` | Who last modified this record |
| `status` | `VARCHAR` or `deleted_at TIMESTAMPTZ` | Soft delete — never hard delete tenant data |

### Base Model Mixin (SQLAlchemy)

```python
# backend/app/models/base_model.py

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class Base(DeclarativeBase):
    pass


class TenantAuditMixin:
    """
    Mixin for all tenant-owned tables.
    
    Apply this to every SQLAlchemy model that stores tenant data.
    Do not skip any of these columns — they are required by architecture.
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
        index=True,  # Always index this — it is in every WHERE clause
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
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
    )
```

---

## 5. Query Scoping Pattern

**Every repository method that queries a tenant-owned table MUST receive and use `org_id`.**

### Correct Pattern

```python
# backend/app/repositories/course_repo.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.course import Course


class CourseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_org(self, org_id: UUID) -> list[Course]:
        """
        Returns all active courses for the given organization.
        
        The WHERE organization_id = :org_id clause is MANDATORY.
        Without it, this would return courses from ALL organizations.
        """
        stmt = (
            select(Course)
            .where(Course.organization_id == org_id)  # NEVER SKIP THIS
            .where(Course.status == "active")
            .order_by(Course.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_id_and_org(self, course_id: UUID, org_id: UUID) -> Course | None:
        """
        Gets a specific course, scoped to the organization.
        
        If the course exists but belongs to a different org, this returns None.
        The caller gets a 404 — not a 403 — to avoid leaking that the resource exists.
        """
        stmt = (
            select(Course)
            .where(Course.id == course_id)
            .where(Course.organization_id == org_id)  # NEVER SKIP THIS
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

### What NEVER to do

```python
# WRONG — no tenant scope. Returns courses from ALL organizations.
async def list_all_courses(self) -> list[Course]:
    stmt = select(Course)  # CRITICAL SECURITY BUG
    result = await self.db.execute(stmt)
    return result.scalars().all()

# WRONG — accepting org_id from user input
async def list_courses(self, org_id_from_request: str):
    # org_id must come from the verified JWT, not from the request
    stmt = select(Course).where(Course.organization_id == org_id_from_request)
    ...
```

---

## 6. Tenant-Aware Uniqueness Constraints

Some fields must be unique **within** a tenant, but can be duplicated across tenants. For example, a course title of "Introduction to Python" can exist in multiple organizations — it just can't appear twice within the same organization.

### Pattern: Composite Unique Constraint

```python
# In the SQLAlchemy model
from sqlalchemy import UniqueConstraint

class Course(Base, TenantAuditMixin):
    __tablename__ = "courses"
    __table_args__ = (
        # Course slug must be unique within an organization, not globally
        UniqueConstraint("organization_id", "slug", name="uq_courses_org_slug"),
    )
    
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    ...
```

### Pattern: User email uniqueness

User email must be unique within an organization (same email can exist in different orgs):

```python
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
    )
```

---

## 7. Tables That Are NOT Tenant-Scoped

Some tables store global (cross-tenant) data. These tables do **not** have a mandatory `organization_id` column, but some may store it as an optional reference for context.

| Table | Reason for Global Scope |
|---|---|
| `organizations` | Organizations ARE tenants; they are the root scope |
| `audit_logs` | Must be globally accessible for security investigations. An org admin cannot see logs for other orgs, but the system/superadmin can. |
| `system_settings` | Platform-level configuration, not per-tenant |

### Audit Logs Design

The `audit_logs` table stores `organization_id` as an optional foreign key (for filtering), but it is **not** the tenant isolation key. The audit log is a global, append-only ledger. This allows platform administrators to investigate cross-tenant security incidents without being blocked by tenant isolation.

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID NOT NULL,          -- user who performed the action
    actor_role VARCHAR(50) NOT NULL,  -- their role at time of action
    organization_id UUID,             -- nullable: some system events have no org
    action VARCHAR(255) NOT NULL,     -- e.g., "user.login", "course.publish"
    resource_type VARCHAR(100),       -- e.g., "course", "user"
    resource_id UUID,                 -- the affected resource's ID
    metadata JSONB,                   -- additional context (IP, user agent, etc.)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 8. Cross-Tenant Access Prevention Strategy

The strategy is **defense in depth** — multiple independent layers each prevent cross-tenant data access:

### Layer 1: JWT-sourced org_id (Primary)
The `org_id` always comes from the server-signed JWT. A user cannot change their own `org_id` because they cannot forge a JWT signature.

### Layer 2: Tenant Dependency Check (Secondary)
The `get_current_tenant` dependency verifies that the `org_id` in the JWT maps to an active organization in the database. If an org is deactivated, all its users immediately lose access.

### Layer 3: Repository-Level Scoping (Tertiary)
Every repository method for tenant-owned data includes `WHERE organization_id = ?`. Even if Layers 1 and 2 somehow passed an incorrect `org_id`, this layer would prevent the wrong data from being returned.

### Layer 4: Response Serialization Omits Sensitive Fields
Pydantic response schemas never include `organization_id` in API responses to clients. This reduces the risk of information leakage.

### Layer 5: Negative Tests (Verification)
The test suite includes **mandatory negative tests** that verify cross-tenant access is impossible. See Section 10.

---

## 9. Future Row-Level Security (RLS) Consideration

PostgreSQL supports Row Level Security (RLS) — policies defined at the database level that restrict which rows a database user can see. This provides an **additional** layer of tenant isolation that operates even if the application-layer scoping is accidentally bypassed.

**Current decision:** RLS is **not** implemented in Phase 1. Reasons:

1. Application-level scoping is sufficient for the current scale and team.
2. RLS adds complexity to Alembic migrations and SQLAlchemy session management.
3. RLS makes debugging harder — a missing row might look like a bug when it's actually an RLS policy.
4. RLS requires a separate PostgreSQL role per tenant or a session variable approach, both of which add operational complexity.

**Future consideration:** If the platform grows to require stronger database-level isolation guarantees (e.g., for compliance reasons), RLS can be added as an additional layer. This should be captured in a new ADR when the decision is made.

---

## 10. Test Strategy for Tenant Isolation

Tenant isolation **must** be verified by automated tests. The following test patterns are required. Negative tests — tests that verify access is *denied* — are just as important as positive tests.

### Required Negative Tests

```python
# backend/tests/integration/test_tenant_isolation.py

import pytest

@pytest.mark.asyncio
async def test_user_cannot_access_other_org_course(
    client,
    org_a_teacher_token,  # JWT for a teacher in Organization A
    org_b_course_id,       # A course that belongs to Organization B
):
    """
    A user from Org A must not be able to read Org B's course.
    Expected: 404 (not 403 — do not leak that the resource exists).
    """
    response = await client.get(
        f"/api/v1/courses/{org_b_course_id}",
        cookies={"access_token": org_a_teacher_token},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_update_other_org_course(
    client,
    org_a_admin_token,
    org_b_course_id,
):
    """
    An Admin from Org A must not be able to update Org B's course.
    Even though Admins have full privileges within their org, those
    privileges do not extend across org boundaries.
    """
    response = await client.put(
        f"/api/v1/courses/{org_b_course_id}",
        json={"title": "Injected Title"},
        cookies={"access_token": org_a_admin_token},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_org_id_in_request_body_is_ignored(
    client,
    org_a_admin_token,
    org_b_id,
):
    """
    Sending org_id in the request body must have no effect.
    The API should use the org_id from the JWT, not from the body.
    The created course must belong to Org A, not Org B.
    """
    response = await client.post(
        "/api/v1/courses",
        json={
            "title": "Test Course",
            "organization_id": str(org_b_id),  # Attempting to inject Org B's ID
        },
        cookies={"access_token": org_a_admin_token},
    )
    assert response.status_code == 201
    created_course = response.json()
    # The course must be in Org A despite the body specifying Org B
    assert created_course["organization_id"] != str(org_b_id)
```

### Test Fixture Pattern

```python
# backend/tests/conftest.py

@pytest.fixture
async def org_a(db) -> Organization:
    """Creates Organization A for isolation tests."""
    ...

@pytest.fixture
async def org_b(db) -> Organization:
    """Creates Organization B — a completely separate tenant."""
    ...

@pytest.fixture
async def org_a_teacher_token(org_a, db) -> str:
    """Returns a JWT for a teacher in Organization A."""
    ...

@pytest.fixture
async def org_b_course_id(org_b, db) -> UUID:
    """Creates a course in Organization B and returns its ID."""
    ...
```

Every new resource type added to the system must have corresponding cross-tenant isolation tests before that feature phase is marked Done.


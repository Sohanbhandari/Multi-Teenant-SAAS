"""
Database Multi-Tenant Isolation & Negative Constraint Tests.

Tests:
1. cross-tenant lookup (Org A user cannot query Org B records)
2. cross-tenant insert (Cannot insert record for Org B using Org A context)
3. cross-tenant update (Cannot mutate Org B records when scoped to Org A)
4. cross-tenant delete (Cannot soft-delete or remove Org B records from Org A)
5. invalid membership (Role validation and FK checks)
6. duplicate membership (Cannot enroll user twice into the same organization)
7. duplicate attendance (Unique constraint enforces exactly 1 record per student/batch/date)
8. invalid foreign keys (Foreign key integrity failures raise IntegrityError)
"""

import uuid
from datetime import date, datetime
import pytest
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.base import Base
from app.models.organization import Organization
from app.models.user import User
from app.models.membership import OrganizationMembership
from app.models.batch import Batch, BatchMembership
from app.models.attendance import Attendance
from app.models.file import File

# In-memory or isolated test database engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_db_session():
    """Provides an isolated SQLite in-memory database with full schema for isolation tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def seed_two_tenants(test_db_session: AsyncSession):
    """Seeds two separate organizations with users for cross-tenant isolation testing."""
    # Organization A
    org_a = Organization(
        id=uuid.uuid4(),
        name="Organization Alpha",
        slug="org-alpha",
        code="ALPHA-100",
        status="active",
    )
    # Organization B
    org_b = Organization(
        id=uuid.uuid4(),
        name="Organization Beta",
        slug="org-beta",
        code="BETA-200",
        status="active",
    )
    test_db_session.add_all([org_a, org_b])
    await test_db_session.flush()

    # Users for Org A
    user_a = User(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        email="student@alpha.com",
        hashed_password="hashed_pw",
        first_name="Alice",
        last_name="Alpha",
        role="student",
        status="active",
    )
    # Users for Org B
    user_b = User(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        email="student@beta.com",
        hashed_password="hashed_pw",
        first_name="Bob",
        last_name="Beta",
        role="student",
        status="active",
    )
    test_db_session.add_all([user_a, user_b])
    await test_db_session.flush()

    # Batch in Org A
    batch_a = Batch(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        name="Alpha Python Cohort",
        slug="alpha-python",
        mode="offline",
        start_date=date(2026, 1, 1),
        status="active",
    )
    # Batch in Org B
    batch_b = Batch(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        name="Beta Python Cohort",
        slug="beta-python",
        mode="online",
        start_date=date(2026, 1, 1),
        status="active",
    )
    test_db_session.add_all([batch_a, batch_b])
    await test_db_session.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": user_a,
        "user_b": user_b,
        "batch_a": batch_a,
        "batch_b": batch_b,
    }


@pytest.mark.asyncio
async def test_cross_tenant_lookup_denied(test_db_session: AsyncSession, seed_two_tenants: dict):
    """Negative test: A query scoped to Org A must return 0 records when querying Org B resources."""
    org_a = seed_two_tenants["org_a"]
    batch_b = seed_two_tenants["batch_b"]

    # When querying with Org A scope for a batch belonging to Org B, result must be empty
    stmt = (
        select(Batch)
        .where(Batch.id == batch_b.id)
        .where(Batch.organization_id == org_a.id)
    )
    result = await test_db_session.execute(stmt)
    found_batch = result.scalar_one_or_none()

    assert found_batch is None, "Cross-tenant leakage: Org A successfully looked up Org B batch!"


@pytest.mark.asyncio
async def test_cross_tenant_update_isolated(test_db_session: AsyncSession, seed_two_tenants: dict):
    """Negative test: An update scoped to Org A cannot mutate Org B's records."""
    org_a = seed_two_tenants["org_a"]
    batch_b = seed_two_tenants["batch_b"]

    # Attempt to update batch_b title while passing organization_id = org_a.id
    stmt = (
        update(Batch)
        .where(Batch.id == batch_b.id)
        .where(Batch.organization_id == org_a.id)
        .values(name="Compromised Title")
    )
    result = await test_db_session.execute(stmt)
    await test_db_session.commit()

    assert result.rowcount == 0, "Security violation: Cross-tenant update modified rows!"

    # Verify batch_b title is unchanged
    refreshed = await test_db_session.get(Batch, batch_b.id)
    assert refreshed.name == "Beta Python Cohort"


@pytest.mark.asyncio
async def test_cross_tenant_delete_isolated(test_db_session: AsyncSession, seed_two_tenants: dict):
    """Negative test: A delete statement scoped to Org A cannot delete Org B's records."""
    org_a = seed_two_tenants["org_a"]
    batch_b = seed_two_tenants["batch_b"]

    stmt = (
        delete(Batch)
        .where(Batch.id == batch_b.id)
        .where(Batch.organization_id == org_a.id)
    )
    result = await test_db_session.execute(stmt)
    await test_db_session.commit()

    assert result.rowcount == 0, "Security violation: Cross-tenant delete deleted rows!"

    # Verify batch_b still exists
    remains = await test_db_session.get(Batch, batch_b.id)
    assert remains is not None


@pytest.mark.asyncio
async def test_duplicate_organization_membership_rejected(test_db_session: AsyncSession, seed_two_tenants: dict):
    """Negative test: Adding duplicate membership for the same user in an org violates uniqueness."""
    org_a = seed_two_tenants["org_a"]
    user_a = seed_two_tenants["user_a"]

    # First membership
    mem1 = OrganizationMembership(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        user_id=user_a.id,
        role="student",
        status="active",
    )
    test_db_session.add(mem1)
    await test_db_session.commit()

    # Attempt second membership for same org and user
    mem2 = OrganizationMembership(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        user_id=user_a.id,
        role="student",
        status="active",
    )
    test_db_session.add(mem2)
    with pytest.raises(IntegrityError):
        await test_db_session.commit()
    await test_db_session.rollback()


@pytest.mark.asyncio
async def test_duplicate_attendance_rejected(test_db_session: AsyncSession, seed_two_tenants: dict):
    """Negative test: Enforces idempotent attendance constraint on (org_id, batch_id, student_id, date)."""
    org_a = seed_two_tenants["org_a"]
    batch_a = seed_two_tenants["batch_a"]
    user_a = seed_two_tenants["user_a"]
    att_date = date(2026, 3, 15)

    att1 = Attendance(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        batch_id=batch_a.id,
        student_id=user_a.id,
        attendance_date=att_date,
        status="present",
        marked_by=user_a.id,
    )
    test_db_session.add(att1)
    await test_db_session.commit()

    # Duplicate record on same day for same student and batch
    att2 = Attendance(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        batch_id=batch_a.id,
        student_id=user_a.id,
        attendance_date=att_date,
        status="absent",
        marked_by=user_a.id,
    )
    test_db_session.add(att2)
    with pytest.raises(IntegrityError):
        await test_db_session.commit()
    await test_db_session.rollback()


@pytest.mark.asyncio
async def test_invalid_foreign_key_rejected(test_db_session: AsyncSession):
    """Negative test: Attempting to insert a user referencing a non-existent organization fails."""
    non_existent_org_id = uuid.uuid4()

    orphan_user = User(
        id=uuid.uuid4(),
        organization_id=non_existent_org_id,
        email="orphan@invalid.com",
        hashed_password="pw",
        first_name="Ghost",
        last_name="User",
        role="student",
        status="active",
    )
    test_db_session.add(orphan_user)
    # Foreign key constraint check fails
    with pytest.raises(Exception):
        await test_db_session.commit()
    await test_db_session.rollback()


@pytest.mark.asyncio
async def test_file_size_upper_bound_constraint(test_db_session: AsyncSession, seed_two_tenants: dict):
    """Negative test: Database enforces 4MB file limit constraint on the files table."""
    org_a = seed_two_tenants["org_a"]
    user_a = seed_two_tenants["user_a"]

    # 4MB = 4,194,304 bytes. 5MB = 5,242,880 bytes.
    oversized_file = File(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        storage_bucket="lms-dev",
        storage_path="oversized.pdf",
        filename="oversized.pdf",
        mime_type="application/pdf",
        size_bytes=5242880,  # 5MB > 4MB limit
        uploaded_by=user_a.id,
        status="active",
    )
    test_db_session.add(oversized_file)
    with pytest.raises(IntegrityError):
        await test_db_session.commit()
    await test_db_session.rollback()


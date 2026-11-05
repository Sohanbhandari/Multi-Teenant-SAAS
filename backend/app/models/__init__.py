"""
SQLAlchemy ORM models package.

Exports all database models so they are registered with Base.metadata
and available for Alembic migrations and repository queries.
"""

from app.db.base import Base
from app.models.base_model import TenantAuditMixin
from app.models.organization import Organization
from app.models.file import File
from app.models.user import User
from app.models.membership import OrganizationMembership
from app.models.student_profile import StudentProfile
from app.models.teacher_profile import TeacherProfile
from app.models.batch import Batch, BatchMembership, BatchTeacherAssignment
from app.models.attendance import Attendance
from app.models.assignment import Assignment, AssignmentVersion
from app.models.submission import AssignmentSubmission, CodingTask
from app.models.announcement import Announcement
from app.models.notification import Notification
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "TenantAuditMixin",
    "Organization",
    "File",
    "User",
    "OrganizationMembership",
    "StudentProfile",
    "TeacherProfile",
    "Batch",
    "BatchMembership",
    "BatchTeacherAssignment",
    "Attendance",
    "Assignment",
    "AssignmentVersion",
    "AssignmentSubmission",
    "CodingTask",
    "Announcement",
    "Notification",
    "AuditLog",
]

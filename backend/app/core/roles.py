"""
Role enumerations for Role-Based Access Control (RBAC).

Three primary roles exist per the blueprint and architecture docs:
- ADMIN: Full control over tenant organization, courses, settings, and users
- TEACHER: Manage authoring, teaching, grading, sessions within assigned courses
- STUDENT: Read and complete enrolled content, submit assignments
"""

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


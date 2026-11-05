"""
Role-Based Access Control (RBAC) dependency factory.

Phase 0 placeholder.
Enforces Role requirements on protected endpoints in Phase 1.
"""

from app.core.roles import Role


def require_role(*roles: Role):
    """Placeholder dependency factory for Phase 1 role enforcement."""
    async def role_checker():
        return True
    return role_checker


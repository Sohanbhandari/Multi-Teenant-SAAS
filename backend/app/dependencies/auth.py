"""
Authentication dependencies.

Phase 0 placeholder.
Full JWT token extraction from httpOnly cookies and validation are implemented in Phase 1.
"""

from fastapi import HTTPException, status


async def get_current_user():
    """Placeholder dependency for Phase 1 authentication."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication system will be active starting in Phase 1.",
    )


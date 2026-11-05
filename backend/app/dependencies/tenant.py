"""
Tenant isolation dependencies.

Phase 0 placeholder.
Extracts organization_id from the verified JWT in Phase 1.
"""

from fastapi import HTTPException, status


async def get_current_tenant():
    """Placeholder dependency for Phase 1 tenant context resolution."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Tenant resolution will be active starting in Phase 1.",
    )


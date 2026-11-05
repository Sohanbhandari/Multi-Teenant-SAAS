"""Database session dependency re-export."""
from app.db.session import get_db

__all__ = ["get_db"]


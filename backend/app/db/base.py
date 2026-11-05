"""
SQLAlchemy DeclarativeBase setup.

All ORM models must inherit from Base.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root declarative base class for all SQLAlchemy ORM models."""
    pass


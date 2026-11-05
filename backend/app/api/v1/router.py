"""
API version 1 root router.

Aggregates all resource sub-routers into a single APIRouter instance.
Per Phase 0 instructions: no business modules (students, teachers, courses, etc.) are registered yet.
"""

from fastapi import APIRouter
from app.api.v1.health import router as health_router

api_v1_router = APIRouter()

# Register core health router
api_v1_router.include_router(health_router)


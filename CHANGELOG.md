# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [0.1.0] — 2026-11-05 — Foundation & Architecture

### Added

#### Documentation
- `README.md` — project overview, tech stack, quick start, phase plan
- `docs/architecture/system-architecture.md` — full system architecture document
- `docs/architecture/multi-tenancy.md` — multi-tenancy model and query patterns
- `docs/architecture/authentication.md` — JWT auth strategy and token lifecycle
- `docs/architecture/multi-tenant-erd.md` — visual entity-relationship diagram and schema dictionary
- `docs/architecture/data-and-tenant-ownership-matrix.md` — data ownership matrix, index and constraint rationale

#### Infrastructure
- `docker-compose.yml` — PostgreSQL 15 (port 5432) + Redis 7 (port 6379)
- `.env.example` — required environment variable template (with safe placeholders)
- `.gitignore` — Python, Node.js, Supabase, and editor ignore rules
- `CHANGELOG.md` — this release changelog

#### Backend (FastAPI Foundation)
- `backend/app/main.py` — FastAPI application factory with async lifespan management
- `backend/app/core/config.py` — Pydantic BaseSettings; fails fast on missing env vars
- `backend/app/core/exceptions.py` — global exception handlers; standard error envelope
- `backend/app/core/middleware.py` — request ID injection; every request gets a UUID for log correlation
- `backend/app/core/logging.py` — structured logging configuration
- `backend/app/core/security.py` — cryptographic and security utility foundation
- `backend/app/core/roles.py` — Role enum (admin, teacher, student)
- `backend/app/db/base.py` — SQLAlchemy DeclarativeBase
- `backend/app/db/session.py` — async session factory; get_db dependency; connection pool lifecycle
- `backend/app/models/base_model.py` — TenantAuditMixin (7 required columns for all tenant tables)
- `backend/app/schemas/common.py` — ErrorResponse, HealthResponse, PaginatedResponse
- `backend/app/api/v1/health.py` — GET /api/v1/health endpoint
- `backend/app/api/v1/router.py` — v1 router aggregator
- `backend/app/dependencies/db.py` — get_db dependency
- `backend/app/dependencies/auth.py` — authentication dependency stub
- `backend/app/dependencies/tenant.py` — tenant context resolution dependency stub
- `backend/app/dependencies/rbac.py` — role enforcement dependency factory stub
- `backend/alembic/env.py` — async Alembic migration environment
- `backend/alembic/script.py.mako` — migration file template
- `backend/tests/conftest.py` — shared test fixtures and AsyncClient setup
- `backend/tests/integration/test_health.py` — health endpoint integration test
- `backend/pyproject.toml` — ruff, mypy, pytest configuration
- `backend/requirements.txt` — pinned Python dependencies

#### Frontend (Next.js 14 Foundation)
- Next.js 14 App Router + TypeScript strict mode + Tailwind CSS 3.4
- `frontend/app/layout.tsx` — root layout
- `frontend/app/page.tsx` — landing page
- `frontend/app/(public)/login/page.tsx` — login page
- `frontend/app/(public)/register/page.tsx` — register page
- `frontend/app/(auth)/layout.tsx` — authenticated workspace layout shell
- `frontend/app/(auth)/dashboard/page.tsx` — dashboard placeholder
- `frontend/middleware.ts` — edge middleware for auth cookie presence check
- `frontend/components/ui/Button.tsx` — reusable button primitive (4 variants, loading state)
- `frontend/components/ui/Input.tsx` — reusable input primitive (label, error, hint)
- `frontend/components/ui/index.ts` — barrel export
- `frontend/components/shared/ErrorBoundary.tsx` — React class error boundary
- `frontend/components/shared/LoadingSpinner.tsx` — accessible loading spinner
- `frontend/lib/api/client.ts` — API client with credentials support
- `frontend/lib/utils.ts` — cn(), formatBytes()
- `frontend/types/common.ts` — ApiErrorResponse, PaginatedResponse<T>, Role, RecordStatus
- `frontend/styles/globals.css` — Tailwind base + global resets
- `frontend/__tests__/components/ui/Button.test.tsx` — Button unit tests
- Jest + Testing Library + ESLint + Prettier configuration

#### Supabase
- `supabase/config.toml` — local development configuration (4 MB file size limit)
- `supabase/seed.sql` — seed template (clean, no fake data)

#### CI/CD
- `.github/workflows/ci.yml` — backend (lint → type-check → test) + frontend (lint → type-check → build → test)

### Specifications Established
- Modular monolith architecture pattern with shared database and row-level tenant isolation via `organization_id`
- FastAPI-issued JWT authentication in httpOnly cookies (15-min access token, 7-day refresh token)
- Redis token blocklist for refresh token rotation and revocation
- Tenant scoping on all tenant-owned database tables with composite unique constraints
- Idempotent attendance tracking per student/batch/date
- Immutable assignment version snapshots to protect historical submission contexts
- Strict 4MB storage quota enforced at the database level

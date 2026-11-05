# System Architecture

**Project:** Multi-Tenant Learning & Coaching Management SaaS  
**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Phase 0 — Foundational (no application code written yet)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Responsibilities](#2-component-responsibilities)
3. [Request Lifecycle](#3-request-lifecycle)
4. [Layering Rules](#4-layering-rules)
5. [Backend Folder Structure](#5-backend-folder-structure)
6. [Frontend Folder Structure](#6-frontend-folder-structure)
7. [Environment Variables Reference](#7-environment-variables-reference)
8. [External Services](#8-external-services)

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSER                       │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Next.js 14 Frontend (SSR + CSR)          │   │
│  │  - App Router pages and layouts                       │   │
│  │  - React 18 components with Tailwind CSS              │   │
│  │  - Auth context: reads cookies (no JWT parsing)       │   │
│  │  - All API calls go to FastAPI backend                │   │
│  └───────────────────┬──────────────────────────────────┘   │
└──────────────────────┼──────────────────────────────────────┘
                       │ HTTPS (httpOnly cookies for auth)
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend (Python 3.11)              │
│                                                             │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐              │
│  │  Routes  │→ │  Services  │→ │   Repos    │              │
│  │  (thin)  │  │ (business) │  │ (queries)  │              │
│  └──────────┘  └────────────┘  └─────┬──────┘              │
│                                      │                       │
│  ┌───────────────────────────────────▼───────────────────┐  │
│  │              SQLAlchemy 2.0 ORM                        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────────────────┐    │
│  │  Redis 7          │  │  Supabase Storage Client      │    │
│  │  (token blocklist │  │  (file upload/download)       │    │
│  │   + optional cache│  │                               │    │
│  └──────────────────┘  └──────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────┘
                                  │ TCP (asyncpg / psycopg2)
┌─────────────────────────────────▼───────────────────────────┐
│              Supabase (Managed PostgreSQL 15)                │
│                                                             │
│  - Single database, shared by all tenants                    │
│  - Row-level tenant isolation via organization_id            │
│  - Supabase Storage for files (S3-compatible)                │
└─────────────────────────────────────────────────────────────┘
```

**Key architectural principle:** The FastAPI backend is the **single security boundary**. The frontend never makes direct database calls, never directly accesses Supabase (except receiving presigned storage URLs from the backend), and never determines authorization context. Every security decision — authentication, tenant resolution, role authorization — happens in the FastAPI backend.

---

## 2. Component Responsibilities

### Frontend (Next.js 14)

| Responsibility | Owned by Frontend | Notes |
|---|---|---|
| Rendering UI for authenticated users | ✅ | Uses server components where possible |
| Redirecting unauthenticated users | ✅ | Via `middleware.ts` checking cookie presence |
| Calling backend API endpoints | ✅ | All calls include credentials (cookies) |
| Parsing or validating JWT | ❌ | Never. The backend validates tokens. |
| Determining `org_id` or `role` | ❌ | Never. Received from `/auth/me` endpoint only. |
| Storing tokens in localStorage | ❌ | Never. Tokens are in httpOnly cookies. |
| Direct database access | ❌ | Never. |
| Direct Supabase API calls | ❌ | Except using presigned URLs issued by the backend. |

### Backend (FastAPI)

| Responsibility | Notes |
|---|---|
| Validating JWT from httpOnly cookie | Every protected request |
| Resolving tenant context (`org_id`) from JWT | Never from request body |
| Enforcing RBAC per route | Using FastAPI dependency injection |
| All business logic | Services layer only |
| All database queries | Repositories layer only |
| Issuing and revoking tokens | Auth service + Redis blocklist |
| Writing audit logs | Service layer, after sensitive actions |
| Generating presigned storage URLs | Backend issues, frontend uses |

### PostgreSQL (via Supabase)

| Responsibility | Notes |
|---|---|
| Persistent data storage | Source of truth for all application state |
| Row-level tenant isolation | Enforced by application-layer `WHERE organization_id = ?` |
| Schema versioning | Managed by Alembic migrations only |
| NOT responsible for: | RLS (Row Level Security) is not used in Phase 1; may be added later |

### Redis

| Responsibility | Notes |
|---|---|
| Refresh token JTI blocklist | Primary use — required for secure logout |
| Optional query caching | Only when justified by profiling; document in an ADR |

### Supabase Storage

| Responsibility | Notes |
|---|---|
| File storage (S3-compatible) | Course materials, assignment submissions |
| Accessed only via backend | Frontend uses presigned URLs issued by the backend |

---

## 3. Request Lifecycle

Every authenticated, tenant-scoped request goes through these stages in order. Understanding this pipeline is essential for debugging.

```
Browser
  │
  │  1. HTTP Request (with httpOnly cookie containing access_token)
  ▼
FastAPI Middleware Stack
  │
  │  2. CORS Middleware — validates Origin header against FRONTEND_URL
  │
  │  3. Request ID Middleware — attaches a unique correlation ID to every request
  │     (used for log tracing)
  │
  ▼
Route Handler (e.g., GET /courses)
  │
  │  4. Auth Dependency (get_current_user)
  │     - Reads 'access_token' from httpOnly cookie
  │     - Decodes and validates JWT signature and expiry
  │     - Checks JTI against Redis blocklist (prevents revoked token use)
  │     - Returns User object — or raises HTTP 401
  │
  │  5. Tenant Dependency (get_current_tenant)
  │     - Reads organization_id from the verified JWT payload
  │     - Returns the Organization object from DB — or raises HTTP 403
  │     - NEVER reads org_id from request body, query params, or headers
  │
  │  6. RBAC Dependency (require_role("admin", "teacher"))
  │     - Reads role from the verified JWT payload
  │     - Checks if user's role is in the allowed set
  │     - Raises HTTP 403 if not authorized
  │
  ▼
Service Layer (e.g., CourseService.list_courses)
  │
  │  7. Business Logic
  │     - Validates business rules (e.g., can't publish empty course)
  │     - Calls Repository methods
  │     - Applies cross-cutting concerns (e.g., pagination)
  │
  ▼
Repository Layer (e.g., CourseRepository.list_by_org)
  │
  │  8. Database Query
  │     - ALWAYS includes WHERE organization_id = :org_id
  │     - Uses SQLAlchemy 2.0 select() statements
  │     - Returns ORM model instances
  │
  ▼
Service Layer (continued)
  │
  │  9. Persistence
  │     - Commits transaction if write operation
  │     - Handles DB errors (integrity violations, etc.)
  │
  │  10. Audit Log (for sensitive operations)
  │      - Writes to audit_logs table AFTER successful operation
  │      - Includes: actor_id, actor_role, org_id, action, resource details
  │
  ▼
Route Handler (continued)
  │
  │  11. Response Serialization
  │      - ORM model → Pydantic schema → JSON
  │      - Never expose internal IDs; use UUIDs only
  │      - Standard response envelope for errors
  │
  ▼
Browser
  │  HTTP Response (JSON body + appropriate status code)
```

---

## 4. Layering Rules

These rules are enforced by code review and must never be violated:

### Rule 1: Routes are thin

A route handler does **exactly** three things:
1. Parse and validate the incoming request (Pydantic does this automatically)
2. Call one service method
3. Return the result

```python
# CORRECT
@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(
    tenant: Organization = Depends(get_current_tenant),
    service: CourseService = Depends(get_course_service),
):
    return await service.list_courses(org_id=tenant.id)

# WRONG — business logic in route handler
@router.get("/courses")
async def list_courses(db: Session = Depends(get_db)):
    return db.query(Course).filter(Course.status == "published").all()
```

### Rule 2: Services hold business logic

Services:
- Implement all domain rules and validations
- Orchestrate calls to one or more repositories
- Write audit log entries
- Never write raw SQL or use `db` sessions directly (delegate to repos)

### Rule 3: Repositories hold queries

Repositories:
- Accept a `db` session and `org_id` as parameters
- Contain all SQLAlchemy `select()`, `insert()`, `update()` statements
- Always include `WHERE organization_id = :org_id` for tenant-owned tables
- Return ORM model instances, not Pydantic schemas

### Rule 4: Schemas are separate from ORM models

- `app/models/course.py` — SQLAlchemy ORM model (maps to DB table)
- `app/schemas/course.py` — Pydantic models (request body, response body)
- Never inherit from both; never use `model_validate` to hide the distinction

### Rule 5: Dependencies inject context

Auth user, tenant, and role context are injected via FastAPI `Depends()`. They are **never** passed as function arguments from route to route, or read from a global/thread-local variable.

---

## 5. Backend Folder Structure

```
backend/
├── app/
│   ├── __init__.py
│   │
│   ├── main.py
│   │   # FastAPI application factory.
│   │   # Creates the app instance, registers routers, adds middleware.
│   │   # Handles startup/shutdown events (DB connection pool, Redis).
│   │
│   ├── api/
│   │   # All HTTP route handlers. Thin by rule.
│   │   ├── __init__.py
│   │   └── v1/
│   │       # Version 1 of the API. All routes live here.
│   │       # Each file corresponds to one resource (auth, courses, sessions, etc.)
│   │       ├── __init__.py
│   │       ├── router.py      # Aggregates all v1 sub-routers into one APIRouter
│   │       ├── auth.py        # /auth/login, /auth/logout, /auth/register, /auth/refresh
│   │       ├── organizations.py  # /organizations (onboarding)
│   │       ├── users.py       # /users (admin manages users within org)
│   │       ├── courses.py     # /courses and /courses/{id}
│   │       ├── sessions.py    # /sessions
│   │       ├── enrollments.py # /enrollments
│   │       └── ...            # One file per resource
│   │
│   ├── core/
│   │   # Cross-cutting concerns: config, security utilities, middleware.
│   │   ├── __init__.py
│   │   ├── config.py
│   │   │   # Pydantic BaseSettings class. Reads all config from environment
│   │   │   # variables. This is the ONLY place env vars are read.
│   │   │   # Raises an error at startup if required vars are missing.
│   │   ├── security.py
│   │   │   # Password hashing (bcrypt), JWT encode/decode, cookie helpers.
│   │   │   # Does NOT contain route logic or DB access.
│   │   ├── middleware.py
│   │   │   # Custom Starlette middleware (request ID injection, logging).
│   │   └── storage.py
│   │       # Supabase Storage client wrapper. Methods: upload, get_presigned_url.
│   │
│   ├── db/
│   │   # Database connectivity only. No models, no queries.
│   │   ├── __init__.py
│   │   ├── base.py       # SQLAlchemy DeclarativeBase definition
│   │   └── session.py    # AsyncSession factory and get_db dependency
│   │
│   ├── models/
│   │   # SQLAlchemy ORM models. One file per entity.
│   │   # Each model class maps 1:1 to a database table.
│   │   ├── __init__.py
│   │   ├── base_model.py   # Abstract mixin: id (UUID), created_at, updated_at,
│   │   │                   # created_by, updated_by, status (for tenant-owned tables)
│   │   ├── organization.py # organizations table
│   │   ├── user.py         # users table
│   │   ├── course.py       # courses table
│   │   ├── audit_log.py    # audit_logs table (global, not tenant-scoped)
│   │   └── ...
│   │
│   ├── schemas/
│   │   # Pydantic v2 models for API request and response validation.
│   │   # Separate from ORM models. One file per resource.
│   │   ├── __init__.py
│   │   ├── auth.py       # LoginRequest, TokenResponse, UserResponse
│   │   ├── course.py     # CourseCreate, CourseUpdate, CourseResponse
│   │   ├── common.py     # Shared types: PaginatedResponse, ErrorResponse
│   │   └── ...
│   │
│   ├── services/
│   │   # Business logic layer. One file per domain concept.
│   │   # Services are plain Python classes (or functions).
│   │   # They receive a DB session and config as constructor args.
│   │   ├── __init__.py
│   │   ├── auth_service.py         # register, login, logout, refresh
│   │   ├── organization_service.py # create_organization
│   │   ├── course_service.py       # create_course, publish_course, etc.
│   │   ├── audit_service.py        # write_audit_log (called by other services)
│   │   └── ...
│   │
│   ├── repositories/
│   │   # Database query layer. One file per ORM model.
│   │   # All SQLAlchemy select/insert/update/delete lives here.
│   │   # Every method that touches a tenant-owned table accepts org_id.
│   │   ├── __init__.py
│   │   ├── user_repo.py         # get_by_email, create_user, get_by_id
│   │   ├── organization_repo.py # get_by_id, get_by_slug, create
│   │   ├── course_repo.py       # list_by_org, get_by_id_and_org, create
│   │   └── ...
│   │
│   └── dependencies/
│       # FastAPI Depends() functions. Injected into route handlers.
│       ├── __init__.py
│       ├── auth.py    # get_current_user: reads + validates JWT from cookie
│       ├── tenant.py  # get_current_tenant: reads org_id from JWT, loads org from DB
│       ├── rbac.py    # require_role(*roles): factory that returns a Depends
│       └── db.py      # get_db: yields an async DB session
│
├── alembic/
│   # Schema migrations managed by Alembic.
│   ├── env.py        # Alembic runtime config; imports all ORM models so
│   │                 # autogenerate can detect changes.
│   ├── script.py.mako  # Template for new migration files
│   └── versions/     # One .py file per migration, named with revision hash
│
├── tests/
│   # All tests. Mirror the app/ structure.
│   ├── conftest.py   # Shared pytest fixtures: test DB, test client, test users,
│   │                 # test organizations. Contains ALL test data setup.
│   ├── unit/         # Tests for services and repos in isolation (mocked DB)
│   └── integration/  # Tests against a real test DB using TestClient
│
├── alembic.ini
├── pyproject.toml
└── requirements.txt
```

---

## 6. Frontend Folder Structure

```
frontend/
├── app/
│   # Next.js 14 App Router. Folders = URL segments.
│   # layout.tsx = persistent shell. page.tsx = route content.
│   │
│   ├── layout.tsx          # Root layout: sets HTML lang, loads fonts, wraps in providers
│   ├── (public)/           # Route group for unauthenticated pages (not a URL segment)
│   │   ├── login/
│   │   │   └── page.tsx    # Login page
│   │   └── register/
│   │       └── page.tsx    # Registration/org onboarding page
│   │
│   └── (auth)/             # Route group for authenticated pages
│       ├── layout.tsx      # Auth layout: checks cookie presence, redirects if absent
│       ├── dashboard/
│       │   └── page.tsx    # Home dashboard (role-aware content)
│       ├── courses/
│       │   ├── page.tsx    # Course list
│       │   ├── [courseId]/
│       │   │   └── page.tsx  # Course detail / learning view
│       │   └── new/
│       │       └── page.tsx  # Course builder (Teacher/Admin only)
│       ├── sessions/
│       │   └── page.tsx
│       └── settings/
│           └── page.tsx    # Org settings (Admin only)
│
├── components/
│   # Reusable UI components. Not page-specific.
│   # Organized by domain, not by type (not "buttons/" and "forms/").
│   ├── ui/               # Generic, stateless components (Button, Input, Modal, Badge)
│   ├── auth/             # AuthGuard, LoginForm, etc.
│   ├── courses/          # CourseCard, CourseBreadcrumb, LessonPlayer, etc.
│   ├── layout/           # Sidebar, Navbar, PageHeader
│   └── shared/           # ErrorBoundary, LoadingSpinner, EmptyState
│
├── lib/
│   # Non-component logic: API calls, hooks, utilities, context.
│   ├── api/
│   │   # Functions that call the FastAPI backend.
│   │   # One file per resource. Always use the shared apiClient.
│   │   ├── client.ts     # Axios/fetch wrapper: sets baseURL, attaches credentials,
│   │   │                 # handles 401 → trigger refresh flow
│   │   ├── auth.ts       # login(), logout(), register(), getMe()
│   │   ├── courses.ts    # listCourses(), getCourse(), createCourse(), etc.
│   │   └── ...
│   │
│   ├── context/
│   │   # React Context providers for global state.
│   │   └── AuthContext.tsx  # Stores: user, org, role. Populated from /auth/me.
│   │                        # Never derives role from JWT directly.
│   │
│   └── hooks/
│       # Custom React hooks.
│       ├── useAuth.ts        # Returns { user, org, role, logout }
│       ├── useCourses.ts     # Returns { courses, isLoading, error }
│       └── ...
│
├── types/
│   # TypeScript type definitions shared across the app.
│   # Mirror the backend Pydantic schemas.
│   ├── auth.ts     # User, Organization, Role
│   ├── course.ts   # Course, Section, Lesson
│   └── common.ts   # PaginatedResponse<T>, ApiError
│
├── public/         # Static assets (images, icons, fonts)
├── styles/
│   └── globals.css  # Tailwind base + component + utility imports
│
├── middleware.ts
│   # Next.js middleware. Runs on the edge before every request.
│   # Checks for the presence of the access_token cookie.
│   # Redirects unauthenticated users to /login.
│   # Does NOT parse or validate the JWT — that is the backend's job.
│
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## 7. Environment Variables Reference

All environment variables are loaded in `backend/app/core/config.py` via Pydantic `BaseSettings`. The application will fail to start if any required variable is missing.

| Variable | Required | Example | Purpose |
|---|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://user:pass@host:5432/dbname` | SQLAlchemy async connection string |
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` | Redis connection for token blocklist |
| `JWT_SECRET_KEY` | ✅ | `<64-char random hex>` | HMAC key for JWT signing. Generate with `openssl rand -hex 32` |
| `JWT_ALGORITHM` | ✅ | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | `15` | Access token TTL in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✅ | `7` | Refresh token TTL in days |
| `SUPABASE_URL` | ✅ | `https://xyz.supabase.co` | Supabase project base URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | `eyJ...` | Supabase service role key (backend only, never expose to client) |
| `SUPABASE_STORAGE_BUCKET` | ✅ | `lms-files` | Default bucket for file storage |
| `FRONTEND_URL` | ✅ | `http://localhost:3000` | Allowed CORS origin |
| `ENVIRONMENT` | ✅ | `development` | Controls logging level, debug mode |
| `COOKIE_SECURE` | ✅ | `false` (dev) / `true` (prod) | httpOnly cookie Secure flag |
| `COOKIE_SAMESITE` | ✅ | `lax` | httpOnly cookie SameSite policy |

---

## 8. External Services

### Supabase (PostgreSQL 15 + Storage)

**Role:** Primary database and file storage.

- **PostgreSQL** is the source of truth for all application data. We use Supabase for managed hosting, connection pooling, and backups. We do **not** use Supabase Auth — we issue our own JWTs.
- **Supabase Storage** stores course materials, assignment files, and other user uploads. The backend uses the Supabase service role key to generate short-lived presigned URLs, which the frontend then uses to upload/download directly.
- **Why not use Supabase RLS (Row Level Security)?** This is an architectural decision deferred to a later phase. Application-level query scoping is implemented first because it is more transparent, testable, and debuggable. See ADR-0001.

### Redis 7

**Role:** Refresh token JTI blocklist (required) and optional caching (justified-use only).

- On logout, the refresh token's `jti` (JWT ID) is stored in Redis with a TTL equal to the token's remaining lifetime. The auth middleware checks every refresh attempt against this blocklist.
- Redis is also available for caching expensive queries (e.g., analytics aggregates) but must only be used when justified by profiling. Any new cache usage must be documented in an ADR.

### bcrypt (via passlib)

**Role:** Password hashing.

- All user passwords are hashed with bcrypt before storage. The plaintext password is never stored.
- Work factor: 12 rounds (reviewed periodically as hardware performance increases).

### No Other External Services (Phase 0–1)

Do not add external services (email providers, payment gateways, monitoring tools) without:
1. A documented justification (what problem does it solve that can't be solved otherwise?)
2. Human approval
3. An ADR entry


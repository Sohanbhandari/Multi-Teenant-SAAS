# Multi-Tenant Learning & Coaching Management SaaS

A production-grade, multi-tenant SaaS platform for managing learning programs, coaching sessions, courses, and learner progress — built for organizations, teachers, and students.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Role Model](#role-model)
- [Phase Delivery Plan](#phase-delivery-plan)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Documentation](#documentation)

---

## Project Overview

This platform allows **organizations** (tenants) to onboard, manage, and deliver coaching or learning programs to their members. Each organization operates in complete isolation from other tenants — they share the same database infrastructure but are separated at the row level via `organization_id`.

**Key capabilities (full roadmap):**
- Organization-scoped user management with role-based access (Admin, Teacher, Student)
- Course and curriculum authoring
- Session scheduling and attendance tracking
- Progress analytics and reporting
- File uploads (assignments, resources) via Supabase Storage
- Notifications and email delivery (background jobs)
- Code execution sandbox for programming courses (Phase 7)

**Current Status:** Phase 0 — Scaffold & Documentation only. No application code has been written yet.

---

## Tech Stack

| Layer | Technology | Version | Role |
|---|---|---|---|
| **Frontend Framework** | Next.js | 14 (App Router) | SSR/CSR hybrid UI |
| **UI Language** | TypeScript | 5.x | Type-safe frontend |
| **UI Library** | React | 18 | Component model |
| **Styling** | Tailwind CSS | 3.4 | Utility-first CSS |
| **Backend Framework** | FastAPI | 0.104 | REST API, security boundary |
| **Backend Language** | Python | 3.11 | All server-side logic |
| **Data Validation** | Pydantic | v2 | Request/response schemas |
| **ORM** | SQLAlchemy | 2.0 | Database access layer |
| **Migrations** | Alembic | latest | Schema version control |
| **Database** | PostgreSQL | 15 | Primary data store (via Supabase) |
| **Auth** | FastAPI JWT | custom | httpOnly cookie tokens |
| **File Storage** | Supabase Storage | — | Upload/download files |
| **Cache / Token Blocklist** | Redis | 7 | Refresh token revocation, optional cache |
| **Package Manager (FE)** | pnpm | 8+ | Fast, disk-efficient installs |
| **Package Manager (BE)** | pip + venv | — | Python dependency management |

---

## Repository Structure

```
Multi-Teenant-SAAS/
│
├── frontend/                        # Next.js 14 App Router application
│   ├── app/                         # App Router pages and layouts
│   │   ├── (auth)/                  # Auth-gated route group
│   │   ├── (public)/                # Public pages (login, signup)
│   │   └── layout.tsx               # Root layout
│   ├── components/                  # Shared UI components
│   ├── lib/                         # API clients, utilities, hooks
│   ├── styles/                      # Global CSS
│   ├── types/                       # Shared TypeScript types
│   ├── public/                      # Static assets
│   ├── next.config.ts               # Next.js configuration
│   ├── tailwind.config.ts           # Tailwind configuration
│   └── tsconfig.json                # TypeScript configuration
│
├── backend/                         # FastAPI Python application
│   ├── app/                         # Application package
│   │   ├── api/                     # Route handlers (thin — no business logic)
│   │   │   └── v1/                  # API version 1 routers
│   │   ├── core/                    # Config, security, middleware
│   │   ├── db/                      # Database engine, session factory
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── services/                # Business logic layer
│   │   ├── repositories/            # Database query layer
│   │   ├── dependencies/            # FastAPI dependency injection (auth, tenant)
│   │   └── main.py                  # App factory and startup
│   ├── alembic/                     # Database migrations
│   │   ├── versions/                # Migration files
│   │   └── env.py                   # Alembic environment config
│   ├── tests/                       # Test suite
│   │   ├── unit/                    # Unit tests (services, repos)
│   │   ├── integration/             # Integration tests (API endpoints)
│   │   └── conftest.py              # Shared fixtures
│   ├── alembic.ini                  # Alembic configuration
│   ├── pyproject.toml               # Project metadata and dependencies
│   └── requirements.txt             # Pinned dependencies
│
├── docs/                            # Project documentation
│   └── architecture/
│       ├── system-architecture.md   # Full system architecture document
│       ├── multi-tenancy.md         # Multi-tenancy model and patterns
│       ├── authentication.md        # Auth strategy and token lifecycle
│       ├── multi-tenant-erd.md      # Entity-relationship diagram and schema dictionary
│       └── data-and-tenant-ownership-matrix.md # Ownership matrix and constraint rationale
│
├── docker-compose.yml               # Local dev services (PostgreSQL, Redis)
├── .env.example                     # Environment variable template
└── README.md                        # This file
```

---

## Role Model

The platform uses a **three-fact authorization model**:

> **Who** (identity) → **Which tenant** (org context) → **What is allowed** (role + resource)

| Role | Scope | Capabilities |
|---|---|---|
| **Organization Admin** | Tenant-wide | Manage users, invite teachers/students, configure org settings, view all analytics |
| **Teacher** | Within their courses | Create/edit courses, schedule sessions, view student progress in their courses |
| **Student** | Within their enrollments | View and complete enrolled courses, submit assignments, view personal progress |

**Security rule:** The frontend **never** determines `org_id` or `role`. These are always extracted from the server-issued JWT by backend middleware. The client has zero authority over authorization context.

---

## Phase Delivery Plan

| Phase | Name | Key Deliverables | Status |
|---|---|---|---|
| **0** | Scaffold & Docs | Repo structure, documentation, ADRs, agent skills | 🟡 In Progress |
| **1** | Auth & Tenant Onboarding | JWT auth, org creation, user registration, RBAC middleware | ⬜ Planned |
| **2** | Course Management | Course CRUD, curriculum builder, file uploads | ⬜ Planned |
| **3** | Session Scheduling | Session creation, calendar views, attendance tracking | ⬜ Planned |
| **4** | Student Enrollment & Progress | Enrollment flows, progress tracking, completion status | ⬜ Planned |
| **5** | Assignments & Submissions | Assignment creation, student submissions, grading | ⬜ Planned |
| **6** | Analytics & Reporting | Org-wide dashboards, teacher analytics, student reports | ⬜ Planned |
| **7** | Code Execution Sandbox | Sandboxed code runner for programming courses | ⬜ Planned |
| **8** | Polish & Launch | Performance hardening, security audit, production deploy | ⬜ Planned |

> **Phase gate rule:** No phase begins until the previous phase's Definition of Done is verified. See [`docs/PROJECT_CHECKLIST.md`](docs/PROJECT_CHECKLIST.md).

---

## Quick Start

### Prerequisites

- **Docker Desktop** (for PostgreSQL + Redis locally)
- **Python 3.11** with `venv`
- **Node.js 20+** with `pnpm` (`npm install -g pnpm`)
- **Git**

### 1. Clone the Repository

```bash
git clone <repo-url>
cd Multi-Teenant-SAAS
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual values — see Environment Variables section below
```

### 3. Start Local Services (PostgreSQL + Redis)

```bash
docker-compose up -d
```

This starts:
- PostgreSQL 15 on `localhost:5432`
- Redis 7 on `localhost:6379`

### 4. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: `http://localhost:8000`  
Interactive API docs: `http://localhost:8000/docs`

### 5. Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Start the development server
pnpm dev
```

Frontend will be available at: `http://localhost:3000`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in values. **Never commit `.env` to version control.**

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `JWT_SECRET_KEY` | ✅ | Secret key for signing JWTs (min 32 chars, random) |
| `JWT_ALGORITHM` | ✅ | Algorithm for JWT signing (use `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | Access token lifetime (default: `15`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✅ | Refresh token lifetime (default: `7`) |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Supabase service role key (backend only) |
| `SUPABASE_STORAGE_BUCKET` | ✅ | Default storage bucket name |
| `FRONTEND_URL` | ✅ | Frontend origin for CORS (e.g., `http://localhost:3000`) |
| `ENVIRONMENT` | ✅ | `development`, `staging`, or `production` |
| `COOKIE_SECURE` | ✅ | `true` in production (requires HTTPS), `false` in dev |

---

## Documentation

| Document | Description |
|---|---|
| [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md) | Full system architecture, layering rules, folder map |
| [`docs/architecture/multi-tenancy.md`](docs/architecture/multi-tenancy.md) | Multi-tenancy model, query scoping, isolation strategy |
| [`docs/architecture/authentication.md`](docs/architecture/authentication.md) | JWT auth strategy, token lifecycle, RBAC patterns |
| [`docs/architecture/multi-tenant-erd.md`](docs/architecture/multi-tenant-erd.md) | Entity-relationship diagram and database schema dictionary |
| [`docs/architecture/data-and-tenant-ownership-matrix.md`](docs/architecture/data-and-tenant-ownership-matrix.md) | Data ownership matrix, index rationale, and constraint rationale |

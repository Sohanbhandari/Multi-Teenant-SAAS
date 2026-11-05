# Authentication Architecture

**Project:** Multi-Tenant Learning & Coaching Management SaaS  
**Version:** 1.0  
**Date:** 2026-11-03

---

## Table of Contents

1. [Chosen Strategy](#1-chosen-strategy)
2. [Token Lifecycle](#2-token-lifecycle)
3. [Cookie Security Flags](#3-cookie-security-flags)
4. [What the JWT Payload Contains](#4-what-the-jwt-payload-contains)
5. [Refresh Flow](#5-refresh-flow)
6. [Logout and Server-Side Token Revocation](#6-logout-and-server-side-token-revocation)
7. [Password Hashing](#7-password-hashing)
8. [Why FastAPI Issues Its Own JWTs (Not Supabase Auth)](#8-why-fastapi-issues-its-own-jwts-not-supabase-auth)
9. [RBAC Dependency Pattern](#9-rbac-dependency-pattern)
10. [Security Invariants](#10-security-invariants)

---

## 1. Chosen Strategy

**FastAPI-issued JWT tokens stored in httpOnly cookies.**

When a user logs in, the FastAPI backend:
1. Verifies credentials (email + bcrypt password check)
2. Issues two tokens: an **access token** (short-lived) and a **refresh token** (long-lived)
3. Sets both tokens as **httpOnly cookies** in the HTTP response

The frontend never sees the raw tokens. Cookies are automatically sent with every subsequent request from the browser.

### Why httpOnly cookies instead of localStorage?

| Risk | localStorage | httpOnly Cookie |
|---|---|---|
| **XSS attack** (malicious script reads token) | ❌ Vulnerable — JS can read `localStorage` | ✅ Safe — JS cannot read httpOnly cookies |
| **CSRF attack** (malicious site triggers request) | ✅ Not automatically sent cross-origin | ⚠️ Mitigated by `SameSite=Lax` + CSRF token on state-changing requests |
| **Framework/library support** | Simple to implement | Requires cookie handling |

httpOnly cookies with `SameSite=Lax` provide strong protection against the most common web authentication attacks, particularly XSS, which is more prevalent than CSRF.

---

## 2. Token Lifecycle

### Access Token

| Property | Value |
|---|---|
| **Purpose** | Authorize API requests |
| **Lifetime** | 15 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`) |
| **Storage** | httpOnly cookie named `access_token` |
| **When used** | Sent automatically by browser with every request |
| **What happens on expiry** | The server returns HTTP 401. The frontend intercepts this and triggers the refresh flow. |

### Refresh Token

| Property | Value |
|---|---|
| **Purpose** | Obtain a new access token without re-entering credentials |
| **Lifetime** | 7 days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`) |
| **Storage** | httpOnly cookie named `refresh_token` |
| **When used** | Sent to `POST /auth/refresh` when access token expires |
| **Rotation** | Each refresh generates a new refresh token and revokes the old one |
| **Revocation** | Old refresh token's `jti` is added to Redis blocklist on use |

### Why refresh token rotation?

If a refresh token is stolen, the attacker can use it to generate access tokens indefinitely. Rotation limits the damage window: as soon as the legitimate user refreshes, the stolen token becomes invalid. If the attacker uses the token first, the legitimate user will get a 401 on their next refresh, indicating a potential compromise.

---

## 3. Cookie Security Flags

Both the access token and refresh token cookies are set with these flags:

| Flag | Value | Why |
|---|---|---|
| `HttpOnly` | `true` | Prevents JavaScript from reading the cookie. Blocks XSS token theft. |
| `Secure` | `true` in production | Ensures cookie is only sent over HTTPS. Prevents token interception on insecure connections. `false` in development (no HTTPS locally). |
| `SameSite` | `Lax` | Prevents the cookie from being sent in cross-site requests (CSRF mitigation). `Lax` allows top-level navigations (clicking a link) but blocks cross-origin form POSTs. |
| `Path` | `/` | Cookie is sent with all requests to the backend. |
| `Max-Age` / `Expires` | Token TTL in seconds | Browser automatically removes the cookie when it expires. |

### Setting cookies in FastAPI

```python
# backend/app/core/security.py

from fastapi import Response
from datetime import timedelta

def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_token_expire_minutes: int,
    refresh_token_expire_days: int,
    secure: bool,
) -> None:
    """
    Sets httpOnly cookies for both access and refresh tokens.
    
    Called by the auth service after a successful login or refresh.
    Never call this directly from a route handler — use the auth service.
    """
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_token_expire_minutes * 60,
        httponly=True,
        secure=secure,          # True in production, False in dev
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/auth/refresh",   # Scoped to the refresh endpoint only
    )
```

> **Note:** Scoping the `refresh_token` cookie to `/auth/refresh` means the refresh token is only sent with requests to that path, reducing its exposure surface.

---

## 4. What the JWT Payload Contains

Every JWT issued by this system contains exactly these claims:

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "org_id": "7f7e4930-d9f3-4b2a-9b2a-8f9b3c5d1234",
  "role": "teacher",
  "jti": "unique-random-token-identifier",
  "iat": 1700000000,
  "exp": 1700000900,
  "token_type": "access"
}
```

| Claim | Type | Description |
|---|---|---|
| `sub` | UUID string | The user's UUID. This is the "subject" of the token. |
| `org_id` | UUID string | The organization this user belongs to. Used for tenant scoping. |
| `role` | string | The user's role: `admin`, `teacher`, or `student`. |
| `jti` | UUID string | JWT ID — a unique identifier for this token. Used to detect revoked tokens. |
| `iat` | Unix timestamp | "Issued at" — when the token was created. |
| `exp` | Unix timestamp | "Expires at" — when the token stops being valid. |
| `token_type` | string | `"access"` or `"refresh"`. Prevents a refresh token from being used as an access token. |

### What the JWT does NOT contain

| Missing Claim | Why |
|---|---|
| User's name or email | Not needed for authorization. Fetch from DB if needed. Avoids stale data. |
| Permissions list | Role is sufficient. Permissions are derived from role in code, not in JWT. |
| Organization name or slug | Not needed for authorization. Load from DB if needed for display. |
| User's password hash | Never. |

---

## 5. Refresh Flow

The refresh flow is triggered when the frontend receives an HTTP 401 from any API call:

```
Frontend                          FastAPI Backend                    Redis
  │                                     │                              │
  │  (Access token expired)             │                              │
  │                                     │                              │
  │──── POST /auth/refresh ────────────►│                              │
  │     (refresh_token cookie attached) │                              │
  │                                     │                              │
  │                            Decode refresh token                   │
  │                            Verify signature & expiry              │
  │                                     │                              │
  │                                     │── Check JTI in blocklist ───►│
  │                                     │◄─ "not found" (valid) ───────│
  │                                     │                              │
  │                            Generate new access_token              │
  │                            Generate new refresh_token             │
  │                                     │                              │
  │                                     │── Add OLD jti to blocklist ─►│
  │                                     │   (TTL = remaining old TTL)  │
  │                                     │◄─ OK ────────────────────────│
  │                                     │                              │
  │◄─── 200 OK (new cookies set) ───────│                              │
  │                                     │                              │
  │  Retry original request             │                              │
  │──── GET /courses ──────────────────►│                              │
  │◄─── 200 OK ─────────────────────────│                              │
```

If the refresh token is:
- **Expired** → Return 401. Frontend redirects to login.
- **In the Redis blocklist** → Return 401 (token reuse detected). Frontend redirects to login.
- **Valid** → Issue new token pair, return 200.

---

## 6. Logout and Server-Side Token Revocation

### The Problem with Stateless JWTs

Pure JWTs are stateless — once issued, they are valid until they expire. If a user logs out, the access token they had is still technically valid for up to 15 more minutes. A stolen token cannot be invalidated before expiry.

### Our Solution: Redis Blocklist for Refresh Tokens

On logout:
1. The `jti` from the **refresh token** is added to a Redis key with a TTL equal to the token's remaining lifetime.
2. The access token and refresh token cookies are cleared (set to empty, expires in the past).
3. On any subsequent refresh attempt, the backend checks Redis — the revoked token is rejected.

```python
# backend/app/services/auth_service.py

async def logout(self, refresh_token: str, response: Response) -> None:
    """
    Logs out the user by:
    1. Decoding the refresh token to get its JTI and remaining TTL
    2. Adding the JTI to the Redis blocklist
    3. Clearing both auth cookies from the response
    
    The access token cannot be revoked directly (it's stateless).
    Its 15-minute lifetime is an acceptable security trade-off.
    """
    try:
        payload = self.security.decode_token(refresh_token)
        jti = payload["jti"]
        exp = payload["exp"]
        remaining_ttl = int(exp - time.time())
        
        if remaining_ttl > 0:
            await self.redis.setex(
                f"blocklist:{jti}",
                remaining_ttl,
                "revoked"
            )
    except Exception:
        # Even if token decoding fails, clear the cookies
        pass
    finally:
        self.security.clear_auth_cookies(response)
```

### Why not blocklist access tokens too?

Access tokens have a 15-minute lifetime. Adding them to a Redis blocklist would require a Redis lookup on every single API request — significant operational overhead. The 15-minute window is an accepted security trade-off. If shorter invalidation is required for specific high-security actions (e.g., admin privilege removal), the access token lifetime can be reduced or a dedicated endpoint can force re-authentication.

---

## 7. Password Hashing

**Algorithm:** bcrypt via `passlib[bcrypt]`

```python
# backend/app/core/security.py

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.
    
    The resulting hash is safe to store in the database.
    bcrypt automatically generates and embeds a random salt,
    so two hashes of the same password will differ.
    
    Never store plain-text passwords. Never log plain-text passwords.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a bcrypt hash.
    
    Returns True if the password matches, False otherwise.
    Uses constant-time comparison to prevent timing attacks.
    """
    return pwd_context.verify(plain_password, hashed_password)
```

**bcrypt work factor:** The default rounds (12) are used. This takes approximately 100–300ms per hash on modern hardware, which is intentionally slow to make brute-force attacks impractical. Review this periodically as hardware performance increases.

---

## 8. Why FastAPI Issues Its Own JWTs (Not Supabase Auth)

Supabase provides an Auth service that can issue JWTs. We chose **not** to use Supabase Auth as our primary auth system.

### Reason 1: JWT payload control

Supabase Auth JWTs have a fixed payload structure. Our system needs custom claims: `org_id` (for multi-tenancy) and `role` (for RBAC). Adding custom claims to Supabase JWTs requires workarounds (custom access token hooks) that add complexity and a runtime dependency on Supabase's infrastructure.

### Reason 2: Refresh token rotation

Supabase Auth's refresh token behavior is managed by Supabase. We cannot fully control the rotation logic, blocklist checks, or revocation strategy without building on top of it.

### Reason 3: Redis blocklist

Our logout strategy requires a Redis blocklist. This is custom infrastructure that must be managed by our backend regardless. Integrating it with Supabase Auth would create an awkward dependency.

### Reason 4: Unified security boundary

FastAPI is our single security boundary. If auth lived in Supabase, every request would need to be validated against Supabase's servers, creating a network dependency and a split security model. Having everything in FastAPI means one place to audit, one place to debug, one place to change.

### Supabase usage

We **do** use Supabase for:
- PostgreSQL database hosting (connection string used by SQLAlchemy)
- File storage (course materials, submissions)

We do **not** use Supabase for:
- Authentication or JWT issuance
- Row Level Security (deferred to a future phase)
- Supabase client libraries in the backend (we use SQLAlchemy + supabase-py for storage only)

---

## 9. RBAC Dependency Pattern

Role-Based Access Control is implemented as FastAPI dependencies that are declared on each route.

### Role Constants

```python
# backend/app/core/roles.py

from enum import StrEnum

class Role(StrEnum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
```

### RBAC Dependency Factory

```python
# backend/app/dependencies/rbac.py

from fastapi import Depends, HTTPException, status
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.core.roles import Role


def require_role(*allowed_roles: Role):
    """
    FastAPI dependency factory that enforces role-based access control.
    
    Usage:
        @router.post("/courses")
        async def create_course(
            _: None = Depends(require_role(Role.ADMIN, Role.TEACHER)),
        ):
            ...
    
    How it works:
    - Calls get_current_user to verify the JWT (auth check first)
    - Checks if the user's role is in the allowed_roles set
    - Raises HTTP 403 if the role is not permitted
    
    The user's role comes from the JWT payload — never from the request body.
    """
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    
    return check_role
```

### Usage in Routes

```python
# backend/app/api/v1/courses.py

@router.post("/courses", response_model=CourseResponse, status_code=201)
async def create_course(
    body: CourseCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_role(Role.ADMIN, Role.TEACHER)),
    service: CourseService = Depends(get_course_service),
):
    """Only admins and teachers can create courses."""
    return await service.create_course(
        org_id=tenant.id,
        created_by=current_user.id,
        data=body,
    )


@router.delete("/courses/{course_id}", status_code=204)
async def delete_course(
    course_id: UUID,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_role(Role.ADMIN)),
    service: CourseService = Depends(get_course_service),
):
    """Only admins can delete courses."""
    await service.delete_course(
        course_id=course_id,
        org_id=tenant.id,
        deleted_by=current_user.id,
    )
```

---

## 10. Security Invariants

These are non-negotiable security properties that must hold at all times. Test these explicitly.

| # | Invariant | Verified by |
|---|---|---|
| 1 | No endpoint returns data to an unauthenticated request | Integration test: call any protected endpoint without cookie → expect 401 |
| 2 | No endpoint returns data to a user from a different organization | Integration test: cross-tenant access test → expect 404 |
| 3 | No endpoint allows a lower-privileged role to perform a higher-privileged action | Integration test: student calls admin endpoint → expect 403 |
| 4 | A revoked refresh token cannot be used | Integration test: logout, then attempt refresh → expect 401 |
| 5 | An expired access token is rejected | Integration test: use expired token → expect 401 |
| 6 | A forged/tampered JWT is rejected | Integration test: modify JWT payload → expect 401 |
| 7 | The `org_id` in a request body has no effect on authorization | Integration test: send different org_id in body → verify it is ignored |
| 8 | Passwords are never returned in any API response | Unit test: User response schema has no `password` or `hashed_password` field |
| 9 | Auth cookies are cleared on logout | Integration test: call logout → verify cookies are cleared in response |


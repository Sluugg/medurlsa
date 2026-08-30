"""
Authentication / authorisation helpers.

Current behaviour:
  - require_admin checks a static Bearer token from config.
  - Failed attempts are rate-limited per IP: 5 failures within 15 minutes
    locks that IP out for the remainder of that window. X-Forwarded-For is
    respected so the real client IP is used behind a reverse proxy.

Future (multi-user):
  - Replace the body of _verify_token with a DB lookup against the users table.
  - Use require_permission("create_links") etc. on individual routes instead of
    require_admin, so per-role access control falls out automatically.
  - The route signatures don't need to change — only this module.
"""

import secrets
import time
from collections import defaultdict

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import ADMIN_TOKEN
from app.rate_limit import client_ip

_bearer = HTTPBearer()

# ── Rate limiting ─────────────────────────────────────────────────────────────
# In-memory store: IP → list of failure timestamps.
# Safe for single-worker deployments; resets on process restart.

_MAX_FAILURES = 10    # max failures allowed within the window
_WINDOW_S     = 500   # rolling window and lockout time

_failures: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    now    = time.time()
    cutoff = now - _WINDOW_S
    _failures[ip] = [t for t in _failures[ip] if t > cutoff]
    if len(_failures[ip]) >= _MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(_WINDOW_S)},
        )


def _record_failure(ip: str) -> None:
    _failures[ip].append(time.time())


def _clear_failures(ip: str) -> None:
    _failures.pop(ip, None)


# ── Token verification ────────────────────────────────────────────────────────

def _verify_token(token: str) -> str:
    """
    Verify a bearer token and return an identity string.

    Currently: validates against the static ADMIN_TOKEN from config.
    Future:     look up token in the users table, return user id / role.
    """
    if not ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_TOKEN is not configured on the server.",
        )
    if not secrets.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "admin"


def require_admin(
    request:     Request,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Dependency: requires a valid admin bearer token. Rate-limits failures by IP."""
    ip = client_ip(request)
    _check_rate_limit(ip)
    try:
        result = _verify_token(credentials.credentials)
        _clear_failures(ip)
        return result
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            _record_failure(ip)
        raise


def require_permission(permission: str):
    """
    Dependency factory: requires a token whose role includes *permission*.

    Currently a no-op wrapper around require_admin — every valid token has
    all permissions.  When the user table is live, swap the body for a real
    role/permission check.
    """
    def _dep(
        request:     Request,
        credentials: HTTPAuthorizationCredentials = Security(_bearer),
    ) -> str:
        return require_admin(request, credentials)
    return _dep

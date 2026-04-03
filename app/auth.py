"""
Authentication / authorisation helpers.

Current behaviour:
  - require_admin checks a static Bearer token from config.

Future (multi-user):
  - Replace the body of _verify_token with a DB lookup against the users table.
  - Use require_permission("create_links") etc. on individual routes instead of
    require_admin, so per-role access control falls out automatically.
  - The route signatures don't need to change — only this module.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import ADMIN_TOKEN

_bearer = HTTPBearer()


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
    if token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "admin"


def require_admin(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Dependency: requires a valid admin bearer token."""
    return _verify_token(credentials.credentials)


def require_permission(permission: str):
    """
    Dependency factory: requires a token whose role includes *permission*.

    Currently a no-op wrapper around require_admin — every valid token has
    all permissions.  When the user table is live, swap the body for a real
    role/permission check.
    """
    def _dep(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> str:
        return _verify_token(credentials.credentials)
    return _dep

"""
Per-IP request tracking shared by the admin login guard (app/auth.py) and the
public endpoints that are otherwise unauthenticated and could be used to
brute-force guess link IDs (register, cover art).

In-memory only: safe for this app's single-worker deployment model (the same
constraint SQLite already imposes on the process), resets on restart.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


def client_ip(request: Request) -> str:
    """Return the real client IP, honouring X-Forwarded-For from a reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limiter(max_requests: int, window_s: int):
    """
    Dependency factory: returns a FastAPI dependency allowing at most
    max_requests per client IP within a rolling window_s-second window.
    Each call to this factory gets its own independent counter — endpoints
    using separate instances have separate budgets.
    """
    hits: dict[str, list[float]] = defaultdict(list)

    def _dep(request: Request) -> None:
        ip     = client_ip(request)
        now    = time.time()
        cutoff = now - window_s
        hits[ip] = [t for t in hits[ip] if t > cutoff]
        if len(hits[ip]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
                headers={"Retry-After": str(window_s)},
            )
        hits[ip].append(now)

    return _dep

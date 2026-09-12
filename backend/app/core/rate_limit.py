"""
Minimal in-memory sliding-window rate limiter.

The /api/identify endpoint is deliberately left unauthenticated (it's the
public "walk up to the camera" flow), which makes it the one endpoint an
anonymous client could hammer. A tiny per-IP rate limit is cheap insurance
against that, without needing an external dependency (Redis, slowapi) for
what is a small, single-process application.

Not suitable as-is for a multi-process/horizontally-scaled deployment (state
is per-process); a production version would move this to shared storage.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_WINDOW_SECONDS = 10
_MAX_REQUESTS_PER_WINDOW = 15

_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _hits[client_ip]

    while hits and now - hits[0] > _WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= _MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many identification requests - please slow down.",
        )
    hits.append(now)

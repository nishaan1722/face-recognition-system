import secrets

from fastapi import Header, HTTPException, status

from app.core.config import ADMIN_TOKEN


def require_admin(x_admin_token: str = Header(default="")) -> None:
    """
    Simple shared-secret guard for admin-only endpoints (register / list / delete).

    This is intentionally lightweight for the scope of this assignment. In a
    production system this header check would be replaced with proper
    session-based auth (e.g. OAuth2/JWT + role checks per admin user), but the
    principle -- registration and management of identity data must be
    authenticated, while the read-only "identify" flow can stay open for
    walk-up kiosk use -- would remain the same.
    """
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid admin token.",
        )

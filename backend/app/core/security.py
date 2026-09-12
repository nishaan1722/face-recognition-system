import secrets

from fastapi import Header, HTTPException, status

from app.core.config import ADMIN_TOKEN


def require_admin(x_admin_token: str = Header(default="")) -> None:
    
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid admin token.",
        )

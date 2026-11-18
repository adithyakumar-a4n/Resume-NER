"""Password hashing, bearer-token creation, and request authentication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import SECRET_KEY
from .db import conn


PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
BEARER_SCHEME = HTTPBearer(auto_error=False)
TOKEN_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(hours=8)


def hashpw(password: str) -> str:
    """Return a bcrypt password hash."""
    return PASSWORD_CONTEXT.hash(password)


def checkpw(password: str, password_hash: str) -> bool:
    """Check a password against its stored hash."""
    return PASSWORD_CONTEXT.verify(password, password_hash)


def token(user: dict[str, Any]) -> str:
    """Create an eight-hour bearer token for an authenticated user."""
    expires_at = datetime.now(timezone.utc) + TOKEN_LIFETIME
    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "exp": expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=TOKEN_ALGORITHM)


def current(
    credentials: HTTPAuthorizationCredentials | None = Depends(BEARER_SCHEME),
) -> dict[str, Any]:
    """Resolve the bearer token to an active account."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in required")

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[TOKEN_ALGORITHM],
        )
        user_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        ) from exc

    with conn() as connection:
        user = connection.execute(
            "SELECT id, name, email, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if user is None:
        raise HTTPException(status_code=401, detail="Account not found")

    return dict(user)


def role_required(required_role: str):
    """Build a dependency that checks the authenticated account's role."""

    def check(user: dict[str, Any] = Depends(current)) -> dict[str, Any]:
        if user["role"] != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"{required_role.title()} account required",
            )
        return user

    return check

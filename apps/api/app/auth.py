"""Who is calling. The browser never talks to the API directly: the web app
checks the Auth.js session, then forwards the request with a short-lived
HS256 token whose `sub` is the user's id (apps/web/src/lib/backend.ts). This
module verifies that token. Anything without a valid one is a 401.
"""

from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

MIN_SECRET_LENGTH = 32


def check_secret(settings: Settings) -> None:
    """Called at startup: the API never runs with a missing or short secret."""
    if len(settings.backend_jwt_secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"BACKEND_JWT_SECRET must be set to at least {MIN_SECRET_LENGTH} characters "
            "(the same value the web app uses) - generate one with `openssl rand -base64 48`."
        )


def user_id_from_token(token: str, settings: Settings) -> int:
    try:
        claims = jwt.decode(
            token,
            settings.backend_jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Not signed in.") from exc


def current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not signed in.")
    user = db.get(User, user_id_from_token(token, settings))
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user

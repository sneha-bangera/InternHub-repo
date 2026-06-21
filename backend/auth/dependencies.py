from __future__ import annotations
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from backend.auth.security import decode_access_token
from backend.db.database import get_db
from backend.db.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise exc
    try:
        user_id_str = decode_access_token(credentials.credentials)
    except JWTError:
        raise exc
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise exc
    return user

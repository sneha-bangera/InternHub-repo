from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
# from passlib.context import CryptContext

from backend.core.config import settings
from backend.core.redis_client import redis_client

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# def hash_password(plain: str) -> str:
#     return pwd_context.hash(plain)


# def verify_password(plain: str, hashed: str) -> bool:
#     return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc), "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    sub = payload.get("sub")
    if sub is None:
        raise JWTError("Missing subject")
    return sub


_PREFIX = "refresh:"


def _key(token: str) -> str:
    return f"{_PREFIX}{token}"


def create_refresh_token(user_id: str) -> str:
    token = str(uuid.uuid4())
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400
    redis_client.setex(_key(token), ttl, user_id)
    return token


def validate_refresh_token(token: str) -> str | None:
    return redis_client.get(_key(token))


def rotate_refresh_token(old_token: str, user_id: str) -> str:
    redis_client.delete(_key(old_token))
    return create_refresh_token(user_id)


def revoke_refresh_token(token: str) -> None:
    redis_client.delete(_key(token))

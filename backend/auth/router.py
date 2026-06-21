from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.auth.schemas import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse
from backend.auth.security import (
    create_access_token, create_refresh_token, hash_password,
    revoke_refresh_token, rotate_refresh_token, validate_refresh_token, verify_password,
)
from backend.api.schemas import UserOut
from backend.db.database import get_db
from backend.db.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalars(select(User).where(User.email == body.email)).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        whatsapp_number=body.whatsapp_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = str(user.id)
    return TokenResponse(access_token=create_access_token(uid), refresh_token=create_refresh_token(uid))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email)).first()
    exc = HTTPException(status_code=401, detail="Incorrect email or password")
    if not user or not verify_password(body.password, user.hashed_password):
        raise exc
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    uid = str(user.id)
    return TokenResponse(access_token=create_access_token(uid), refresh_token=create_refresh_token(uid))


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    user_id = validate_refresh_token(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or has expired")
    new_refresh = rotate_refresh_token(body.refresh_token, user_id)
    return TokenResponse(access_token=create_access_token(user_id), refresh_token=new_refresh)


@router.post("/logout", status_code=204)
def logout(body: LogoutRequest):
    revoke_refresh_token(body.refresh_token)
    return None


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

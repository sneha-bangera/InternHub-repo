from typing import Type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db.database import get_db
from backend.db.models import (
    Certificate, Education, Project, ResumeProfile, Skill, User,
)
from backend.api.resume_schemas import (
    CertificateCreate, CertificateOut, CertificateUpdate,
    EducationCreate, EducationOut, EducationUpdate,
    ProjectCreate, ProjectOut, ProjectUpdate,
    ResumeProfileCreate, ResumeProfileOut, ResumeProfileUpdate,
    SkillCreate, SkillOut, SkillUpdate,
)

router = APIRouter(prefix="/api/resume/profile", tags=["Resume Profile"])


def _get_profile(db: Session, user_id: UUID) -> ResumeProfile:
    profile = db.scalars(
        select(ResumeProfile).where(ResumeProfile.user_id == user_id)
    ).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Resume profile not found")
    return profile


def _get_owned_item(
    db: Session, model: Type, item_id: UUID, profile_id: UUID,
):
    item = db.scalars(
        select(model).where(model.id == item_id, model.profile_id == profile_id)
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Resume item not found")
    return item


def _create_item(db: Session, model: Type, profile_id: UUID, body: BaseModel):
    values = body.model_dump()
    item = model(profile_id=profile_id, **values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _update_fields(db: Session, item, body):
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and not item.__table__.columns[field].nullable:
            raise HTTPException(
                status_code=422, detail=f"{field} cannot be null"
            )
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.post("", response_model=ResumeProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(
    body: ResumeProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.scalars(
        select(ResumeProfile).where(ResumeProfile.user_id == current_user.id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Resume profile already exists")
    profile = ResumeProfile(user_id=current_user.id, **body.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=ResumeProfileOut)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_profile(db, current_user.id)


@router.patch("", response_model=ResumeProfileOut)
def update_profile(
    body: ResumeProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = _get_profile(db, current_user.id)
    return _update_fields(db, profile, body)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = _get_profile(db, current_user.id)
    db.delete(profile)
    db.commit()


def _register_item_routes(path: str, model: Type, create_schema: Type, update_schema: Type, out_schema: Type):
    @router.get(f"/{path}", response_model=list[out_schema], name=f"list_{path}")
    def list_items(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        profile = _get_profile(db, current_user.id)
        return db.scalars(
            select(model).where(model.profile_id == profile.id).order_by(model.id)
        ).all()

    @router.post(
        f"/{path}", response_model=out_schema, status_code=status.HTTP_201_CREATED,
        name=f"create_{path}",
    )
    def create_item(
        body: create_schema,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        profile = _get_profile(db, current_user.id)
        return _create_item(db, model, profile.id, body)

    @router.get(
        f"/{path}/{{item_id}}", response_model=out_schema, name=f"read_{path}",
    )
    def read_item(
        item_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        profile = _get_profile(db, current_user.id)
        return _get_owned_item(db, model, item_id, profile.id)

    @router.patch(
        f"/{path}/{{item_id}}", response_model=out_schema, name=f"update_{path}",
    )
    def update_item(
        item_id: UUID,
        body: update_schema,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        profile = _get_profile(db, current_user.id)
        item = _get_owned_item(db, model, item_id, profile.id)
        return _update_fields(db, item, body)

    @router.delete(
        f"/{path}/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{path}",
    )
    def delete_item(
        item_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        profile = _get_profile(db, current_user.id)
        item = _get_owned_item(db, model, item_id, profile.id)
        db.delete(item)
        db.commit()


_register_item_routes("education", Education, EducationCreate, EducationUpdate, EducationOut)
_register_item_routes("projects", Project, ProjectCreate, ProjectUpdate, ProjectOut)
_register_item_routes("skills", Skill, SkillCreate, SkillUpdate, SkillOut)
_register_item_routes(
    "certificates", Certificate, CertificateCreate, CertificateUpdate, CertificateOut
)

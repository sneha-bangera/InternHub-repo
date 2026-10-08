from __future__ import annotations
import math
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.db.models import Application, Listing, UserSkill


def get_listing(db: Session, listing_id: UUID) -> Optional[Listing]:
    return db.get(Listing, listing_id)


def get_listings(db, page=1, page_size=20, platform=None, search=None):
    stmt = select(Listing).where(Listing.is_active == True)
    if platform:
        stmt = stmt.where(Listing.source_platform == platform)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Listing.title.ilike(like) | Listing.company.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Listing.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return db.scalars(stmt).all(), total


def upsert_listing(db: Session, data: dict) -> Listing:
    """
    Insert or update a listing by (source_platform, external_id).
    Invalidates the Redis embedding cache on update so stale
    embeddings don't persist after scraper runs.
    """
    from nlp.matcher import invalidate_listing_embedding

    existing = db.scalars(
        select(Listing).where(
            Listing.source_platform == data["source_platform"],
            Listing.external_id == data["external_id"],
        )
    ).first()
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        # Invalidate cached embedding-listing content may have changed
        invalidate_listing_embedding(str(existing.id))
        return existing
    listing = Listing(**data)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def get_application(db: Session, application_id: UUID, user_id: UUID) -> Optional[Application]:
    return db.scalars(
        select(Application)
        .options(joinedload(Application.listing))
        .where(Application.id == application_id, Application.user_id == user_id)
    ).first()


def get_user_applications(db: Session, user_id: UUID) -> list[Application]:
    return db.scalars(
        select(Application)
        .options(joinedload(Application.listing))
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
    ).all()


def create_application(db, user_id, listing_id, status, notes):
    existing = db.scalars(
        select(Application).where(
            Application.user_id == user_id,
            Application.listing_id == listing_id,
        )
    ).first()
    if existing:
        return get_application(db, existing.id, user_id)
    app = Application(user_id=user_id, listing_id=listing_id, status=status, notes=notes)
    db.add(app)
    db.commit()
    db.refresh(app)
    return get_application(db, app.id, user_id)


def update_application(db, application, status, notes, applied_at=None):
    if status is not None:
        application.status = status
    if notes is not None:
        application.notes = notes
    if applied_at is not None:
        application.applied_at = applied_at
    db.commit()
    db.refresh(application)
    return application


def delete_application(db, application):
    db.delete(application)
    db.commit()


def get_user_skills(db, user_id):
    return db.scalars(
        select(UserSkill).where(UserSkill.user_id == user_id).order_by(UserSkill.skill)
    ).all()


def add_user_skill(db, user_id, skill, proficiency):
    norm = skill.lower().strip()
    existing = db.scalars(
        select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.skill == norm)
    ).first()
    if existing:
        if proficiency:
            existing.proficiency = proficiency
            db.commit()
            db.refresh(existing)
        return existing
    us = UserSkill(user_id=user_id, skill=norm, proficiency=proficiency)
    db.add(us)
    db.commit()
    db.refresh(us)
    return us


def delete_user_skill(db, skill_id, user_id):
    us = db.scalars(
        select(UserSkill).where(UserSkill.id == skill_id, UserSkill.user_id == user_id)
    ).first()
    if not us:
        return False
    db.delete(us)
    db.commit()
    return True

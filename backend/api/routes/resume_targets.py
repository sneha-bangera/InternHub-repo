from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.target_schemas import (
    JDParseRequest, JobTargetOut, JobTargetUpdate,
)
from backend.auth.dependencies import get_current_user
from backend.db.database import get_db
from backend.db.models import JobTarget, Listing, User
from backend.services.llm_service import (
    LLMConfigurationError, LLMServiceError, llm_service,
)

router = APIRouter(prefix="/api/resume", tags=["Resume Targets"])


def _get_owned_target(db: Session, target_id: UUID, user_id: UUID) -> JobTarget:
    target = db.scalars(
        select(JobTarget).where(
            JobTarget.id == target_id, JobTarget.user_id == user_id
        )
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


@router.post(
    "/jd/parse", response_model=JobTargetOut, status_code=status.HTTP_201_CREATED
)
def parse_job_description(
    body: JDParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    listing_id = None
    if body.listing_id is not None:
        listing = db.get(Listing, body.listing_id)
        if listing is None or not listing.is_active:
            raise HTTPException(status_code=404, detail="Listing not found")
        jd_text = "\n".join(
            part.strip()
            for part in (
                listing.title,
                listing.description or "",
                listing.skills_required or "",
            )
            if part and part.strip()
        )
        company_name = listing.company
        role_title = body.role_title or listing.title
        listing_id = listing.id
    else:
        jd_text = body.jd_text.strip()
        company_name = body.company_name.strip()
        role_title = body.role_title

    try:
        parsed = llm_service.parse_job_description(jd_text)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    target = JobTarget(
        user_id=current_user.id,
        listing_id=listing_id,
        company_name=company_name,
        role_title=role_title or parsed.role_title,
        seniority=parsed.seniority,
        jd_text=jd_text,
        required_skills=parsed.required_skills,
        preferred_skills=parsed.preferred_skills,
        keywords=parsed.keywords,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.get("/targets", response_model=list[JobTargetOut])
def list_targets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(JobTarget)
        .where(JobTarget.user_id == current_user.id)
        .order_by(JobTarget.created_at.desc())
    ).all()


@router.get("/targets/{target_id}", response_model=JobTargetOut)
def get_target(
    target_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_target(db, target_id, current_user.id)


@router.patch("/targets/{target_id}", response_model=JobTargetOut)
def update_target(
    target_id: UUID,
    body: JobTargetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = _get_owned_target(db, target_id, current_user.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and not JobTarget.__table__.columns[field].nullable:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(target, field, value)
    db.commit()
    db.refresh(target)
    return target

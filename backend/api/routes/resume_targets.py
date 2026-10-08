import hashlib
import hmac
import time
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.target_schemas import (
    JDParseRequest, JobTargetOut, JobTargetUpdate, ResumeCompileJobOut,
    OverleafSnippetOut, ResumeCompileRequest, ResumeSelectionOut,
)
from backend.auth.dependencies import get_current_user
from backend.celery_app import celery_app
from backend.core.config import settings
from backend.db.database import get_db
from backend.db.models import (
    JobTarget, Listing, Project, ResumeCompileJob, ResumeProfile, User,
)
from backend.services.llm_service import (
    LLMConfigurationError, LLMServiceError, llm_service,
)
from backend.services.resume_selection_service import resume_selection_service

router = APIRouter(prefix="/api/resume", tags=["Resume Targets"])
OVERLEAF_SNIPPET_TTL_SECONDS = 600
DEFAULT_RESUME_SECTIONS = {
    "contact": True,
    "education": True,
    "projects": True,
    "skills": True,
    "certificates": True,
}


def _get_owned_target(db: Session, target_id: UUID, user_id: UUID) -> JobTarget:
    target = db.scalars(
        select(JobTarget).where(
            JobTarget.id == target_id, JobTarget.user_id == user_id
        )
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


def _get_owned_compile_job(
    db: Session, job_id: UUID, user_id: UUID
) -> ResumeCompileJob:
    job = db.scalars(
        select(ResumeCompileJob).where(
            ResumeCompileJob.id == job_id,
            ResumeCompileJob.user_id == user_id,
        )
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Resume compile job not found")
    return job


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


@router.post(
    "/targets/{target_id}/select",
    response_model=ResumeSelectionOut,
)
def select_resume_content(
    target_id: UUID,
    top_n: int = Query(default=4, ge=0, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = _get_owned_target(db, target_id, current_user.id)
    profile = db.scalars(
        select(ResumeProfile).where(ResumeProfile.user_id == current_user.id)
    ).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Resume profile not found")
    try:
        return resume_selection_service.select(profile, target, top_n=top_n)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/targets/{target_id}/compile",
    response_model=ResumeCompileJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def compile_resume_target(
    target_id: UUID,
    body: ResumeCompileRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = _get_owned_target(db, target_id, current_user.id)
    profile = db.scalars(
        select(ResumeProfile).where(ResumeProfile.user_id == current_user.id)
    ).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Resume profile not found")

    request = body or ResumeCompileRequest()
    selected_project_ids = request.selected_project_ids
    if selected_project_ids is not None:
        owned_project_ids = set(
            db.scalars(
                select(Project.id).where(
                    Project.profile_id == profile.id,
                    Project.id.in_(selected_project_ids),
                )
            ).all()
        )
        if owned_project_ids != set(selected_project_ids):
            raise HTTPException(
                status_code=422,
                detail="Selected projects must belong to the resume profile",
            )
    sections = DEFAULT_RESUME_SECTIONS | request.sections
    job = ResumeCompileJob(
        target_id=target.id,
        user_id=current_user.id,
        status="queued",
        sections=sections,
        selected_project_ids=(
            [str(project_id) for project_id in selected_project_ids]
            if selected_project_ids is not None
            else None
        ),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        celery_app.send_task(
            "backend.tasks.resume_compile_tasks.compile_resume",
            args=[str(job.id)],
            task_id=str(job.id),
        )
    except Exception as exc:
        job.status = "failed"
        job.error = "Unable to queue resume compilation"
        db.commit()
        raise HTTPException(
            status_code=503, detail="Resume compiler is unavailable"
        ) from exc
    return job


@router.get("/jobs/{job_id}", response_model=ResumeCompileJobOut)
def get_resume_compile_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_compile_job(db, job_id, current_user.id)


@router.get("/jobs/{job_id}/overleaf", response_model=OverleafSnippetOut)
def get_overleaf_snippet(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_owned_compile_job(db, job_id, current_user.id)
    if job.status != "succeeded":
        raise HTTPException(status_code=409, detail="Resume source is not ready")

    public_api_url = settings.PUBLIC_API_URL.rstrip("/")
    parsed_api_url = urlsplit(public_api_url)
    if (
        parsed_api_url.scheme not in {"http", "https"}
        or not parsed_api_url.netloc
        or parsed_api_url.username
        or parsed_api_url.password
    ):
        raise HTTPException(
            status_code=503,
            detail="Overleaf import requires PUBLIC_API_URL to be a valid HTTP(S) API URL",
        )
    expires = int(time.time()) + OVERLEAF_SNIPPET_TTL_SECONDS
    message = f"overleaf:{job.id}:{expires}".encode("utf-8")
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    return {
        "snip_uri": (
            f"{public_api_url}/api/resume/overleaf/{job.id}"
            f"?expires={expires}&signature={signature}"
        ),
        "snip_name": f"resume-{job.target_id}.tex",
    }


@router.get("/overleaf/{job_id}")
def serve_overleaf_snippet(
    job_id: UUID,
    expires: int,
    signature: str,
    db: Session = Depends(get_db),
):
    if expires < int(time.time()) or expires > int(time.time()) + OVERLEAF_SNIPPET_TTL_SECONDS:
        raise HTTPException(status_code=403, detail="Overleaf snippet link has expired")
    message = f"overleaf:{job_id}:{expires}".encode("utf-8")
    expected_signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=403, detail="Invalid Overleaf snippet link")
    job = db.get(ResumeCompileJob, job_id)
    if job is None or job.status != "succeeded":
        raise HTTPException(status_code=404, detail="Resume source not found")
    path = settings.RESUME_ARTIFACT_DIR / f"{job.id}.tex"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Resume source not found")
    return FileResponse(
        path,
        media_type="application/x-tex",
        filename=f"resume-{job.target_id}.tex",
        headers={
            "Cache-Control": "private, no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@router.get("/jobs/{job_id}/download/tex")
def download_resume_tex(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_owned_compile_job(db, job_id, current_user.id)
    path = settings.RESUME_ARTIFACT_DIR / f"{job.id}.tex"
    if not path.is_file():
        raise HTTPException(status_code=409, detail="Resume source is not ready")
    return FileResponse(
        path,
        media_type="application/x-tex",
        filename=f"resume-{job.target_id}.tex",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/jobs/{job_id}/download/pdf")
def download_resume_pdf(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_owned_compile_job(db, job_id, current_user.id)
    if job.status != "succeeded":
        raise HTTPException(status_code=409, detail="Resume PDF is not ready")
    path = settings.RESUME_ARTIFACT_DIR / f"{job.id}.pdf"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Resume PDF artifact not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"resume-{job.target_id}.pdf",
        headers={"Cache-Control": "private, no-store"},
    )

import json
import logging
import os
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from backend.celery_app import celery_app
from backend.core.config import settings
from backend.db.database import SessionLocal
from backend.db.models import (
    JobTarget, ResumeCompileJob, ResumeProfile, TailoredBullet,
)
from backend.services.resume_render_service import resume_render_service
from backend.services.resume_selection_service import resume_selection_service


logger = logging.getLogger(__name__)
COMPILE_TIMEOUT_SECONDS = 20
POLL_INTERVAL_SECONDS = 0.1


def _wait_for_compiler(job_id: UUID, tex: str) -> dict[str, str]:
    compile_root = settings.RESUME_COMPILE_DIR
    inbox = compile_root / "inbox"
    responses = compile_root / "responses"
    inbox.mkdir(parents=True, exist_ok=True)
    responses.mkdir(parents=True, exist_ok=True)

    deadline = time.time() + COMPILE_TIMEOUT_SECONDS
    request_path = inbox / f"{job_id}.json"
    response_path = responses / f"{job_id}.json"
    temporary_path = inbox / f".{job_id}.{os.getpid()}.tmp"
    try:
        temporary_path.write_text(
            json.dumps(
                {
                    "job_id": str(job_id),
                    "tex": tex,
                    "deadline": deadline,
                }
            ),
            encoding="utf-8",
        )
        os.replace(temporary_path, request_path)
        while time.time() < deadline:
            if response_path.is_file():
                response = json.loads(response_path.read_text(encoding="utf-8"))
                response_path.unlink(missing_ok=True)
                if response.get("status") != "succeeded":
                    raise RuntimeError(
                        response.get("error") or "Tectonic compilation failed"
                    )
                return response
            time.sleep(POLL_INTERVAL_SECONDS)
        raise TimeoutError("Resume compilation exceeded 20 seconds")
    finally:
        temporary_path.unlink(missing_ok=True)
        request_path.unlink(missing_ok=True)


@celery_app.task(name="backend.tasks.resume_compile_tasks.compile_resume")
def compile_resume(job_id: str) -> dict[str, str]:
    db = SessionLocal()
    job = None
    try:
        job = db.get(ResumeCompileJob, UUID(job_id))
        if job is None:
            raise ValueError("Resume compile job not found")
        target = db.get(JobTarget, job.target_id)
        if target is None:
            raise ValueError("Resume target not found")
        profile = db.query(ResumeProfile).filter_by(user_id=job.user_id).first()
        if profile is None:
            raise ValueError("Resume profile not found")

        job.status = "running"
        job.error = None
        db.commit()

        selection = resume_selection_service.select(profile, target, top_n=20)
        if job.selected_project_ids is not None:
            projects_by_id = {
                str(entry["item"].id): entry
                for entry in selection["projects"]
            }
            selection["projects"] = [
                projects_by_id[project_id]
                for project_id in job.selected_project_ids
                if project_id in projects_by_id
            ]
        tailored_bullets = db.scalars(
            select(TailoredBullet).where(TailoredBullet.target_id == target.id)
        ).all()
        tex = resume_render_service.render(
            profile,
            selection=selection,
            sections=job.sections,
            tailored_bullets=tailored_bullets,
        )
        result = _wait_for_compiler(UUID(job_id), tex)

        job.status = "succeeded"
        job.error = None
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        if job is None:
            job = db.get(ResumeCompileJob, UUID(job_id))
        if job is not None:
            job.status = "failed"
            job.error = str(exc)[:4000] or "Resume compilation failed"
            db.commit()
        logger.exception("Resume compile job %s failed", job_id)
        raise
    finally:
        db.close()

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import JobTarget, ResumeProfile, TailoredBullet
from backend.services.bullet_guardrail import find_unverified_tokens
from backend.services.llm_service import LLMService, llm_service


def _job_keywords(target: JobTarget) -> list[str]:
    keywords = []
    seen = set()
    for keyword in (
        *(target.required_skills or []),
        *(target.preferred_skills or []),
        *(target.keywords or []),
    ):
        normalized = keyword.casefold()
        if normalized not in seen:
            seen.add(normalized)
            keywords.append(keyword)
    return keywords


class TailoringService:
    def __init__(self, llm: LLMService = llm_service) -> None:
        self.llm = llm

    def tailor_profile(
        self,
        db: Session,
        target: JobTarget,
        profile: ResumeProfile,
        project_ids: Iterable[UUID] | None = None,
    ) -> list[TailoredBullet]:
        if profile.user_id != target.user_id:
            raise ValueError("Job target does not belong to the resume profile owner")

        requested_ids = set(project_ids) if project_ids is not None else None
        projects = [
            project
            for project in (profile.projects or [])
            if requested_ids is None or project.id in requested_ids
        ]
        if requested_ids is not None and {project.id for project in projects} != requested_ids:
            raise ValueError("Selected projects must belong to the resume profile")

        keywords = _job_keywords(target)
        try:
            for project in projects:
                existing = db.scalars(
                    select(TailoredBullet).where(
                        TailoredBullet.target_id == target.id,
                        TailoredBullet.project_id == project.id,
                    )
                ).all()
                existing_originals = {item.original for item in existing}
                for original in project.bullets or []:
                    if original in existing_originals:
                        continue
                    result = self.llm.tailor_bullet(
                        original=original,
                        jd_keywords=keywords,
                        company_name=target.company_name,
                    )
                    unverified_tokens = find_unverified_tokens(
                        original,
                        result.rewritten,
                        project.tech_stack,
                    )
                    db.add(
                        TailoredBullet(
                            user_id=target.user_id,
                            target_id=target.id,
                            project_id=project.id,
                            original=result.original,
                            rewritten=result.rewritten,
                            keywords_used=result.keywords_used,
                            unverified_tokens=unverified_tokens,
                            status="unverified" if unverified_tokens else "pending",
                        )
                    )
                    existing_originals.add(original)
            db.commit()
        except Exception:
            db.rollback()
            raise

        if not projects:
            return []
        return db.scalars(
            select(TailoredBullet)
            .where(
                TailoredBullet.target_id == target.id,
                TailoredBullet.project_id.in_([project.id for project in projects]),
            )
            .order_by(TailoredBullet.project_id, TailoredBullet.id)
        ).all()


tailoring_service = TailoringService()

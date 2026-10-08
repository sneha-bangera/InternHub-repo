from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.target_schemas import TailoredBulletResult
from backend.db.database import Base
from backend.db.models import (
    JobTarget, Project, ResumeProfile, TailoredBullet, User,
)
from backend.services.llm_service import LLMService, LLMServiceError
from backend.services.resume_render_service import ResumeRenderService
from backend.services.tailoring_service import TailoringService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        yield db
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed_resume(db):
    user = User(
        id=uuid4(),
        email="tailor@example.com",
        hashed_password="test",
        full_name="Taylor",
    )
    profile = ResumeProfile(
        id=uuid4(),
        user_id=user.id,
        name="Taylor",
        email="tailor@example.com",
        links=[],
    )
    project = Project(
        id=uuid4(),
        profile_id=profile.id,
        title="API project",
        tech_stack=["Python"],
        bullets=["Built an API for student records."],
        start_date=date(2024, 1, 1),
    )
    target = JobTarget(
        id=uuid4(),
        user_id=user.id,
        company_name="Example Labs",
        jd_text="Build reliable services.",
        required_skills=["Python"],
        preferred_skills=["REST APIs"],
        keywords=["testing"],
    )
    db.add_all([user, profile, project, target])
    db.commit()
    return user, profile, project, target


def test_tailoring_service_persists_pending_results_and_is_idempotent(db_session):
    _, profile, project, target = _seed_resume(db_session)

    class FakeLLM:
        calls = []

        def tailor_bullet(self, **kwargs):
            self.calls.append(kwargs)
            return TailoredBulletResult(
                original=kwargs["original"],
                rewritten="Built a Python API for student records.",
                keywords_used=["Python"],
            )

    fake_llm = FakeLLM()
    service = TailoringService(fake_llm)

    rows = service.tailor_profile(db_session, target, profile)

    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].original == project.bullets[0]
    assert rows[0].keywords_used == ["Python"]
    assert fake_llm.calls == [
        {
            "original": project.bullets[0],
            "jd_keywords": ["Python", "REST APIs", "testing"],
            "company_name": "Example Labs",
        }
    ]

    rows[0].status = "accepted"
    db_session.commit()
    assert service.tailor_profile(db_session, target, profile)[0].status == "accepted"
    assert len(fake_llm.calls) == 1


@pytest.mark.parametrize(
    ("rewritten", "expected_token"),
    [
        ("Built an API with 50% faster processing.", "number: 50%"),
        ("Built a Kubernetes API for student records.", "technology: Kubernetes"),
        ("Built an API for Acme.", "proper_noun: Acme"),
    ],
)
def test_tailoring_service_marks_new_claims_unverified(
    db_session, rewritten, expected_token
):
    _, profile, _, target = _seed_resume(db_session)

    class FakeLLM:
        def tailor_bullet(self, original, **_kwargs):
            return TailoredBulletResult(
                original=original,
                rewritten=rewritten,
                keywords_used=[],
            )

    rows = TailoringService(FakeLLM()).tailor_profile(
        db_session, target, profile
    )

    assert len(rows) == 1
    assert rows[0].status == "unverified"
    assert expected_token in rows[0].unverified_tokens


def test_tailoring_service_rejects_cross_user_profile(db_session):
    _, profile, _, target = _seed_resume(db_session)
    profile.user_id = uuid4()
    db_session.commit()

    with pytest.raises(ValueError, match="does not belong"):
        TailoringService(SimpleNamespace()).tailor_profile(
            db_session, target, profile
        )


def test_renderer_includes_only_accepted_or_edited_tailored_bullets():
    project_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        title="API project",
        tech_stack=[],
        bullets=["Original profile bullet must not appear"],
    )
    profile = SimpleNamespace(
        name="Taylor",
        links=[],
        projects=[project],
        education=[],
        skills=[],
        certificates=[],
    )
    tailored = [
        SimpleNamespace(
            project_id=project_id,
            original="Original profile bullet must not appear",
            rewritten="Pending rewrite must not appear",
            status="pending",
        ),
        SimpleNamespace(
            project_id=project_id,
            original="Original profile bullet must not appear",
            rewritten="Rejected rewrite must not appear",
            status="rejected",
        ),
        SimpleNamespace(
            project_id=project_id,
            original="Original profile bullet must not appear",
            rewritten="Accepted rewrite",
            status="accepted",
        ),
        SimpleNamespace(
            project_id=project_id,
            original="Original profile bullet must not appear",
            rewritten="Edited rewrite",
            status="edited",
        ),
        SimpleNamespace(
            project_id=project_id,
            original="Removed from the profile",
            rewritten="Stale accepted rewrite",
            status="accepted",
        ),
    ]

    rendered = ResumeRenderService().render(profile, tailored_bullets=tailored)

    assert "Accepted rewrite" in rendered
    assert "Edited rewrite" in rendered
    assert "Pending rewrite" not in rendered
    assert "Rejected rewrite" not in rendered
    assert "Stale accepted rewrite" not in rendered
    assert "Original profile bullet" not in rendered


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "original": "Built an API.",
                "rewritten": "Built a Java API.",
                "keywords_used": ["Java"],
            },
            "invalid keyword",
        ),
        (
            {
                "original": "Different source.",
                "rewritten": "Built an API.",
                "keywords_used": [],
            },
            "preserve the original",
        ),
        (
            {
                "original": "Built an API.",
                "rewritten": "Built an API.\nAdded tests.\nImproved docs.",
                "keywords_used": [],
            },
            "two lines",
        ),
    ],
)
def test_llm_service_rejects_unfaithful_or_invalid_rewrites(
    monkeypatch, payload, message
):
    from backend.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "test-key")
    service = LLMService()
    monkeypatch.setattr(
        service,
        "_request_tailored_bullet",
        lambda *_args: TailoredBulletResult.model_validate(payload),
    )

    with pytest.raises(LLMServiceError, match=message):
        service.tailor_bullet(
            "Built an API.",
            ["Python"],
            "Example Labs",
        )

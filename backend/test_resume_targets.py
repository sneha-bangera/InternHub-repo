from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.routes import resume_targets
from backend.api.target_schemas import JDParseResult, TailoredBulletResult
from backend.api.routes import resume_profile
from backend.auth.dependencies import get_current_user
from backend.db.database import Base, get_db
from backend.db.models import Listing, ResumeCompileJob, User


@pytest.fixture
def client() -> Generator[tuple[TestClient, UUID, UUID, UUID], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    owner_id, other_user_id, listing_id = uuid4(), uuid4(), uuid4()
    with test_session() as db:
        db.add_all([
            User(
                id=owner_id, email="owner@example.com", hashed_password="test",
                full_name="Owner",
            ),
            User(
                id=other_user_id, email="other@example.com", hashed_password="test",
                full_name="Other",
            ),
            Listing(
                id=listing_id, title="Backend Intern", company="Example Co",
                description="Build APIs and services.", skills_required="Python, SQL",
                apply_url="https://example.com/apply", source_platform="linkedin",
                is_active=True,
            ),
        ])
        db.commit()

    app = FastAPI()
    app.include_router(resume_targets.router)
    app.include_router(resume_profile.router)
    app.state.test_session = test_session

    def override_get_db() -> Generator[Session, None, None]:
        with test_session() as db:
            yield db

    def override_get_current_user(
        x_user_id: UUID = Header(),
        db: Session = Depends(override_get_db),
    ) -> User:
        user = db.get(User, x_user_id)
        if user is None:
            pytest.fail("Test user header does not identify a stored user")
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client, owner_id, other_user_id, listing_id
    Base.metadata.drop_all(engine)
    engine.dispose()


def _headers(user_id: UUID) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


def test_parse_persists_and_scopes_job_target(client, monkeypatch):
    api, owner_id, other_user_id, _ = client
    calls = []

    def mock_parse(jd_text: str) -> JDParseResult:
        calls.append(jd_text)
        return JDParseResult(
            role_title="Backend Intern",
            seniority="Intern",
            required_skills=["Python"],
            preferred_skills=["Docker"],
            keywords=["REST APIs", "testing"],
        )

    monkeypatch.setattr(resume_targets.llm_service, "parse_job_description", mock_parse)
    response = api.post(
        "/api/resume/jd/parse",
        json={
            "jd_text": "Build and maintain APIs using Python.",
            "company_name": "Example Co",
        },
        headers=_headers(owner_id),
    )
    assert response.status_code == 201
    target = response.json()
    assert calls == ["Build and maintain APIs using Python."]
    assert target["role_title"] == "Backend Intern"
    assert target["required_skills"] == ["Python"]
    assert target["preferred_skills"] == ["Docker"]
    assert target["keywords"] == ["REST APIs", "testing"]

    assert [item["id"] for item in api.get(
        "/api/resume/targets", headers=_headers(owner_id)
    ).json()] == [target["id"]]
    assert api.get(
        f"/api/resume/targets/{target['id']}", headers=_headers(owner_id)
    ).status_code == 200
    assert api.get(
        f"/api/resume/targets/{target['id']}", headers=_headers(other_user_id)
    ).status_code == 404
    assert api.get(
        "/api/resume/targets", headers=_headers(other_user_id)
    ).json() == []

    update = api.patch(
        f"/api/resume/targets/{target['id']}",
        json={"keywords": ["API design"], "preferred_skills": ["Docker", "Redis"]},
        headers=_headers(owner_id),
    )
    assert update.status_code == 200
    assert update.json()["keywords"] == ["API design"]
    assert update.json()["preferred_skills"] == ["Docker", "Redis"]
    assert api.patch(
        f"/api/resume/targets/{target['id']}",
        json={"keywords": ["intrusion"]},
        headers=_headers(other_user_id),
    ).status_code == 404


def test_listing_input_loads_job_description_before_parsing(client, monkeypatch):
    api, owner_id, _, listing_id = client
    received_text = []

    def mock_parse(jd_text: str) -> JDParseResult:
        received_text.append(jd_text)
        return JDParseResult(required_skills=["Python", "SQL"])

    monkeypatch.setattr(resume_targets.llm_service, "parse_job_description", mock_parse)
    response = api.post(
        "/api/resume/jd/parse",
        json={"listing_id": str(listing_id)},
        headers=_headers(owner_id),
    )
    assert response.status_code == 201
    target = response.json()
    assert target["listing_id"] == str(listing_id)
    assert target["company_name"] == "Example Co"
    assert target["role_title"] == "Backend Intern"
    assert "Build APIs and services." in received_text[0]
    assert "Python, SQL" in received_text[0]


def test_tailored_bullet_review_routes_persist_and_enforce_ownership(
    client, monkeypatch
):
    api, owner_id, other_user_id, _ = client
    profile = api.post(
        "/api/resume/profile",
        json={"name": "Resume Owner"},
        headers=_headers(owner_id),
    )
    assert profile.status_code == 201
    project = api.post(
        "/api/resume/profile/projects",
        json={
            "title": "Student API",
            "tech_stack": ["Python"],
            "bullets": ["Built an API for student records."],
        },
        headers=_headers(owner_id),
    )
    assert project.status_code == 201
    monkeypatch.setattr(
        resume_targets.llm_service,
        "parse_job_description",
        lambda _text: JDParseResult(keywords=["Python"]),
    )
    target = api.post(
        "/api/resume/jd/parse",
        json={"jd_text": "Build APIs with Python.", "company_name": "Example"},
        headers=_headers(owner_id),
    )
    assert target.status_code == 201
    target_id = target.json()["id"]
    monkeypatch.setattr(
        resume_targets.tailoring_service.llm,
        "tailor_bullet",
        lambda original, jd_keywords, company_name: TailoredBulletResult(
            original=original,
            rewritten="Built a Python API for student records.",
            keywords_used=["Python"],
        ),
    )

    tailored_url = f"/api/resume/targets/{target_id}/tailored-bullets"
    tailored = api.post(tailored_url, headers=_headers(owner_id))
    assert tailored.status_code == 200
    assert len(tailored.json()) == 1
    bullet = tailored.json()[0]
    assert bullet["status"] == "pending"
    assert bullet["project_id"] == project.json()["id"]
    assert api.get(tailored_url, headers=_headers(owner_id)).json() == tailored.json()
    assert api.get(tailored_url, headers=_headers(other_user_id)).status_code == 404

    reviewed = api.patch(
        f"{tailored_url}/{bullet['id']}",
        json={
            "status": "edited",
            "rewritten": "Built and tested a Python API for student records.",
        },
        headers=_headers(owner_id),
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "edited"
    assert reviewed.json()["unverified_tokens"] == []
    assert reviewed.json()["rewritten"].startswith("Built and tested")
    assert api.patch(
        f"{tailored_url}/{bullet['id']}",
        json={"status": "accepted"},
        headers=_headers(other_user_id),
    ).status_code == 404
    assert api.patch(
        f"{tailored_url}/{bullet['id']}",
        json={"status": "edited", "rewritten": "Too long\n" * 3},
        headers=_headers(owner_id),
    ).status_code == 422
    unverified = api.patch(
        f"{tailored_url}/{bullet['id']}",
        json={
            "status": "edited",
            "rewritten": "Built an API that processed 50% more records.",
        },
        headers=_headers(owner_id),
    )
    assert unverified.status_code == 200
    assert unverified.json()["status"] == "unverified"
    assert unverified.json()["unverified_tokens"] == ["number: 50%"]


def test_compile_job_endpoints_enforce_ownership_and_serve_artifacts(
    client, monkeypatch, tmp_path: Path
):
    api, owner_id, other_user_id, _ = client
    profile_response = api.post(
        "/api/resume/profile",
        json={"name": "Resume Owner", "email": "owner@example.com"},
        headers=_headers(owner_id),
    )
    assert profile_response.status_code == 201

    monkeypatch.setattr(
        resume_targets.llm_service,
        "parse_job_description",
        lambda _text: JDParseResult(role_title="Developer"),
    )
    target_response = api.post(
        "/api/resume/jd/parse",
        json={"jd_text": "Build applications.", "company_name": "Example"},
        headers=_headers(owner_id),
    )
    assert target_response.status_code == 201
    target_id = target_response.json()["id"]

    queued = []
    monkeypatch.setattr(
        resume_targets.celery_app,
        "send_task",
        lambda *args, **kwargs: queued.append((args, kwargs))
        or SimpleNamespace(id=kwargs["task_id"]),
    )
    compile_response = api.post(
        f"/api/resume/targets/{target_id}/compile",
        json={
            "sections": {"skills": False, "projects": False},
            "selected_project_ids": [],
        },
        headers=_headers(owner_id),
    )
    assert compile_response.status_code == 202
    job = compile_response.json()
    assert job["status"] == "queued"
    assert queued[0][0][0] == "backend.tasks.resume_compile_tasks.compile_resume"
    assert queued[0][1]["task_id"] == job["id"]
    with api.app.state.test_session() as db:
        stored_job = db.get(ResumeCompileJob, UUID(job["id"]))
        assert stored_job.sections["skills"] is False
        assert stored_job.sections["education"] is True
        assert stored_job.selected_project_ids == []

    job_url = f"/api/resume/jobs/{job['id']}"
    assert api.get(job_url, headers=_headers(owner_id)).status_code == 200
    assert api.get(job_url, headers=_headers(other_user_id)).status_code == 404
    assert api.get(
        f"{job_url}/download/pdf", headers=_headers(owner_id)
    ).status_code == 409
    assert api.get(
        f"{job_url}/download/tex", headers=_headers(owner_id)
    ).status_code == 409

    with api.app.state.test_session() as db:
        compile_job = db.get(ResumeCompileJob, UUID(job["id"]))
        compile_job.status = "succeeded"
        db.commit()
    monkeypatch.setattr(resume_targets.settings, "RESUME_ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(
        resume_targets.settings, "PUBLIC_API_URL", "https://api.example.test"
    )
    (tmp_path / f"{job['id']}.tex").write_text(r"\documentclass{article}", encoding="utf-8")
    (tmp_path / f"{job['id']}.pdf").write_bytes(b"%PDF-test")

    tex_response = api.get(
        f"{job_url}/download/tex", headers=_headers(owner_id)
    )
    pdf_response = api.get(
        f"{job_url}/download/pdf", headers=_headers(owner_id)
    )
    assert tex_response.status_code == 200
    assert tex_response.text == r"\documentclass{article}"
    assert pdf_response.status_code == 200
    assert pdf_response.content == b"%PDF-test"
    assert api.get(
        f"{job_url}/download/pdf", headers=_headers(other_user_id)
    ).status_code == 404

    snippet = api.get(f"{job_url}/overleaf", headers=_headers(owner_id))
    assert snippet.status_code == 200
    assert snippet.json()["snip_name"].endswith(".tex")
    snippet_uri = snippet.json()["snip_uri"]
    signed_source = api.get(snippet_uri.replace("https://api.example.test", ""))
    assert signed_source.status_code == 200
    assert signed_source.text == r"\documentclass{article}"

    invalid_signature = snippet_uri.replace("signature=", "signature=bad")
    assert api.get(
        invalid_signature.replace("https://api.example.test", "")
    ).status_code == 403

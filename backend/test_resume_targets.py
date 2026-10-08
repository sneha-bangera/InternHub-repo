from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.routes import resume_targets
from backend.api.target_schemas import JDParseResult
from backend.auth.dependencies import get_current_user
from backend.db.database import Base, get_db
from backend.db.models import Listing, User


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

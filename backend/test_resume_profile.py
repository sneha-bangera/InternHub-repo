from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.routes.resume_profile import router
from backend.auth.dependencies import get_current_user
from backend.db.database import Base, get_db
from backend.db.models import User


@pytest.fixture
def client() -> Generator[tuple[TestClient, UUID, UUID], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with test_session() as db:
        user_ids = [uuid4(), uuid4()]
        for index, user_id in enumerate(user_ids):
            db.add(
                User(
                    id=user_id,
                    email=f"user{index}@example.com",
                    hashed_password="test",
                    full_name=f"User {index}",
                )
            )
        db.commit()

    app = FastAPI()
    app.include_router(router)

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
        yield test_client, user_ids[0], user_ids[1]
    Base.metadata.drop_all(engine)
    engine.dispose()


def _headers(user_id: UUID) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


def test_profile_crud_is_scoped_to_authenticated_user(client):
    api, owner_id, other_user_id = client
    body = {
        "name": "Resume Name",
        "email": "resume@example.com",
        "phone": "+1-555-0100",
        "links": ["https://example.com"],
    }

    created = api.post("/api/resume/profile", json=body, headers=_headers(owner_id))
    assert created.status_code == 201
    profile = created.json()
    assert profile["user_id"] == str(owner_id)

    assert api.get(
        "/api/resume/profile", headers=_headers(owner_id)
    ).json()["name"] == "Resume Name"
    assert api.get(
        "/api/resume/profile", headers=_headers(other_user_id)
    ).status_code == 404

    updated = api.patch(
        "/api/resume/profile",
        json={"name": "Updated Name"},
        headers=_headers(owner_id),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Name"
    assert api.patch(
        "/api/resume/profile",
        json={"name": None},
        headers=_headers(owner_id),
    ).status_code == 422

    assert api.post(
        "/api/resume/profile", json=body, headers=_headers(owner_id)
    ).status_code == 409
    assert api.delete(
        "/api/resume/profile", headers=_headers(other_user_id)
    ).status_code == 404
    assert api.delete(
        "/api/resume/profile", headers=_headers(owner_id)
    ).status_code == 204
    assert api.get(
        "/api/resume/profile", headers=_headers(owner_id)
    ).status_code == 404


@pytest.mark.parametrize(
    ("path", "payload", "updated_value"),
    [
        ("education", {"institution": "Example University"}, "degree"),
        (
            "projects",
            {"title": "Portfolio", "tech_stack": ["Python"], "bullets": ["Built app"]},
            "title",
        ),
        ("skills", {"name": "Python", "category": "Programming"}, "proficiency"),
        ("certificates", {"name": "Cloud Cert"}, "issuer"),
    ],
)
def test_resume_item_crud_and_ownership(client, path, payload, updated_value):
    api, owner_id, other_user_id = client
    profile_response = api.post(
        "/api/resume/profile",
        json={"name": "Owner"},
        headers=_headers(owner_id),
    )
    assert profile_response.status_code == 201

    created = api.post(
        f"/api/resume/profile/{path}", json=payload, headers=_headers(owner_id)
    )
    assert created.status_code == 201
    item = created.json()
    item_id = item["id"]
    assert item["profile_id"] == profile_response.json()["id"]

    assert len(
        api.get(
            f"/api/resume/profile/{path}", headers=_headers(owner_id)
        ).json()
    ) == 1
    assert api.get(
        f"/api/resume/profile/{path}/{item_id}", headers=_headers(owner_id)
    ).status_code == 200
    assert api.get(
        f"/api/resume/profile/{path}", headers=_headers(other_user_id)
    ).status_code == 404
    assert api.get(
        f"/api/resume/profile/{path}/{item_id}",
        headers=_headers(other_user_id),
    ).status_code == 404

    value = "Updated"
    update_from_other_user = api.patch(
        f"/api/resume/profile/{path}/{item_id}",
        json={updated_value: value},
        headers=_headers(other_user_id),
    )
    assert update_from_other_user.status_code == 404

    updated = api.patch(
        f"/api/resume/profile/{path}/{item_id}",
        json={updated_value: value},
        headers=_headers(owner_id),
    )
    assert updated.status_code == 200
    assert updated.json()[updated_value] == value

    assert api.delete(
        f"/api/resume/profile/{path}/{item_id}",
        headers=_headers(other_user_id),
    ).status_code == 404
    assert api.delete(
        f"/api/resume/profile/{path}/{item_id}",
        headers=_headers(owner_id),
    ).status_code == 204
    assert api.get(
        f"/api/resume/profile/{path}", headers=_headers(owner_id)
    ).json() == []

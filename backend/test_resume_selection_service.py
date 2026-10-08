from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest

from backend.services import resume_selection_service as selection_module


class FakeModel:
    def __init__(self):
        self.calls = []

    def encode(self, text, **_kwargs):
        self.calls.append(text)
        tokens = text.casefold().split()
        return np.array(
            [len(tokens), sum(len(token) for token in tokens), 1.0],
            dtype=np.float32,
        )


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, _ttl, value):
        self.values[key] = value


def _target(user_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        role_title="Backend Engineer",
        seniority="Junior",
        jd_text="Build Python APIs with PostgreSQL",
        required_skills=["Python", "SQL"],
        preferred_skills=["Docker"],
        keywords=["REST API"],
    )


def _item(profile_id, **fields):
    return SimpleNamespace(id=uuid4(), profile_id=profile_id, **fields)


@pytest.fixture
def fakes(monkeypatch):
    model = FakeModel()
    cache = FakeRedis()
    monkeypatch.setattr(selection_module, "_get_model", lambda: model)
    monkeypatch.setattr(
        selection_module,
        "cosine_similarity",
        lambda first, second: float(
            np.dot(first, second) / (np.linalg.norm(first) * np.linalg.norm(second))
        ),
    )
    monkeypatch.setattr(selection_module, "_get_redis_client", lambda: cache)
    return model, cache


def test_select_ranks_profile_items_and_limits_projects(fakes):
    user_id, profile_id = uuid4(), uuid4()
    profile = SimpleNamespace(
        id=profile_id,
        user_id=user_id,
        projects=[
            _item(
                profile_id,
                title="Python API",
                tech_stack=["Python", "PostgreSQL"],
                bullets=["Built REST API"],
            ),
            _item(
                profile_id,
                title="Illustration",
                tech_stack=["Watercolor"],
                bullets=["Created artwork"],
            ),
            _item(
                profile_id,
                title="Docker service",
                tech_stack=["Docker"],
                bullets=["Containerized a backend"],
            ),
        ],
        skills=[
            _item(profile_id, name="Python", category="Programming", proficiency="Advanced"),
            _item(profile_id, name="SQL", category="Database", proficiency="Intermediate"),
        ],
        certificates=[
            _item(profile_id, name="Python Developer", issuer="Example Institute")
        ],
    )

    result = selection_module.ResumeSelectionService().select(
        profile, _target(user_id), top_n=1
    )

    assert len(result["projects"]) == 1
    assert result["projects"][0]["item"].title == "Python API"
    assert {"Python", "REST API"} <= set(
        result["projects"][0]["matched_keywords"]
    )
    assert [entry["item"].name for entry in result["skills"]] == ["Python", "SQL"]
    assert result["skills"][0]["matched_keywords"][0] == "Python"
    assert len(result["certificates"]) == 1
    assert result["certificates"][0]["matched_keywords"] == ["Python"]
    assert all(
        0.0 <= entry["score"] <= 1.0
        for category in ("projects", "skills", "certificates")
        for entry in result[category]
    )
    assert result["keyword_coverage"]["before"]["score"] == 1.0
    assert result["keyword_coverage"]["after"]["score"] < 1.0
    assert "Docker" in result["keyword_coverage"]["after"]["missing_keywords"]


def test_selection_only_returns_items_belonging_to_profile(fakes):
    user_id, profile_id = uuid4(), uuid4()
    profile = SimpleNamespace(
        id=profile_id,
        user_id=user_id,
        projects=[_item(uuid4(), title="Foreign", tech_stack=[], bullets=[])],
        skills=[_item(uuid4(), name="Foreign skill", category=None, proficiency=None)],
        certificates=[_item(uuid4(), name="Foreign cert", issuer=None)],
    )

    result = selection_module.ResumeSelectionService().select(profile, _target(user_id))

    assert result["projects"] == []
    assert result["skills"] == []
    assert result["certificates"] == []
    assert len(fakes[0].calls) == 1


def test_embeddings_are_reused_only_for_identical_content(fakes):
    service = selection_module.ResumeSelectionService()
    item_id = str(uuid4())

    service._embedding("projects", item_id, "Python API")
    service._embedding("projects", item_id, "Python API")
    service._embedding("projects", item_id, "Python API with PostgreSQL")

    assert len(fakes[0].calls) == 2
    assert len(fakes[1].values) == 2


def test_rejects_target_owned_by_another_user(fakes):
    profile = SimpleNamespace(id=uuid4(), user_id=uuid4(), projects=[], skills=[], certificates=[])

    with pytest.raises(ValueError, match="does not belong"):
        selection_module.ResumeSelectionService().select(profile, _target(uuid4()))


def test_coverage_weights_required_keywords_above_preferred():
    keywords = [
        selection_module._Keyword("Python", "python", 2),
        selection_module._Keyword("JavaScript", "javascript", 2),
        selection_module._Keyword("Docker", "docker", 1),
    ]

    coverage = selection_module._coverage(
        keywords,
        ["Python projects"],
    )

    assert coverage == {
        "score": 0.4,
        "matched_keywords": ["Python"],
        "missing_keywords": ["JavaScript", "Docker"],
    }


@pytest.mark.parametrize(
    ("jd_keyword", "profile_text"),
    [
        ("JavaScript", "Experience with JS"),
        ("js", "JavaScript applications"),
        ("Kubernetes", "Deployed with k8s"),
        ("k8s", "Managed Kubernetes clusters"),
        ("API", "Built APIs"),
    ],
)
def test_keyword_normalization_handles_aliases_and_lemmas(jd_keyword, profile_text):
    keyword = selection_module._Keyword(
        jd_keyword, selection_module._normalize_text(jd_keyword), 1
    )

    coverage = selection_module._coverage([keyword], [profile_text])

    assert coverage["score"] == 1.0
    assert coverage["matched_keywords"] == [jd_keyword]
    assert coverage["missing_keywords"] == []


def test_duplicate_aliases_count_once_and_required_weight_wins():
    target = _target(uuid4())
    target.required_skills = ["JavaScript"]
    target.preferred_skills = ["js"]
    target.keywords = ["Kubernetes", "k8s"]

    keywords = selection_module._target_keywords(target)

    assert [(keyword.display, keyword.weight) for keyword in keywords] == [
        ("JavaScript", 2),
        ("Kubernetes", 1),
    ]

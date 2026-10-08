import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_TTL = 86_400
CACHE_PREFIX = "resume_selection_embed"
KEYWORD_BOOST = 0.1
REQUIRED_KEYWORD_WEIGHT = 2
PREFERRED_KEYWORD_WEIGHT = 1

_ALIASES = {
    "js": "javascript",
    "k8s": "kubernetes",
    "apis": "api",
}


@dataclass(frozen=True)
class _Keyword:
    display: str
    normalized: str
    weight: int


def _lemma(token: str) -> str:
    """Apply conservative English inflection rules without external language data."""
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("ing"):
        stem = token[:-3]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if len(token) > 3 and token.endswith("ed"):
        stem = token[:-2]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if len(token) > 3 and token.endswith("s") and not token.endswith(
        ("ss", "us", "is", "es")
    ):
        return token[:-1]
    return token


def _normalize_text(text: str) -> str:
    tokens = re.findall(r"[\w+#.]+", text.casefold(), flags=re.UNICODE)
    normalized = []
    for token in tokens:
        alias = _ALIASES.get(token)
        if alias is not None:
            normalized.append(alias)
            continue
        lemma = _lemma(token)
        normalized.append(_ALIASES.get(lemma, lemma))
    return " ".join(normalized)


def _target_keywords(target: Any) -> list[_Keyword]:
    candidates = [
        *((value, REQUIRED_KEYWORD_WEIGHT) for value in (target.required_skills or [])),
        *((value, PREFERRED_KEYWORD_WEIGHT) for value in (target.preferred_skills or [])),
        *((value, PREFERRED_KEYWORD_WEIGHT) for value in (target.keywords or [])),
    ]
    keywords: dict[str, _Keyword] = {}
    for value, weight in candidates:
        display = value.strip()
        normalized = _normalize_text(display)
        if not normalized:
            continue
        current = keywords.get(normalized)
        if current is None or weight > current.weight:
            keywords[normalized] = _Keyword(display, normalized, weight)
    return list(keywords.values())


def _get_model():
    from nlp.matcher import _get_model as get_model

    return get_model()


def _get_redis_client():
    from backend.core.redis_client import redis_client

    return redis_client


def cosine_similarity(first: np.ndarray, second: np.ndarray) -> float:
    from nlp.matcher import cosine_similarity as compare

    return compare(first, second)


def _item_text(item: Any, category: str) -> str:
    if category == "projects":
        fields = [item.title, *(item.tech_stack or []), *(item.bullets or [])]
    elif category == "skills":
        fields = [item.name, item.category, item.proficiency]
    else:
        fields = [item.name, item.issuer]
    return " ".join(str(field) for field in fields if field).strip()


def _matched_keywords(item: Any, category: str, target_terms: list[str]) -> list[str]:
    normalized_item_text = f" {_normalize_text(_item_text(item, category))} "
    return [
        term
        for term in target_terms
        if f" {_normalize_text(term)} " in normalized_item_text
    ]


def _coverage(
    keywords: list[_Keyword], contents: list[str]
) -> dict[str, Any]:
    normalized_content = " ".join(_normalize_text(text) for text in contents)
    normalized_content = f" {normalized_content} "
    matched = [
        keyword
        for keyword in keywords
        if f" {keyword.normalized} " in normalized_content
    ]
    total_weight = sum(keyword.weight for keyword in keywords)
    matched_weight = sum(keyword.weight for keyword in matched)
    return {
        "score": round(matched_weight / total_weight, 4) if total_weight else 0.0,
        "matched_keywords": [keyword.display for keyword in matched],
        "missing_keywords": [
            keyword.display for keyword in keywords if keyword not in matched
        ],
    }


class ResumeSelectionService:
    """Ranks the contents of one resume profile against one job target."""

    def select(self, profile: Any, target: Any, top_n: int = 4) -> dict[str, Any]:
        if top_n < 0:
            raise ValueError("top_n must be non-negative")
        if profile.user_id != target.user_id:
            raise ValueError("Job target does not belong to the resume profile owner")

        keywords = _target_keywords(target)
        terms = [keyword.display for keyword in keywords]
        target_text = " ".join(
            part
            for part in (
                target.role_title or "",
                target.seniority or "",
                target.jd_text or "",
                *(target.required_skills or []),
                *(target.preferred_skills or []),
                *(target.keywords or []),
            )
            if part
        ).strip()
        target_embedding = self._embedding(
            "target", str(target.id), target_text
        )

        ranked = {}
        all_contents = []
        for category in ("projects", "skills", "certificates"):
            items = [
                item
                for item in (getattr(profile, category, None) or [])
                if item.profile_id == profile.id
            ]
            scored = []
            for item in items:
                text = _item_text(item, category)
                all_contents.append(text)
                matched = _matched_keywords(item, category, terms)
                embedding = self._embedding(category, str(item.id), text)
                similarity = max(
                    0.0,
                    min(1.0, cosine_similarity(target_embedding, embedding)),
                )
                overlap = len(matched) / len(terms) if terms else 0.0
                score = min(1.0, similarity + KEYWORD_BOOST * overlap)
                scored.append(
                    {
                        "item": item,
                        "score": round(score, 4),
                        "matched_keywords": matched,
                    }
                )
            scored.sort(key=lambda result: result["score"], reverse=True)
            ranked[category] = scored[:top_n] if category == "projects" else scored
        selected_contents = [
            _item_text(entry["item"], category)
            for category, entries in ranked.items()
            for entry in entries
        ]
        ranked["keyword_coverage"] = {
            "before": _coverage(keywords, all_contents),
            "after": _coverage(keywords, selected_contents),
        }
        return ranked

    @staticmethod
    def _embedding(category: str, item_id: str, content: str) -> np.ndarray:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        cache_key = f"{CACHE_PREFIX}:{category}:{item_id}:{digest}"

        try:
            cached = _get_redis_client().get(cache_key)
        except Exception as exc:
            logger.warning("Redis read error for %s: %s", cache_key, exc)
            cached = None
        if cached:
            try:
                return np.asarray(json.loads(cached), dtype=np.float32)
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid cached embedding for %s", cache_key)

        embedding = _get_model().encode(
            content, convert_to_numpy=True, show_progress_bar=False
        )
        try:
            _get_redis_client().setex(
                cache_key, EMBEDDING_TTL, json.dumps(np.asarray(embedding).tolist())
            )
        except Exception as exc:
            logger.warning("Redis write error for %s: %s", cache_key, exc)
        return np.asarray(embedding, dtype=np.float32)


resume_selection_service = ResumeSelectionService()

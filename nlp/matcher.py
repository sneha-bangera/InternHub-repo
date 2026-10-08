"""
NLP Skill Matcher
-----------------
1. Loads sentence-transformers (all-MiniLM-L6-v2) to embed text
2. Embeds the user's skill profile as a single string
3. Embeds each listing's title + skills_required + description
4. Computes cosine similarity → match_score (0.0 - 1.0)
5. Returns listings sorted by match_score descending

Model is loaded once at module level (cached for the process lifetime).
"""
import logging
from functools import lru_cache
import json
from xml.parsers.expat import model

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.core.redis_client import redis_client

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_TTL = 86_400          # 24 hours in seconds
CACHE_PREFIX = "listing_embed"

@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load model once and cache it."""
    logger.info(f"Loading sentence-transformer model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    logger.info("Model loaded successfully")
    return model


def _build_listing_text(listing) -> str:
    """Combine listing fields into a single string for embedding."""
    parts = [
        listing.title or "",
        listing.company or "",
        listing.skills_required or "",
        listing.description or "",
        listing.location or "",
    ]
    return " ".join(p for p in parts if p).strip()


def _build_user_text(skills: list) -> str:
    """Convert user skill objects into a single string for embedding."""
    if not skills:
        return ""
    skill_parts = []
    for s in skills:
        # Weight advanced skills more by repeating them
        text = s.skill
        if s.proficiency == "advanced":
            text = f"{s.skill} {s.skill} {s.skill}"
        elif s.proficiency == "intermediate":
            text = f"{s.skill} {s.skill}"
        skill_parts.append(text)
    return " ".join(skill_parts)


def _get_listing_embedding(listing) -> np.ndarray:
    """
    Return the embedding for a listing.
    1. Check Redis — if found, deserialize and return (fast path, ~1ms).
    2. If miss — compute via model.encode(), store in Redis with TTL, return.
    """
    cache_key = f"{CACHE_PREFIX}:{listing.id}"

    #Cache hit 
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return np.array(json.loads(cached), dtype=np.float32)
    except Exception as e:
        # Redis unavailable — fall through to recompute
        logger.warning(f"Redis read error for {cache_key}: {e}")

    #Cache miss — compute and store 
    model = _get_model()
    text = _build_listing_text(listing)
    embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)

    try:
        redis_client.setex(cache_key, EMBEDDING_TTL, json.dumps(embedding.tolist()))
        logger.debug(f"Cached embedding for listing {listing.id}")
    except Exception as e:
        # Store failure is non-fatal — we still have the embedding in memory
        logger.warning(f"Redis write error for {cache_key}: {e}")

    return embedding


def invalidate_listing_embedding(listing_id: str) -> None:
    """
    Delete a listing's cached embedding.
    Call this from crud.upsert_listing() so stale embeddings
    don't persist after a scraper run updates the listing content.
    """
    try:
        redis_client.delete(f"{CACHE_PREFIX}:{listing_id}")
        logger.debug(f"Invalidated embedding cache for listing {listing_id}")
    except Exception as e:
        logger.warning(f"Redis delete error for listing {listing_id}: {e}")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def rank_listings(listings: list, user_skills: list) -> list[tuple]:
    """
    Score and rank listings against a user's skill profile.

    Args:
        listings: list of Listing ORM objects
        user_skills: list of UserSkill ORM objects

    Returns:
        List of (listing, match_score) tuples sorted by score descending.
        If user has no skills, returns all listings with score 0.0.
    
    Performance:
        Cold cache  — first request computes + stores all embeddings (~5-8s)
        Warm cache  — subsequent requests fetch from Redis + compute similarity (<200ms)
    """
    if not listings:
        return []

    if not user_skills:
        logger.info("No user skills — returning listings with score 0.0")
        return [(listing, 0.0) for listing in listings]

    model = _get_model()

    # Build user profile text
    user_text = _build_user_text(user_skills)
    logger.info(f"User profile text: '{user_text[:100]}...'")
    user_embedding = model.encode(user_text, convert_to_numpy=True, show_progress_bar=False)

    # Build listing texts
    # listing_texts = [_build_listing_text(l) for l in listings]

    # Embed everything in one batch (fast)
    # all_texts = [user_text] + listing_texts
    # logger.info(f"Embedding {len(all_texts)} texts...")
    # embeddings = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=False)

    # user_embedding = embeddings[0]
    # listing_embeddings = embeddings[1:]

    # Score each listing
    cache_hits = 0
    cache_misses = 0
    scored = []

    # for listing, embedding in zip(listings, listing_embeddings):
    #     score = cosine_similarity(user_embedding, embedding)
    #     # Clamp to [0, 1]
    #     score = max(0.0, min(1.0, score))
    #     scored.append((listing, round(score, 4)))

    # Sort by score descending
    # scored.sort(key=lambda x: x[1], reverse=True)
    # logger.info(f"Ranked {len(scored)} listings. Top score: {scored[0][1] if scored else 'N/A'}")
    # return scored

    for listing in listings:
        cache_key = f"{CACHE_PREFIX}:{listing.id}"
        cached = None

        try:
            cached = redis_client.get(cache_key)
        except Exception:
            pass

        if cached:
            embedding = np.array(json.loads(cached), dtype=np.float32)
            cache_hits += 1
        else:
            text = _build_listing_text(listing)
            embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
            try:
                redis_client.setex(cache_key, EMBEDDING_TTL, json.dumps(embedding.tolist()))
            except Exception:
                pass
            cache_misses += 1

        score = cosine_similarity(user_embedding, embedding)
        score = max(0.0, min(1.0, score))
        scored.append((listing, round(score, 4)))

    logger.info(
        f"Ranked {len(scored)} listings — "
        f"cache hits: {cache_hits}, misses: {cache_misses}. "
        f"Top score: {scored[0][1] if scored else 'N/A'}"
    )

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

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

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"


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

    # Build listing texts
    listing_texts = [_build_listing_text(l) for l in listings]

    # Embed everything in one batch (fast)
    all_texts = [user_text] + listing_texts
    logger.info(f"Embedding {len(all_texts)} texts...")
    embeddings = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=False)

    user_embedding = embeddings[0]
    listing_embeddings = embeddings[1:]

    # Score each listing
    scored = []
    for listing, embedding in zip(listings, listing_embeddings):
        score = cosine_similarity(user_embedding, embedding)
        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))
        scored.append((listing, round(score, 4)))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    logger.info(f"Ranked {len(scored)} listings. Top score: {scored[0][1] if scored else 'N/A'}")
    return scored

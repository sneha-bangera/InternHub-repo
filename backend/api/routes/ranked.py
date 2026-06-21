"""
GET /listings/ranked
Returns listings sorted by NLP cosine similarity match score
for the currently authenticated user's skill profile.
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db.database import get_db
from backend.db.models import Listing, User, UserSkill
from backend.api import crud
from backend.api.schemas import ListingOut, ListingPage

router = APIRouter(prefix="/listings", tags=["Listings"])


class RankedListingOut(ListingOut):
    match_score: float = 0.0


class RankedListingPage(ListingPage):
    items: list[RankedListingOut]


@router.get("/ranked", response_model=RankedListingPage)
def get_ranked_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    platform: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns listings ranked by NLP match score against the user's skill profile.
    Scores are computed fresh on each request using sentence-transformers.
    Users with no skills get all listings with score 0.0 (unranked).
    """
    from nlp.matcher import rank_listings

    # Fetch all active listings (we rank all, then paginate)
    stmt = select(Listing).where(Listing.is_active == True)
    if platform:
        stmt = stmt.where(Listing.source_platform == platform)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            Listing.title.ilike(like) | Listing.company.ilike(like)
        )
    all_listings = db.scalars(stmt).all()

    # Fetch user skills
    user_skills = db.scalars(
        select(UserSkill).where(UserSkill.user_id == current_user.id)
    ).all()

    # Rank
    scored = rank_listings(list(all_listings), list(user_skills))
    total = len(scored)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    page_items = scored[start:end]

    # Build response — attach match_score to each listing
    items = []
    for listing, score in page_items:
        data = RankedListingOut.model_validate(listing)
        data.match_score = score
        items.append(data)

    pages = math.ceil(total / page_size) if total else 0
    return RankedListingPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )

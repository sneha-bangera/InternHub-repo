import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api import crud
from backend.api.schemas import ListingOut, ListingPage
from backend.auth.dependencies import get_current_user
from backend.db.database import get_db
from backend.db.models import User

router = APIRouter(prefix="/listings", tags=["Listings"])


@router.get("", response_model=ListingPage)
def list_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    platform: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = crud.get_listings(db, page=page, page_size=page_size, platform=platform, search=search)
    pages = math.ceil(total / page_size) if total else 0
    return ListingPage(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    listing = crud.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing

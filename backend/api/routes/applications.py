from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api import crud
from backend.api.schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate, MessageResponse
from backend.auth.dependencies import get_current_user
from backend.db.database import get_db
from backend.db.models import User

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(
    body: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not crud.get_listing(db, body.listing_id):
        raise HTTPException(status_code=404, detail="Listing not found")
    return crud.create_application(db, current_user.id, body.listing_id, body.status, body.notes)


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.get_user_applications(db, current_user.id)


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: UUID,
    body: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app = crud.get_application(db, application_id, current_user.id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return crud.update_application(db, app, body.status, body.notes, body.applied_at)


@router.delete("/{application_id}", response_model=MessageResponse)
def delete_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app = crud.get_application(db, application_id, current_user.id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    crud.delete_application(db, app)
    return {"message": "Deleted successfully"}

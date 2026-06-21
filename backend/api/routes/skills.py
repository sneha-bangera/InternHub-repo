from uuid import UUID
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api import crud
from backend.api.schemas import MessageResponse, UserSkillCreate, UserSkillOut
from backend.auth.dependencies import get_current_user
from backend.db.database import get_db
from backend.db.models import User

router = APIRouter(prefix="/user", tags=["User Skills"])


# ── Skills ────────────────────────────────────────────────────────────────────

@router.get("/skills", response_model=list[UserSkillOut])
def list_skills(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_user_skills(db, current_user.id)


@router.post("/skills", response_model=UserSkillOut, status_code=201)
def add_skill(body: UserSkillCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.add_user_skill(db, current_user.id, body.skill, body.proficiency)


@router.delete("/skills/{skill_id}", response_model=MessageResponse)
def delete_skill(skill_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not crud.delete_user_skill(db, skill_id, current_user.id):
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"message": "Skill deleted"}


# ── WhatsApp number ───────────────────────────────────────────────────────────

class WhatsAppUpdate(BaseModel):
    whatsapp_number: str


@router.patch("/whatsapp")
def update_whatsapp(
    body: WhatsAppUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update WhatsApp number for the current user."""
    current_user.whatsapp_number = body.whatsapp_number
    db.commit()
    db.refresh(current_user)
    return {
        "message": "WhatsApp number updated",
        "whatsapp_number": current_user.whatsapp_number,
    }

from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

VALID_STATUSES = ["saved", "applied", "test", "interview", "rejected", "accepted"]
STATUS_PATTERN = "^(saved|applied|test|interview|rejected|accepted)$"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    whatsapp_number: Optional[str] = None


class UserOut(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ListingBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    skills_required: Optional[str] = None
    stipend: Optional[str] = None
    duration: Optional[str] = None
    deadline: Optional[datetime] = None
    apply_url: str
    source_platform: str
    external_id: Optional[str] = None


class ListingOut(ListingBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    match_score: Optional[float] = None
    model_config = {"from_attributes": True}


class ListingPage(BaseModel):
    items: list[ListingOut]
    total: int
    page: int
    page_size: int
    pages: int


class UserSkillCreate(BaseModel):
    skill: str = Field(..., min_length=1, max_length=100)
    proficiency: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")


class UserSkillOut(BaseModel):
    id: UUID
    user_id: UUID
    skill: str
    proficiency: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    listing_id: UUID
    status: str = Field(default="saved", pattern=STATUS_PATTERN)
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern=STATUS_PATTERN)
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None


class ApplicationOut(BaseModel):
    id: UUID
    user_id: UUID
    listing_id: UUID
    status: str
    match_score: Optional[float] = None
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    listing: ListingOut
    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str

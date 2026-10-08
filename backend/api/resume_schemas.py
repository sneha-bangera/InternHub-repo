from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ResumeProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    links: list[str] = Field(default_factory=list)


class ResumeProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    links: Optional[list[str]] = None


class ResumeProfileOut(ResumeProfileCreate):
    id: UUID
    user_id: UUID

    model_config = {"from_attributes": True}


class EducationCreate(BaseModel):
    institution: str = Field(..., min_length=1, max_length=255)
    degree: Optional[str] = Field(None, max_length=255)
    field_of_study: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class EducationUpdate(BaseModel):
    institution: Optional[str] = Field(None, min_length=1, max_length=255)
    degree: Optional[str] = Field(None, max_length=255)
    field_of_study: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class EducationOut(EducationCreate):
    id: UUID
    profile_id: UUID

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    tech_stack: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    url: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    tech_stack: Optional[list[str]] = None
    bullets: Optional[list[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    url: Optional[str] = None


class ProjectOut(ProjectCreate):
    id: UUID
    profile_id: UUID

    model_config = {"from_attributes": True}


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    proficiency: Optional[str] = Field(None, max_length=50)


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    proficiency: Optional[str] = Field(None, max_length=50)


class SkillOut(SkillCreate):
    id: UUID
    profile_id: UUID

    model_config = {"from_attributes": True}


class CertificateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    issuer: Optional[str] = Field(None, max_length=255)
    date: Optional[date] = None
    url: Optional[str] = None


class CertificateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    issuer: Optional[str] = Field(None, max_length=255)
    date: Optional[date] = None
    url: Optional[str] = None


class CertificateOut(CertificateCreate):
    id: UUID
    profile_id: UUID

    model_config = {"from_attributes": True}

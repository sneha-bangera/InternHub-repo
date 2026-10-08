from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.api.resume_schemas import CertificateOut, ProjectOut, SkillOut


class JDParseRequest(BaseModel):
    jd_text: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=255)
    role_title: Optional[str] = Field(None, max_length=255)
    listing_id: Optional[UUID] = None

    @model_validator(mode="after")
    def validate_source(self):
        if self.listing_id is None:
            if not self.jd_text or not self.jd_text.strip():
                raise ValueError("jd_text is required when listing_id is not provided")
            if not self.company_name or not self.company_name.strip():
                raise ValueError("company_name is required when using pasted JD text")
        elif self.jd_text and self.jd_text.strip():
            raise ValueError("Provide either listing_id or jd_text, not both")
        return self


class JDParseResult(BaseModel):
    role_title: Optional[str] = None
    seniority: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class TailoredBulletResult(BaseModel):
    original: str = Field(min_length=1)
    rewritten: str = Field(min_length=1)
    keywords_used: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("original", "rewritten")
    @classmethod
    def validate_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Bullet text cannot be blank")
        return value


class TailoredBulletOut(BaseModel):
    id: UUID
    target_id: UUID
    project_id: UUID
    original: str
    rewritten: str
    keywords_used: list[str]
    unverified_tokens: list[str]
    status: Literal["pending", "accepted", "rejected", "edited", "unverified"]

    model_config = {"from_attributes": True}


class TailoredBulletUpdate(BaseModel):
    status: Literal["pending", "accepted", "rejected", "edited"]
    rewritten: Optional[str] = Field(None, min_length=1)

    @field_validator("rewritten")
    @classmethod
    def validate_rewritten_lines(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and len(value.splitlines()) > 2:
            raise ValueError("Rewritten bullet must not exceed two lines")
        return value

    @model_validator(mode="after")
    def validate_edited_text(self):
        if self.status == "edited" and not self.rewritten:
            raise ValueError("rewritten is required when status is edited")
        if self.status != "edited" and self.rewritten is not None:
            raise ValueError("rewritten can only be provided when status is edited")
        return self


class JobTargetUpdate(BaseModel):
    role_title: Optional[str] = Field(None, max_length=255)
    seniority: Optional[str] = Field(None, max_length=100)
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    keywords: Optional[list[str]] = None


class JobTargetOut(BaseModel):
    id: UUID
    user_id: UUID
    listing_id: Optional[UUID] = None
    company_name: str
    role_title: Optional[str] = None
    seniority: Optional[str] = None
    jd_text: str
    required_skills: list[str]
    preferred_skills: list[str]
    keywords: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SelectedProjectOut(BaseModel):
    item: ProjectOut
    score: float
    matched_keywords: list[str]


class SelectedSkillOut(BaseModel):
    item: SkillOut
    score: float
    matched_keywords: list[str]


class SelectedCertificateOut(BaseModel):
    item: CertificateOut
    score: float
    matched_keywords: list[str]


class KeywordCoverageOut(BaseModel):
    score: float
    matched_keywords: list[str]
    missing_keywords: list[str]


class ResumeSelectionOut(BaseModel):
    projects: list[SelectedProjectOut]
    skills: list[SelectedSkillOut]
    certificates: list[SelectedCertificateOut]
    keyword_coverage: dict[str, KeywordCoverageOut]


class ResumeCompileJobOut(BaseModel):
    id: UUID
    target_id: UUID
    status: str
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeCompileRequest(BaseModel):
    sections: dict[str, bool] = Field(default_factory=dict)
    selected_project_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_sections(self):
        allowed_sections = {
            "contact",
            "education",
            "projects",
            "skills",
            "certificates",
        }
        unknown_sections = self.sections.keys() - allowed_sections
        if unknown_sections:
            raise ValueError(
                f"Unknown resume section(s): {', '.join(sorted(unknown_sections))}"
            )
        return self


class OverleafSnippetOut(BaseModel):
    snip_uri: str
    snip_name: str

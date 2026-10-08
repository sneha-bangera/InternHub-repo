import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Float, JSON,
    ForeignKey, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    whatsapp_number = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    skills = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    resume_profile = relationship(
        "ResumeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    job_targets = relationship(
        "JobTarget", back_populates="user", cascade="all, delete-orphan"
    )
    tailored_bullets = relationship(
        "TailoredBullet", back_populates="user", cascade="all, delete-orphan"
    )
    resume_compile_jobs = relationship(
        "ResumeCompileJob", back_populates="user", cascade="all, delete-orphan"
    )


class Listing(Base):
    __tablename__ = "listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    skills_required = Column(Text, nullable=True)
    stipend = Column(String(100), nullable=True)
    duration = Column(String(100), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    apply_url = Column(Text, nullable=False)
    source_platform = Column(String(50), nullable=False)
    external_id = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_platform", "external_id", name="uq_listing_platform_external"),
    )

    applications = relationship("Application", back_populates="listing", cascade="all, delete-orphan")


class UserSkill(Base):
    __tablename__ = "user_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill = Column(String(100), nullable=False)
    proficiency = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "skill", name="uq_user_skill"),
    )

    user = relationship("User", back_populates="skills")


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="saved", nullable=False)
    match_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_application_user_listing"),
    )

    user = relationship("User", back_populates="applications")
    listing = relationship("Listing", back_populates="applications")


class ResumeProfile(Base):
    __tablename__ = "resume_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    links = Column(JSON, nullable=False, default=list)

    user = relationship("User", back_populates="resume_profile")
    education = relationship(
        "Education", back_populates="profile", cascade="all, delete-orphan"
    )
    projects = relationship(
        "Project", back_populates="profile", cascade="all, delete-orphan"
    )
    skills = relationship(
        "Skill", back_populates="profile", cascade="all, delete-orphan"
    )
    certificates = relationship(
        "Certificate", back_populates="profile", cascade="all, delete-orphan"
    )


class Education(Base):
    __tablename__ = "resume_education"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(
        UUID(as_uuid=True), ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    institution = Column(String(255), nullable=False)
    degree = Column(String(255), nullable=True)
    field_of_study = Column(String(255), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    profile = relationship("ResumeProfile", back_populates="education")


class Project(Base):
    __tablename__ = "resume_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(
        UUID(as_uuid=True), ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title = Column(String(255), nullable=False)
    tech_stack = Column(JSON, nullable=False, default=list)
    bullets = Column(JSON, nullable=False, default=list)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    url = Column(Text, nullable=True)

    profile = relationship("ResumeProfile", back_populates="projects")


class Skill(Base):
    __tablename__ = "resume_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(
        UUID(as_uuid=True), ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(100), nullable=False)
    category = Column(String(100), nullable=True)
    proficiency = Column(String(50), nullable=True)

    profile = relationship("ResumeProfile", back_populates="skills")


class Certificate(Base):
    __tablename__ = "resume_certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(
        UUID(as_uuid=True), ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    issuer = Column(String(255), nullable=True)
    date = Column(Date, nullable=True)
    url = Column(Text, nullable=True)

    profile = relationship("ResumeProfile", back_populates="certificates")


class JobTarget(Base):
    __tablename__ = "job_targets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    listing_id = Column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_name = Column(String(255), nullable=False)
    role_title = Column(String(255), nullable=True)
    seniority = Column(String(100), nullable=True)
    jd_text = Column(Text, nullable=False)
    required_skills = Column(JSON, nullable=False, default=list)
    preferred_skills = Column(JSON, nullable=False, default=list)
    keywords = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="job_targets")
    listing = relationship("Listing")
    tailored_bullets = relationship(
        "TailoredBullet", back_populates="target", cascade="all, delete-orphan"
    )


class TailoredBullet(Base):
    __tablename__ = "tailored_bullets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    target_id = Column(
        UUID(as_uuid=True), ForeignKey("job_targets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("resume_projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    original = Column(Text, nullable=False)
    rewritten = Column(Text, nullable=False)
    keywords_used = Column(JSON, nullable=False, default=list)
    unverified_tokens = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="pending")

    __table_args__ = (
        UniqueConstraint(
            "target_id", "project_id", "original",
            name="uq_tailored_bullet_target_project_original",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'edited', 'unverified')",
            name="ck_tailored_bullets_status",
        ),
    )

    user = relationship("User", back_populates="tailored_bullets")
    target = relationship("JobTarget", back_populates="tailored_bullets")


class ResumeCompileJob(Base):
    __tablename__ = "resume_compile_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(
        UUID(as_uuid=True), ForeignKey("job_targets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status = Column(String(20), nullable=False, default="queued")
    error = Column(Text, nullable=True)
    sections = Column(JSON, nullable=False, default=dict)
    selected_project_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    target = relationship("JobTarget")
    user = relationship("User", back_populates="resume_compile_jobs")

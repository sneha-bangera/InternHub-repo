"""Track asynchronous resume compile jobs.

Revision ID: 0004_resume_compile_jobs
Revises: 0003_job_targets
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_resume_compile_jobs"
down_revision = "0003_job_targets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resume_compile_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["target_id"], ["job_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resume_compile_jobs_target_id",
        "resume_compile_jobs",
        ["target_id"],
    )
    op.create_index(
        "ix_resume_compile_jobs_user_id",
        "resume_compile_jobs",
        ["user_id"],
    )


def downgrade():
    op.drop_index("ix_resume_compile_jobs_user_id", table_name="resume_compile_jobs")
    op.drop_index("ix_resume_compile_jobs_target_id", table_name="resume_compile_jobs")
    op.drop_table("resume_compile_jobs")

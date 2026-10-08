"""Persist reviewed resume bullet rewrites per job target.

Revision ID: 0006_tailored_bullets
Revises: 0005_resume_compile_selection
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_tailored_bullets"
down_revision = "0005_resume_compile_selection"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tailored_bullets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original", sa.Text(), nullable=False),
        sa.Column("rewritten", sa.Text(), nullable=False),
        sa.Column("keywords_used", sa.JSON(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'edited')",
            name="ck_tailored_bullets_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["job_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["resume_projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "target_id", "project_id", "original",
            name="uq_tailored_bullet_target_project_original",
        ),
    )
    for column in ("user_id", "target_id", "project_id"):
        op.create_index(
            f"ix_tailored_bullets_{column}", "tailored_bullets", [column]
        )


def downgrade():
    for column in ("project_id", "target_id", "user_id"):
        op.drop_index(f"ix_tailored_bullets_{column}", table_name="tailored_bullets")
    op.drop_table("tailored_bullets")

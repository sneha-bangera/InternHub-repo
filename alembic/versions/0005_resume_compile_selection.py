"""Persist section toggles and selected projects for resume compilation.

Revision ID: 0005_resume_compile_selection
Revises: 0004_resume_compile_jobs
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_resume_compile_selection"
down_revision = "0004_resume_compile_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "resume_compile_jobs",
        sa.Column(
            "sections", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    op.add_column(
        "resume_compile_jobs",
        sa.Column("selected_project_ids", sa.JSON(), nullable=True),
    )
    op.alter_column("resume_compile_jobs", "sections", server_default=None)


def downgrade():
    op.drop_column("resume_compile_jobs", "selected_project_ids")
    op.drop_column("resume_compile_jobs", "sections")

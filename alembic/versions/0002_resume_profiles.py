"""Add resume profiles and profile-owned resume details.

Revision ID: 0002_resume_profiles
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_resume_profiles"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resume_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    for table, columns in (
        ("resume_education", [
            sa.Column("institution", sa.String(255), nullable=False),
            sa.Column("degree", sa.String(255), nullable=True),
            sa.Column("field_of_study", sa.String(255), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
        ]),
        ("resume_projects", [
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("tech_stack", sa.JSON(), nullable=False),
            sa.Column("bullets", sa.JSON(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("url", sa.Text(), nullable=True),
        ]),
        ("resume_skills", [
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("proficiency", sa.String(50), nullable=True),
        ]),
        ("resume_certificates", [
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("issuer", sa.String(255), nullable=True),
            sa.Column("date", sa.Date(), nullable=True),
            sa.Column("url", sa.Text(), nullable=True),
        ]),
    ):
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
            *columns,
            sa.ForeignKeyConstraint(
                ["profile_id"], ["resume_profiles.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            f"ix_{table}_profile_id", table, ["profile_id"], unique=False
        )


def downgrade():
    for table in (
        "resume_certificates",
        "resume_skills",
        "resume_projects",
        "resume_education",
    ):
        op.drop_index(f"ix_{table}_profile_id", table_name=table)
        op.drop_table(table)
    op.drop_table("resume_profiles")

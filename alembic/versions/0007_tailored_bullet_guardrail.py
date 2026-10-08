"""Add code-based verification findings to tailored bullets.

Revision ID: 0007_tailored_bullet_guardrail
Revises: 0006_tailored_bullets
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_tailored_bullet_guardrail"
down_revision = "0006_tailored_bullets"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tailored_bullets",
        sa.Column("unverified_tokens", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.drop_constraint(
        "ck_tailored_bullets_status", "tailored_bullets", type_="check"
    )
    op.create_check_constraint(
        "ck_tailored_bullets_status",
        "tailored_bullets",
        "status IN ('pending', 'accepted', 'rejected', 'edited', 'unverified')",
    )
    op.alter_column("tailored_bullets", "unverified_tokens", server_default=None)


def downgrade():
    op.drop_constraint(
        "ck_tailored_bullets_status", "tailored_bullets", type_="check"
    )
    op.create_check_constraint(
        "ck_tailored_bullets_status",
        "tailored_bullets",
        "status IN ('pending', 'accepted', 'rejected', 'edited')",
    )
    op.drop_column("tailored_bullets", "unverified_tokens")

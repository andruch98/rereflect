"""Add apartment review rating and lossless analysis payload.

Revision ID: b8a4029c7d10
Revises: ad76527a185e
"""
from alembic import op
import sqlalchemy as sa

revision = "b8a4029c7d10"
down_revision = "ad76527a185e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("feedback_items", sa.Column("star_rating", sa.Integer(), nullable=True))
    op.add_column("feedback_items", sa.Column("apartment_analysis", sa.JSON(), nullable=True))
    op.create_check_constraint("ck_feedback_star_rating", "feedback_items", "star_rating BETWEEN 1 AND 5")
    # sentiment_label is already an unconstrained String: mixed/unknown survive.


def downgrade():
    op.drop_constraint("ck_feedback_star_rating", "feedback_items", type_="check")
    op.drop_column("feedback_items", "apartment_analysis")
    op.drop_column("feedback_items", "star_rating")

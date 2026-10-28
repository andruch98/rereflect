"""Store original review posting date separately from import time."""
from alembic import op
import sqlalchemy as sa

revision = "c9b5130d8e21"
down_revision = "b8a4029c7d10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("feedback_items", sa.Column("review_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("feedback_items", "review_date")

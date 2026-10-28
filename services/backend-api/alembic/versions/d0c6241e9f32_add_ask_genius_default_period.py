"""Store each user's explicitly selected Ask Genius default period."""
from alembic import op
import sqlalchemy as sa

revision = "d0c6241e9f32"
down_revision = "c9b5130d8e21"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("ask_genius_default_period", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("users", "ask_genius_default_period")

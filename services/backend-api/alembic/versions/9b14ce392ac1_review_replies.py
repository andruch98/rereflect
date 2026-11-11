"""Manager-facing replies with approval separate from publication."""
from alembic import op
import sqlalchemy as sa

revision = '9b14ce392ac1'
down_revision = 'b46200d17e11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('review_replies',
        sa.Column('review_id', sa.Integer(), sa.ForeignKey('feedback_items.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('generation_method', sa.String(12)),
        sa.Column('generation_usage', sa.JSON()),
        sa.Column('settings_version', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('approved_by', sa.String(320)),
        sa.Column('approved_at', sa.DateTime(timezone=True)),
        sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.Column('error', sa.Text()),
        sa.CheckConstraint("status IN ('pending_approval','approved','published','failed')", name='ck_review_replies_status'),
    )


def downgrade():
    op.drop_table('review_replies')

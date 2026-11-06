"""Store manager-confirmed settings independently of existing reviews and surveys."""
from alembic import op
import sqlalchemy as sa

revision = 'b46200d17e11'
down_revision = 'a3c927b6d801'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'community_agent_settings',
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('section', sa.String(12), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("section IN ('reviews', 'surveys')", name='ck_agent_settings_section'),
    )


def downgrade():
    op.drop_table('community_agent_settings')

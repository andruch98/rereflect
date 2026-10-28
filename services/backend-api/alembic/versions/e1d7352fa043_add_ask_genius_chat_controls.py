"""Pin personal chats and store explicitly published conversation snapshots."""
from alembic import op
import sqlalchemy as sa

revision = 'e1d7352fa043'
down_revision = 'd0c6241e9f32'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('conversations', sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        'ask_genius_shares',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_ask_genius_shares_organization_id', 'ask_genius_shares', ['organization_id'])
    op.create_index('ix_ask_genius_shares_token_hash', 'ask_genius_shares', ['token_hash'], unique=True)


def downgrade():
    op.drop_index('ix_ask_genius_shares_token_hash', table_name='ask_genius_shares')
    op.drop_index('ix_ask_genius_shares_organization_id', table_name='ask_genius_shares')
    op.drop_table('ask_genius_shares')
    op.drop_column('conversations', 'is_pinned')

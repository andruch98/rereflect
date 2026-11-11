"""Add survey review receipts and invitation scheduling; preserve existing answers."""
from alembic import op
import sqlalchemy as sa

revision = '46eeba18d492'
down_revision = '9b14ce392ac1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('survey_instances', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('survey_instances', sa.Column('reviewed_by', sa.String(), nullable=True))
    for name in ('scheduled_for', 'sent_at', 'reminder_due_at', 'reminder_simulated_at'):
        op.add_column('survey_invitations', sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    for name in ('scheduled_for', 'reminder_due_at'):
        op.create_index(f'ix_survey_invitations_{name}', 'survey_invitations', [name])


def downgrade():
    for name in ('scheduled_for', 'reminder_due_at'):
        op.drop_index(f'ix_survey_invitations_{name}', table_name='survey_invitations')
    for name in ('scheduled_for', 'sent_at', 'reminder_due_at', 'reminder_simulated_at'):
        op.drop_column('survey_invitations', name)
    for name in ('reviewed_by', 'reviewed_at'):
        op.drop_column('survey_instances', name)

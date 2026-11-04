"""Allow lifecycle occurrences without fabricated maintenance tickets.

Keep existing rows, foreign keys, tokens, snapshots and answers unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a3c927b6d801'
down_revision = 'f2e8463ab154'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('maintenance_occurrences') as batch:
        batch.alter_column('ticket_id', existing_type=sa.String(200), nullable=True)
        batch.alter_column('request_description', existing_type=sa.String(1000), nullable=True)


def downgrade():
    # Never delete lifecycle responses or invent tickets to make a rollback fit.
    count = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM maintenance_occurrences '
        'WHERE ticket_id IS NULL OR request_description IS NULL')).scalar_one()
    if count:
        raise RuntimeError('Cannot downgrade while lifecycle survey occurrences exist; preserve their data.')
    with op.batch_alter_table('maintenance_occurrences') as batch:
        batch.alter_column('ticket_id', existing_type=sa.String(200), nullable=False)
        batch.alter_column('request_description', existing_type=sa.String(1000), nullable=False)

"""Occurrence-bound maintenance surveys; no review or analysis backfill."""
from alembic import op
import sqlalchemy as sa

revision = 'f2e8463ab154'
down_revision = 'e1d7352fa043'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('survey_email_opt_outs',
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('email', sa.String(320), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('survey_residents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('resident_id', sa.String(200), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('email_opt_out', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint('organization_id', 'resident_id', name='uq_survey_resident_identity'))
    op.create_table('survey_units',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_id', sa.String(200), nullable=False),
        sa.Column('number', sa.String(100), nullable=False),
        sa.UniqueConstraint('organization_id', 'unit_id', name='uq_survey_unit_identity'))
    op.create_table('maintenance_occurrences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.String(200), nullable=False),
        sa.Column('occurrence_id', sa.String(200), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('ticket_id', sa.String(200), nullable=False),
        sa.Column('request_description', sa.String(1000), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resident_record_id', sa.Integer(), sa.ForeignKey('survey_residents.id'), nullable=False),
        sa.Column('unit_record_id', sa.Integer(), sa.ForeignKey('survey_units.id'), nullable=False),
        sa.Column('resident_id', sa.String(200), nullable=False),
        sa.Column('resident_name', sa.String(200), nullable=False),
        sa.Column('resident_email', sa.String(320), nullable=False),
        sa.Column('unit_id', sa.String(200), nullable=False),
        sa.Column('unit_number', sa.String(100), nullable=False),
        sa.Column('employee_id', sa.String(200)),
        sa.Column('employee_name', sa.String(200)),
        sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('organization_id', 'event_id', name='uq_maintenance_event'),
        sa.UniqueConstraint('organization_id', 'occurrence_id', name='uq_maintenance_occurrence'))
    op.create_table('survey_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(36), nullable=False, unique=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('occurrence_id', sa.Integer(), sa.ForeignKey('maintenance_occurrences.id'), nullable=False, unique=True),
        sa.Column('token', sa.String(100), nullable=False, unique=True),
        sa.Column('questionnaire_snapshot', sa.JSON(), nullable=False),
        sa.Column('context_snapshot', sa.JSON(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('draft_answers', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_survey_instances_org_submitted', 'survey_instances', ['organization_id', 'submitted_at'])
    op.create_table('survey_invitations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('survey_id', sa.Integer(), sa.ForeignKey('survey_instances.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('provider', sa.String(30), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('recipient', sa.String(320), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('html', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('survey_url', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('survey_invitations')
    op.drop_index('ix_survey_instances_org_submitted', table_name='survey_instances')
    op.drop_table('survey_instances')
    op.drop_table('maintenance_occurrences')
    op.drop_table('survey_units')
    op.drop_table('survey_residents')
    op.drop_table('survey_email_opt_outs')

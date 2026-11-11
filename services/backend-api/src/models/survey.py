"""Occurrence-bound resident surveys, deliberately separate from review feedback."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from .base import Base


def utcnow():
    return datetime.now(timezone.utc)


class SurveyResident(Base):
    __tablename__ = 'survey_residents'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    resident_id = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=False)
    email_opt_out = Column(Boolean, nullable=False, default=False, server_default='false')
    is_simulated = Column(Boolean, nullable=False, default=True, server_default='true')
    __table_args__ = (UniqueConstraint('organization_id', 'resident_id', name='uq_survey_resident_identity'),)


class SurveyUnit(Base):
    __tablename__ = 'survey_units'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    unit_id = Column(String(200), nullable=False)
    number = Column(String(100), nullable=False)
    __table_args__ = (UniqueConstraint('organization_id', 'unit_id', name='uq_survey_unit_identity'),)


class SurveyEmailOptOut(Base):
    """Community email suppression survives resident/contact identity changes."""
    __tablename__ = 'survey_email_opt_outs'
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True)
    email = Column(String(320), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class SurveyOccurrence(Base):
    # Retain the physical table and IDs so existing tokens/FKs need no backfill.
    __tablename__ = 'maintenance_occurrences'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    event_id = Column(String(200), nullable=False)
    occurrence_id = Column(String(200), nullable=False)
    event_type = Column(String(50), nullable=False)
    ticket_id = Column(String(200), nullable=True)
    request_description = Column(String(1000), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    resident_record_id = Column(Integer, ForeignKey('survey_residents.id'), nullable=False)
    unit_record_id = Column(Integer, ForeignKey('survey_units.id'), nullable=False)
    # Event-time snapshots preserve the identity/context of this occurrence.
    resident_id = Column(String(200), nullable=False)
    resident_name = Column(String(200), nullable=False)
    resident_email = Column(String(320), nullable=False)
    unit_id = Column(String(200), nullable=False)
    unit_number = Column(String(100), nullable=False)
    employee_id = Column(String(200), nullable=True)
    employee_name = Column(String(200), nullable=True)
    is_simulated = Column(Boolean, nullable=False, default=True, server_default='true')
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resident = relationship('SurveyResident')
    unit = relationship('SurveyUnit')
    __table_args__ = (
        UniqueConstraint('organization_id', 'event_id', name='uq_maintenance_event'),
        UniqueConstraint('organization_id', 'occurrence_id', name='uq_maintenance_occurrence'),
    )


class SurveyInstance(Base):
    __tablename__ = 'survey_instances'
    id = Column(Integer, primary_key=True)
    public_id = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    occurrence_id = Column(Integer, ForeignKey('maintenance_occurrences.id'), nullable=False, unique=True)
    token = Column(String(100), nullable=False, unique=True)
    questionnaire_snapshot = Column(JSON, nullable=False)
    context_snapshot = Column(JSON, nullable=False)
    answers = Column(JSON, nullable=False, default=dict)
    draft_answers = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default='pending')
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    # Snapshot the authenticated manager's identity so account changes preserve the audit.
    reviewed_by = Column(String, nullable=True)
    occurrence = relationship('SurveyOccurrence')
    invitation = relationship('SurveyInvitation', uselist=False, back_populates='survey')
    __table_args__ = (Index('ix_survey_instances_org_submitted', 'organization_id', 'submitted_at'),)


class SurveyInvitation(Base):
    __tablename__ = 'survey_invitations'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    survey_id = Column(Integer, ForeignKey('survey_instances.id', ondelete='CASCADE'), nullable=False, unique=True)
    provider = Column(String(30), nullable=False, default='resend')
    status = Column(String(30), nullable=False)
    is_simulated = Column(Boolean, nullable=False, default=True, server_default='true')
    recipient = Column(String(320), nullable=False)
    subject = Column(String(500), nullable=False)
    html = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    survey_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    reminder_due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    reminder_simulated_at = Column(DateTime(timezone=True), nullable=True)
    survey = relationship('SurveyInstance', back_populates='invitation')


# Existing controlled maintenance preview/test imports keep their behavior.
MaintenanceOccurrence = SurveyOccurrence

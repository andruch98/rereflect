"""Persistent maintenance-event ingestion and immutable final survey answers."""
import os
import secrets
from urllib.parse import urlsplit

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from src.models.organization import Organization
from src.models.customer_health import CustomerHealth
from src.models.survey import MaintenanceOccurrence, SurveyInstance, SurveyInvitation, SurveyResident, SurveyUnit, SurveyEmailOptOut, utcnow
from src.services.survey_catalog import bind_questionnaire, validate_answers, answer_label
from src.services.survey_delivery import prepare_invitation, SimulatedSurveySender


def public_base_url() -> str:
    base = os.getenv('SURVEY_PUBLIC_BASE_URL') or (
        'http://127.0.0.1:53004' if os.getenv('BOOMSAY_REVIEW_PREVIEW', '').lower() == 'true'
        else os.getenv('APP_URL', 'http://localhost:3000'))
    parsed = urlsplit(base)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username
            or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Configure SURVEY_PUBLIC_BASE_URL as the browser application origin')
    return base.rstrip('/')


def _existing(db, event):
    occurrence = db.query(MaintenanceOccurrence).filter(
        MaintenanceOccurrence.organization_id == event.community_id,
        or_(MaintenanceOccurrence.event_id == event.event_id,
            MaintenanceOccurrence.occurrence_id == event.occurrence_id)).first()
    if occurrence is None:
        return None
    # Replays cannot bind a known event/occurrence identity to a different ticket/resident.
    if (occurrence.occurrence_id != event.occurrence_id or occurrence.ticket_id != event.ticket_id
            or occurrence.resident_id != event.resident_id):
        raise ValueError('Event or occurrence identity conflicts with an existing maintenance occurrence')
    return db.query(SurveyInstance).filter_by(occurrence_id=occurrence.id).one()


def suppress_email(db, organization_id: int, email: str):
    """Record the actual invited address, independently of mutable resident contact data."""
    email = email.lower()
    if db.get(SurveyEmailOptOut, (organization_id, email)) is None:
        try:
            with db.begin_nested():
                db.add(SurveyEmailOptOut(organization_id=organization_id, email=email))
                db.flush()
        except IntegrityError:
            # A concurrent opt-out already made the same durable suppression.
            pass


def ingest_simulated_event(db, event):
    """The sole ingestion path this increment: synchronous fake-provider delivery.

    Unique constraints are the durable dedupe boundary. The organization row lock
    also serializes concurrent ingestions for PostgreSQL; no Redis is involved.
    """
    if not event.is_simulated:
        raise ValueError('Only explicitly simulated events are supported')
    for attempt in range(2):
        try:
            org = db.query(Organization).filter_by(id=event.community_id).with_for_update().first()
            if org is None:
                raise LookupError('Community not found')
            survey = _existing(db, event)
            if survey is not None:
                db.commit()
                return survey
            resident = db.query(SurveyResident).filter_by(organization_id=org.id, resident_id=event.resident_id).first()
            if resident is None:
                resident = SurveyResident(organization_id=org.id, resident_id=event.resident_id,
                    name=event.resident_name, email=event.resident_email,
                    email_opt_out=event.resident_opt_out, is_simulated=True)
                db.add(resident)
            elif event.resident_opt_out:
                resident.email_opt_out = True  # An event must never undo an existing opt-out.
            unit = db.query(SurveyUnit).filter_by(organization_id=org.id, unit_id=event.unit_id).first()
            if unit is None:
                unit = SurveyUnit(organization_id=org.id, unit_id=event.unit_id, number=event.unit_number)
                db.add(unit)
            db.flush()
            values = event.model_dump(exclude={'community_id', 'resident_opt_out'})
            occurrence = MaintenanceOccurrence(organization_id=org.id, resident_record_id=resident.id,
                unit_record_id=unit.id, **values)
            db.add(occurrence); db.flush()
            context = {**event.model_dump(mode='json', exclude={'community_id', 'resident_opt_out', 'completed_at'}),
                       'community_name': org.name, 'ticket_completed_at': event.completed_at.isoformat()}
            survey = SurveyInstance(organization_id=org.id, occurrence_id=occurrence.id,
                token=secrets.token_urlsafe(32), questionnaire_snapshot=bind_questionnaire(context),
                context_snapshot=context, status='pending', answers={}, draft_answers={})
            db.add(survey); db.flush()
            base = public_base_url()
            survey_url = f'{base}/survey/{survey.token}'
            prepared = prepare_invitation(name=event.resident_name, community_name=org.name,
                survey_url=survey_url, unsubscribe_url=f'{base}/survey/{survey.token}/unsubscribe')
            invitation = SurveyInvitation(organization_id=org.id, survey_id=survey.id,
                recipient=event.resident_email, is_simulated=True, provider='resend',
                survey_url=survey_url, status='prepared', **prepared)
            db.add(invitation); db.flush()
            if event.resident_opt_out:
                suppress_email(db, org.id, event.resident_email)
            existing_optout = db.query(CustomerHealth.id).filter(
                CustomerHealth.organization_id == org.id,
                func.lower(CustomerHealth.customer_email) == event.resident_email.lower(),
                CustomerHealth.outreach_opt_out.is_(True)).first()
            # Honor opt-outs across aliases of the same email within this community too.
            survey_optout = db.query(SurveyResident.id).filter(
                SurveyResident.organization_id == org.id,
                func.lower(SurveyResident.email) == event.resident_email.lower(),
                SurveyResident.email_opt_out.is_(True)).first()
            email_optout = db.get(SurveyEmailOptOut, (org.id, event.resident_email.lower()))
            invitation.status = ('suppressed_opt_out' if resident.email_opt_out or existing_optout or survey_optout
                                 or email_optout
                                 else SimulatedSurveySender().send(invitation))
            db.commit()
            return survey
        except IntegrityError:
            db.rollback()
            if attempt:
                raise
    raise RuntimeError('Could not ingest maintenance event')


def serialize_survey(survey, *, manager=False):
    result = {'public_id': survey.public_id, 'status': survey.status,
              'submitted_at': survey.submitted_at, 'created_at': survey.created_at,
              'questionnaire': survey.questionnaire_snapshot,
              'context': (survey.context_snapshot if manager else {
                  key: survey.context_snapshot[key] for key in (
                      'community_name', 'request_description', 'ticket_id', 'ticket_completed_at')
                  if key in survey.context_snapshot}), 'answers': survey.answers,
              'draft_answers': survey.draft_answers}
    result['answer_labels'] = {q['id']: answer_label(q, survey.answers.get(q['id']), survey.questionnaire_snapshot)
                               for q in survey.questionnaire_snapshot['questions']}
    if manager:
        invitation = survey.invitation
        result['invitation'] = ({key: getattr(invitation, key) for key in (
            'status', 'provider', 'is_simulated', 'recipient', 'subject', 'html', 'text', 'survey_url', 'created_at')}
            if invitation else None)
    return result


def save_answers(db, survey, answers, *, final=False):
    try:
        # Reload under the PostgreSQL row lock: separate tabs may both have read
        # an older draft before reaching this write. Merge against the winner's
        # latest saved values, preserving disjoint partial autosaves.
        survey = db.query(SurveyInstance).filter(SurveyInstance.id == survey.id).populate_existing().with_for_update().one()
        if survey.submitted_at is not None:
            db.commit()  # Release the lock without changing finalized answers.
            return survey
        validated = validate_answers(survey.questionnaire_snapshot, answers, final=final)
        now = utcnow()
        values = {'updated_at': now}
        if final:
            values.update(answers=validated, draft_answers={}, status='submitted', submitted_at=now)
        else:
            values.update(draft_answers={**survey.draft_answers, **validated}, status='draft')
        # Retain the conditional final guard in addition to write serialization.
        db.query(SurveyInstance).filter(SurveyInstance.id == survey.id,
            SurveyInstance.submitted_at.is_(None)).update(values, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(survey)
    return survey

"""Persistent lifecycle-event ingestion and immutable final survey answers."""
import os
import secrets
from urllib.parse import urlsplit

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from src.models.organization import Organization
from src.models.survey import SurveyOccurrence, SurveyInstance, SurveyInvitation, SurveyResident, SurveyUnit, SurveyEmailOptOut, utcnow
from src.services.survey_catalog import bind_questionnaire, validate_answers, answer_label, event_type_for, EVENT_LABELS
from src.services.survey_delivery import prepare_invitation
from src.services.survey_schedule import cancel_simulated_work, schedule_invitation


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
    occurrence = db.query(SurveyOccurrence).filter(
        SurveyOccurrence.organization_id == event.community_id,
        or_(SurveyOccurrence.event_id == event.event_id,
            SurveyOccurrence.occurrence_id == event.occurrence_id)).first()
    if occurrence is None:
        return None
    # Replays cannot bind a known event/occurrence identity to a different ticket/resident.
    if (occurrence.event_type != event.event_type or occurrence.occurrence_id != event.occurrence_id or occurrence.ticket_id != event.ticket_id
            or occurrence.resident_id != event.resident_id):
        raise ValueError('Event or occurrence identity conflicts with an existing survey occurrence')
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
    """Bind a simulated event to one resident survey and apply its community schedule.

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
            occurrence = SurveyOccurrence(organization_id=org.id, resident_record_id=resident.id,
                unit_record_id=unit.id, **values)
            db.add(occurrence); db.flush()
            context = {**event.model_dump(mode='json', exclude={'community_id', 'resident_opt_out', 'completed_at'}),
                       'community_name': org.name, 'event_occurred_at': event.completed_at.isoformat(),
                       'survey_type_label': EVENT_LABELS[event.event_type]}
            if event.event_type == 'maintenance_completed':
                context['ticket_completed_at'] = event.completed_at.isoformat()
            survey = SurveyInstance(organization_id=org.id, occurrence_id=occurrence.id,
                token=secrets.token_urlsafe(32), questionnaire_snapshot=bind_questionnaire(context, event.event_type),
                context_snapshot=context, status='pending', answers={}, draft_answers={})
            db.add(survey); db.flush()
            base = public_base_url()
            survey_url = f'{base}/survey/{survey.token}'
            prepared = prepare_invitation(name=event.resident_name, community_name=org.name,
                survey_url=survey_url, unsubscribe_url=f'{base}/survey/{survey.token}/unsubscribe',
                questionnaire=survey.questionnaire_snapshot)
            invitation = SurveyInvitation(organization_id=org.id, survey_id=survey.id,
                recipient=event.resident_email, is_simulated=True, provider='resend',
                survey_url=survey_url, status='prepared', **prepared)
            db.add(invitation); db.flush()
            if event.resident_opt_out:
                suppress_email(db, org.id, event.resident_email)
            schedule_invitation(db, survey, invitation, event.completed_at)
            db.commit()
            return survey
        except IntegrityError:
            db.rollback()
            if attempt:
                raise
    raise RuntimeError('Could not ingest survey event')


def serialize_survey(survey, *, manager=False):
    context = dict(survey.context_snapshot)
    kind = event_type_for(survey.questionnaire_snapshot, context)
    context.update(event_type=kind, survey_type_label=EVENT_LABELS.get(kind, 'Survey'))
    context.setdefault('event_occurred_at', context.get('ticket_completed_at'))
    result = {'public_id': survey.public_id, 'status': survey.status,
              'submitted_at': survey.submitted_at, 'created_at': survey.created_at,
              'questionnaire': survey.questionnaire_snapshot,
              'context': (context if manager else {
                  key: context[key] for key in (
                      'community_name', 'request_description', 'ticket_id', 'ticket_completed_at',
                      'event_type', 'survey_type_label', 'event_occurred_at')
                  if key in context}), 'answers': survey.answers,
              'draft_answers': survey.draft_answers}
    result['answer_labels'] = {q['id']: answer_label(q, survey.answers.get(q['id']), survey.questionnaire_snapshot)
                               for q in survey.questionnaire_snapshot['questions']}
    if manager:
        invitation = survey.invitation
        result['invitation'] = ({key: getattr(invitation, key) for key in (
            'status', 'provider', 'is_simulated', 'recipient', 'subject', 'html', 'text', 'survey_url', 'created_at',
            'scheduled_for', 'sent_at', 'reminder_due_at', 'reminder_simulated_at')}
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
        if final:
            cancel_simulated_work(db, [survey.id], 'suppressed_submitted')
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(survey)
    return survey

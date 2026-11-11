"""Community survey activity and manager review receipts, separate from resident answers."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload

from src.models.survey import SurveyInstance, SurveyInvitation, SurveyOccurrence, utcnow
from src.services.ask_genius_periods import TIMEZONE
from src.services.agent_settings import survey_settings
from src.services.survey_catalog import answer_label
from src.services.surveys import serialize_survey


def attention_reasons(snapshot, answers, settings):
    reasons = []
    for question in snapshot.get('questions', []):
        key = question['id']
        value = answers.get(key)
        low = (settings.flag_low_ratings and question.get('type') == 'rating'
               and type(value) is int and value in (1, 2))
        unresolved = settings.flag_unresolved and (
            (key == 'move_in_unresolved' and value == 'yes') or
            (key == 'issue_resolution' and value in ('partially_resolved', 'unresolved')))
        if low or unresolved or (key == 'follow_up_requested' and value == 'yes'):
            reasons.append({'question_id': key, 'label': question.get('rendered_text') or question['text'],
                            'answer': answer_label(question, value, snapshot)})
    return reasons


def manager_detail(row, settings):
    return {**serialize_survey(row, manager=True), 'reviewed_at': row.reviewed_at,
            'reviewed_by': row.reviewed_by,
            'attention_reasons': (attention_reasons(row.questionnaire_snapshot, row.answers, settings)
                                  if row.submitted_at is not None else [])}


def mark_reviewed(db, row, user):
    if row.submitted_at is None:
        raise ValueError('Only a submitted response can be marked reviewed.')
    # Preserve the first review even when two managers click at the same time.
    db.query(SurveyInstance).filter_by(
        id=row.id, organization_id=user.organization_id, reviewed_at=None).update(
        {SurveyInstance.reviewed_by: user.email, SurveyInstance.reviewed_at: utcnow()},
        synchronize_session=False)
    db.commit()
    db.refresh(row)


def activity_page(db, organization_id, event_type, start_date, end_date, view, page, page_size):
    settings = survey_settings(db, organization_id)
    zone = ZoneInfo(TIMEZONE)

    def calendar_bound(day):
        return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc)

    start = calendar_bound(start_date) if start_date else None
    stop = calendar_bound(end_date + timedelta(days=1)) if end_date and end_date < date.max else None

    def within(column):
        conditions = [column.is_not(None)]
        if start is not None:
            conditions.append(column >= start)
        if stop is not None:
            conditions.append(column < stop)
        return and_(*conditions)

    survey = SurveyInstance
    invite = SurveyInvitation
    query = db.query(survey.id).outerjoin(invite, and_(
        invite.survey_id == survey.id, invite.organization_id == survey.organization_id
    )).filter(survey.organization_id == organization_id)
    if event_type:
        query = query.join(SurveyOccurrence, SurveyOccurrence.id == survey.occurrence_id).filter(
            SurveyOccurrence.event_type == event_type)
    accepted = and_(invite.is_simulated.is_(False), invite.status == 'provider_accepted')
    sent = accepted
    if start or stop:
        # Old accepted records without an acceptance timestamp count only in all history.
        sent = and_(sent, within(invite.sent_at))
    submitted = within(survey.submitted_at)

    # Read only submitted, unreviewed original answers when calculating attention.
    # Edits to flag preferences immediately apply to the queue, including historical surveys.
    offset = (page - 1) * page_size
    candidates = query.filter(submitted, survey.reviewed_at.is_(None)).with_entities(
        survey.id, survey.questionnaire_snapshot, survey.answers).order_by(
        survey.submitted_at.desc(), survey.id.desc())
    flagged_ids, flagged_count = [], 0
    for row in candidates.yield_per(250):
        if attention_reasons(row.questionnaire_snapshot, row.answers, settings):
            if view == 'needs_review' and offset <= flagged_count < offset + page_size:
                flagged_ids.append(row.id)
            flagged_count += 1
    counts = {'sent': query.filter(sent).count(), 'submitted': query.filter(submitted).count(),
              'needs_review': flagged_count}
    if view == 'needs_review':
        ids, total = flagged_ids, flagged_count
    else:
        if view == 'sent':
            result = query.filter(sent).order_by(invite.sent_at.desc().nullslast())
            total = counts['sent']
        elif view == 'submitted':
            result = query.filter(submitted).order_by(survey.submitted_at.desc())
            total = counts['submitted']
        elif view == 'reviewed':
            result = query.filter(submitted, survey.reviewed_at.is_not(None)).order_by(survey.reviewed_at.desc())
            total = result.order_by(None).count()
        else:
            result = query
            if start or stop:
                result = result.filter(or_(within(survey.created_at), submitted, sent))
            # A response arriving today should surface even if its invitation is old.
            latest_response = func.coalesce(survey.submitted_at, survey.created_at)
            latest_activity = case((and_(accepted, invite.sent_at > latest_response), invite.sent_at),
                                   else_=latest_response)
            result = result.order_by(latest_activity.desc())
            total = result.order_by(None).count()
        ids = [r.id for r in result.order_by(survey.id.desc()).offset(offset).limit(page_size)]
    rows = db.query(survey).options(joinedload(survey.invitation)).filter(
        survey.organization_id == organization_id, survey.id.in_(ids)).all()
    by_id = {row.id: manager_detail(row, settings) for row in rows}
    return {'surveys': [by_id[key] for key in ids if key in by_id], 'total': total, 'counts': counts}

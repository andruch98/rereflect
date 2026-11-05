"""Bounded diagnostic using the unchanged PR12 question route and four frozen submissions.

The original database is opened read-only, then disconnected. All route writes go
to an in-memory SQLite copy. No startup, migrations, workers, email or Share calls.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from src.api.routes import ask_genius as routes
from src.models.base import Base
from src.models.conversation_message import ConversationMessage
from src.models.organization import Organization
from src.models.survey import SurveyInstance, SurveyOccurrence, SurveyResident, SurveyUnit
from src.models.user import User
from src.services import ask_genius as service
from src.services import ask_genius_surveys as surveys
from src.services.ask_genius_periods import Period

COHORT = {
    'round2-move-in': 'move_in_completed',
    'round2-maintenance': 'maintenance_completed',
    'round2-pre-renewal': 'lease_month_9',
    'round2-move-out': 'move_out_completed',
}
DAY = '2026-11-05'
QUESTIONS = [
    ('conversation', 'How many survey responses did we receive during this period?'),
    ('conversation', 'Break it down by survey type.'),
    ('conversation', 'What do the maintenance surveys say?'),
    ('conversation', 'Which maintenance response needs attention, and what did the resident say?'),
    ('conversation', 'What issue is it?'),
    ('conversation', 'What does the move-in completed survey say?'),
    ('conversation', 'What about the 9-month renewal planning survey?'),
    ('conversation', 'What does the move-out survey say?'),
    ('conversation', 'Which are the bad surveys? Summarize them in a list.'),
    ('conversation', 'What are the main improvements suggested by all surveys?'),
    ('conversation', 'Do you think we charge good rent?'),
    ('conversation', 'Based on all the surveys, are we doing a good job?'),
    ('conversation', 'What evidence supports your summary? Show the original survey answers.'),
    ('fresh-negative', 'Which are the bad surveys? Summarize them in a list.'),
    ('fresh-overall', 'Based on all the surveys, are we doing a good job?'),
]


SUMMARY_QUESTIONS = [
    ('conversation', 'Which are the bad surveys? Summarize them in a list.'),
    ('conversation', 'What are the main improvements suggested by all surveys?'),
    ('conversation', 'Based on all the surveys, are we doing a good job?'),
    ('fresh-negative', 'Which are the bad surveys? Summarize them in a list.'),
    ('fresh-overall', 'Based on all the surveys, are we doing a good job?'),
]


def emit(event):
    print(json.dumps(event, ensure_ascii=False, default=str), flush=True)


def validate_rows(rows):
    """Fail closed before paid requests, rather than silently selecting latest rows."""
    expected = {'boomsay-email-test-' + key: value for key, value in COHORT.items()}
    if len(rows) != 4 or {r['event_id'] for r in rows} != set(expected):
        raise ValueError('Expected exactly the four named November 5 test submissions. Nothing sent.')
    for row in rows:
        if row['event_type'] != expected[row['event_id']] or not row['is_simulated']:
            raise ValueError('A selected record is not the expected fictional survey type. Nothing sent.')
        if row['status'] != 'submitted' or not row['submitted_at']:
            raise ValueError('All four surveys must be submitted. Nothing sent.')
        stamp = row['submitted_at']
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        if stamp.astimezone(ZoneInfo('America/New_York')).date().isoformat() != DAY:
            raise ValueError('A selected submission is not dated November 5, 2026. Nothing sent.')
        snapshot_type = surveys.event_type_for(row['questionnaire_snapshot'], row['context_snapshot'])
        if snapshot_type != row['event_type']:
            raise ValueError('Survey type and frozen questionnaire disagree. Nothing sent.')
    return rows


def read_cohort(url, org_id):
    engine = create_engine(url, echo=False)
    try:
        # SELECT explicit columns only: no survey tokens, drafts or invitation URLs.
        with engine.connect() as connection:
            if engine.dialect.name == 'postgresql':
                connection.execute(text('SET TRANSACTION READ ONLY'))
            elif engine.dialect.name == 'sqlite':
                connection.execute(text('PRAGMA query_only = ON'))
            else:
                raise ValueError('Unsupported local preview database. Nothing sent.')
            name = connection.execute(select(Organization.name).where(Organization.id == org_id)).scalar_one_or_none()
            if name is None:
                raise ValueError('The configured community was not found. Nothing sent.')
            s, o = SurveyInstance, SurveyOccurrence
            query = select(s.public_id, s.questionnaire_snapshot, s.context_snapshot,
                           s.answers, s.status, s.submitted_at, o.event_id, o.event_type,
                           o.is_simulated, o.completed_at, o.ticket_id, o.request_description).join(
                               o, s.occurrence_id == o.id).where(
                                   s.organization_id == org_id, o.organization_id == org_id,
                                   o.event_id.in_(['boomsay-email-test-' + key for key in COHORT]))
            rows = [deepcopy(dict(r)) for r in connection.execute(query).mappings()]
            validate_rows(rows)
            connection.rollback()
        return name, rows
    finally:
        engine.dispose()


def isolated_database(name, rows, org_id):
    engine = create_engine('sqlite://', echo=False)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add(Organization(id=org_id, name=name, plan='enterprise'))
    db.flush()
    user = User(email='local-diagnostic@example.invalid', password_hash='unused',
                organization_id=org_id, role='member')
    db.add(user)
    for row in rows:
        identity = row['event_id']
        resident = SurveyResident(organization_id=org_id, resident_id=identity,
                                  name='Fictional local test', email='unused@example.invalid')
        unit = SurveyUnit(organization_id=org_id, unit_id=identity, number='EMAIL-TEST')
        db.add_all([resident, unit]); db.flush()
        occurrence = SurveyOccurrence(organization_id=org_id, event_id=identity, occurrence_id=identity,
            event_type=row['event_type'], ticket_id=row['ticket_id'], request_description=row['request_description'],
            completed_at=row['completed_at'], resident_record_id=resident.id, unit_record_id=unit.id,
            resident_id=identity, resident_name=resident.name, resident_email=resident.email,
            unit_id=identity, unit_number=unit.number, is_simulated=True)
        db.add(occurrence); db.flush()
        # Preserve the actual model evidence verbatim; unused credentials/identity are synthetic.
        db.add(SurveyInstance(organization_id=org_id, occurrence_id=occurrence.id,
            public_id=row['public_id'], token='unused-diagnostic-' + str(uuid4()),
            questionnaire_snapshot=deepcopy(row['questionnaire_snapshot']),
            context_snapshot=deepcopy(row['context_snapshot']), answers=deepcopy(row['answers']),
            draft_answers={}, status='submitted', submitted_at=row['submitted_at']))
    db.commit()
    return engine, db, user


async def execute_questions(db, user, questions=None):
    questions = QUESTIONS if questions is None else questions
    conversations = {}
    failed_by_group = {}
    failures = 0
    for index, (group, question) in enumerate(questions, 1):
        request_id = uuid4()
        emit({'kind': 'attempt', 'index': index, 'group': group, 'question': question})
        result, failure = None, None
        continued_after_failure = False
        prior_failures = list(failed_by_group.get(group, []))
        try:
            result = await routes.ask_question(routes.Question(question=question, request_id=request_id,
                conversation_id=conversations.get(group), period=Period(preset='custom', start_date=DAY, end_date=DAY)),
                user=user, db=db)
            conversations[group] = result['conversation_id']
        except HTTPException as exc:
            failure = {'http_status': exc.status_code, 'detail': exc.detail}
            # Only completed answer attempts may continue. Configuration, access,
            # database and unexpected failures still stop the diagnostic.
            continued_after_failure = (exc.status_code == 502 and isinstance(exc.detail, dict)
                                       and exc.detail.get('code') == 'ask_genius_failed')
            if continued_after_failure and exc.detail.get('conversation_id'):
                conversations[group] = exc.detail['conversation_id']
        except Exception as exc:
            failure = {'error_type': type(exc).__name__, 'detail': 'Unexpected error; private exception text omitted.'}
            db.rollback()
        attempted = db.query(ConversationMessage).filter_by(role='user').order_by(ConversationMessage.id.desc()).first()
        audit = attempted.raw_request if attempted and isinstance(attempted.raw_request, dict) else {}
        if audit.get('request_id') != str(request_id):
            attempted, audit = None, {}
        answer = db.get(ConversationMessage, audit['answer_message_id']) if audit.get('answer_message_id') else None
        emit({'kind': 'result', 'index': index, 'group': group, 'question': question,
            'status': 'failed' if failure else 'completed', 'failure': failure, 'response': result,
            'continued_after_failure': continued_after_failure,
            'prior_failed_questions_in_chat': prior_failures,
            'raw_request': audit, 'raw_response': attempted.raw_response if attempted else None,
            'tokens_in': answer.tokens_in if answer else attempted.tokens_in if attempted else None,
            'tokens_out': answer.tokens_out if answer else attempted.tokens_out if attempted else None,
            'cost': None, 'cost_note': 'Unavailable; no price estimate substituted.',
            'human_assessment': 'Pending review against captured source answers.'})
        if failure:
            failures += 1
            failed_by_group.setdefault(group, []).append(index)
            if not continued_after_failure:
                return 1
    emit({'kind': 'complete', 'questions': len(questions), 'failed_questions': failures,
          'completed_questions': len(questions) - failures,
          'status': 'completed_with_failures' if failures else 'completed',
          'human_acceptance': 'pending'})
    return 1 if failures else 0


async def main():
    if os.getenv('BOOMSAY_REVIEW_PREVIEW', '').lower() != 'true':
        raise ValueError('This diagnostic requires the existing local preview. Nothing sent.')
    org_text = os.getenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', '')
    if not org_text.isdecimal() or int(org_text) < 1:
        raise ValueError('The local preview community is not configured. Nothing sent.')
    url = os.getenv('DATABASE_URL', '')
    if not url:
        raise ValueError('The preview database is not configured. Nothing sent.')
    org_id = int(org_text)
    config, reason = service.configured_llm(org_id, None)
    if config is None:
        raise ValueError('Ask Genius is not configured: ' + str(reason))
    name, rows = read_cohort(url, org_id)
    engine, db, user = isolated_database(name, rows, org_id)
    try:
        period = Period(preset='custom', start_date=DAY, end_date=DAY)
        evidence = service.build_authorized_evidence(org_id, db, period, 'surveys')
        if len(evidence['surveys']) != 4:
            raise ValueError('The isolated evidence does not contain all four submissions. Nothing sent.')
        provenance = json.loads((Path(__file__).parent / 'source.json').read_text())
        questions = SUMMARY_QUESTIONS if provenance.get('question_set') == 'summary-check' else QUESTIONS
        emit({'kind': 'preflight', 'provider': config.provider, 'model': config.model,
            'source': provenance,
            'prompt_sha256': hashlib.sha256((service.SYSTEM_PROMPT + '\n\n' + service.RUNTIME_RULES).encode()).hexdigest(),
            'evidence': evidence, 'source_rows': rows,
            'questions': questions, 'max_model_calls': len(questions), 'retries': 0,
            'notes': 'Actual PR12 question route, isolated cohort DB; no HTTP authentication/browser/Share test. '
                     'Only these four submissions are available. Historical example facts are not current evidence. '
                     'Earlier results are historical comparisons, not a controlled paired run. Summary-check starts three '
                     'sequential questions in a new chat and two fresh-chat checks; it does not replay earlier turns.'})
        return await execute_questions(db, user, questions)
    finally:
        db.close(); engine.dispose()


if __name__ == '__main__':
    try:
        code = asyncio.run(main())
    except ValueError as exc:
        emit({'kind': 'preflight_failure', 'reason': str(exc)})
        code = 1
    except Exception as exc:
        emit({'kind': 'preflight_failure', 'reason': type(exc).__name__ + ': preflight failed; no test requests sent.'})
        code = 1
    raise SystemExit(code)

"""Developer-only maintenance survey simulation in a separate fictional database.

Run from services/backend-api with BOOMSAY_SURVEY_DEMO=true. This command never
sends mail, calls a model, creates a completed response, or resets a database.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

DEMO_NAME = 'BoomSay Fictional Survey Demo'
# Use the reserved example.com domain so the existing EmailStr login validator
# accepts the fictional manager; .invalid is rejected before authentication.
DEMO_EMAIL = 'manager@survey-demo.example.com'


def require_demo_mode() -> None:
    if os.getenv('BOOMSAY_SURVEY_DEMO', '').lower() != 'true':
        raise ValueError('Set BOOMSAY_SURVEY_DEMO=true only for a separate fictional demo database.')


def demo_community(db):
    """Refuse to operate on existing communities, including the installed preview."""
    from src.models.organization import Organization
    from src.models.user import User
    require_demo_mode()
    communities = db.query(Organization).all()
    users = db.query(User).all()
    if (len(communities) != 1 or communities[0].id != 1 or communities[0].name != DEMO_NAME
            or communities[0].ai_analysis_enabled or len(users) != 1
            or users[0].organization_id != 1 or users[0].email != DEMO_EMAIL
            or users[0].role != 'owner'):
        raise ValueError('This is not the isolated fictional survey database. No records were changed.')
    return communities[0]


def initialize_demo(db, password: str | None = None):
    from src.api.auth import hash_password
    from src.models.organization import Organization
    from src.models.user import User
    require_demo_mode()
    if db.query(Organization).first() is not None or db.query(User).first() is not None:
        community = demo_community(db)
        return {'community_id': community.id, 'manager_email': DEMO_EMAIL, 'created': False,
                'message': 'Existing fictional demo and password retained.'}
    password = password or os.getenv('SURVEY_DEMO_PASSWORD') or getpass.getpass('New fictional demo login password: ')
    if len(password) < 12:
        raise ValueError('Choose a demo login password with at least 12 characters.')
    community = Organization(id=1, name=DEMO_NAME, plan='enterprise', ai_analysis_enabled=False)
    db.add(community); db.flush()
    db.add(User(email=DEMO_EMAIL, password_hash=hash_password(password), organization_id=community.id,
                role='owner', weekly_digest_enabled=False, daily_digest_enabled=False,
                alert_channels={'dashboard': True, 'email': False, 'slack': False}))
    db.commit()
    return {'community_id': community.id, 'manager_email': DEMO_EMAIL, 'created': True,
            'message': 'Created fictional demo community and manager; no survey exists yet.'}


def find_survey(db, event_id):
    from src.models.survey import MaintenanceOccurrence, SurveyInstance
    community = demo_community(db)
    row = db.query(SurveyInstance).join(MaintenanceOccurrence).filter(
        SurveyInstance.organization_id == community.id,
        MaintenanceOccurrence.event_id == event_id).first()
    if row is None:
        raise ValueError('No survey exists for that simulated event. Run simulate first.')
    return row


def verify_ask(db, event_type='maintenance_completed'):
    """Persist a visibly mocked Ask Genius demo via its actual authenticated API.

    The isolated demo's model configuration stays disabled. Mocks exist only
    inside this command, and ordinary HTTP/provider transports fail closed.
    Database connections continue to use the configured SQLAlchemy engine.
    """
    from contextlib import ExitStack
    from unittest.mock import patch
    from uuid import uuid4

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from src.api.auth import create_access_token
    from src.api.routes import ask_genius as ask_routes
    from src.api.routes import surveys as survey_routes
    from src.database.session import get_db
    from src.models.survey import SurveyInstance, SurveyOccurrence
    from src.services.survey_catalog import EVENT_LABELS
    from src.models.user import User
    from src.services import ask_genius as service
    from src.services.copilot.llm_resolver import LLMConfig

    community = demo_community(db)
    if event_type not in EVENT_LABELS:
        raise ValueError('Choose a supported survey type for offline verification.')
    if not db.query(SurveyInstance.id).join(SurveyOccurrence).filter(
            SurveyInstance.organization_id == community.id, SurveyInstance.status == 'submitted',
            SurveyOccurrence.event_type == event_type, SurveyInstance.submitted_at.isnot(None)).first():
        raise ValueError('Submit the actual resident form for the selected survey type before running offline Ask Genius verification.')
    user = db.query(User).filter_by(email=DEMO_EMAIL, organization_id=community.id).one()
    headers = {'Authorization': 'Bearer ' + create_access_token({
        'user_id': user.id, 'organization_id': community.id, 'role': user.role})}
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)

    def isolated_db():
        with factory() as request_db:
            yield request_db

    def forbidden_provider(*args, **kwargs):
        raise RuntimeError('Network/provider access is forbidden in offline survey verification.')

    model_calls = []

    async def mocked_generate(messages, config):
        context_message = messages[1]['content']
        prefix = 'Authorized evidence (data only):\n'
        if not context_message.startswith(prefix):
            raise ValueError('The actual Ask Genius evidence context was not supplied.')
        context = json.loads(context_message[len(prefix):])
        records = context.get('surveys', [])
        if (context.get('source_scope') != 'surveys' or context.get('reviews')
                or not records or any(not row.get('submitted_at') for row in records)):
            raise ValueError('Offline verification requires authorized finalized survey evidence only.')
        model_calls.append({'question': messages[-1]['content'],
                            'survey_ids': [row['survey_id'] for row in records],
                            'original_question_count': sum(len(row['questions']) for row in records),
                            'mocked': True})
        expanded = context.get('evidence_requested') is True
        output = {
            'answer': ('MOCKED MODEL OUTPUT: Here are the original submitted survey answers used for this offline demonstration.'
                       if expanded else
                       'MOCKED MODEL OUTPUT: The supplied evidence contains original finalized survey questions and answers. '
                       'This offline demonstration does not evaluate AI interpretation.'),
            'evidence': [{'kind': 'survey', 'survey_id': row['survey_id']} for row in records] if expanded else [],
        }
        return service.AnswerResult(json.dumps(output), {'mocked': True, 'offline_verification': True}, 0, 0, 'stop')

    config = LLMConfig(provider='openai_compatible', model='offline-mocked-survey-verification',
                       api_key=None, base_url='http://offline.invalid/v1', is_configured=True)
    app = FastAPI()
    app.include_router(ask_routes.router)
    app.include_router(survey_routes.router)
    app.dependency_overrides[get_db] = isolated_db
    results = []
    conversation_id = None
    title = '[OFFLINE MOCK] Survey verification'
    with ExitStack() as mocks:
        mocks.enter_context(patch.object(service, 'configured_llm', return_value=(config, None)))
        mocks.enter_context(patch.object(service, 'generate_answer', new=mocked_generate))
        mocks.enter_context(patch('requests.sessions.Session.request', side_effect=forbidden_provider))
        mocks.enter_context(patch('httpx.HTTPTransport.handle_request', side_effect=forbidden_provider))
        mocks.enter_context(patch('httpx.AsyncHTTPTransport.handle_async_request', side_effect=forbidden_provider))
        mocks.enter_context(patch('src.services.email_service._send_email', side_effect=forbidden_provider))
        mocks.enter_context(patch('openai.AsyncOpenAI', side_effect=forbidden_provider))
        with TestClient(app) as client:
            for question in (
                f'How many completed {EVENT_LABELS[event_type].lower()} surveys?',
                ('Which submissions say the issue is still unresolved?' if event_type == 'maintenance_completed'
                 else 'How many unique residents submitted a survey?'),
                'What did residents say in these surveys?',
                'Show the original answers behind that.',
            ):
                body = {'question': question, 'request_id': str(uuid4())}
                if conversation_id:
                    body['conversation_id'] = conversation_id
                else:
                    body['period'] = {'preset': 'all_time'}
                response = client.post('/api/v1/ask-genius/questions', headers=headers, json=body)
                if response.status_code != 200:
                    raise ValueError(f'Offline Ask Genius route failed ({response.status_code}): {response.text}')
                answer = response.json()
                first_answer = conversation_id is None
                conversation_id = answer['conversation_id']
                if first_answer:
                    renamed = client.patch('/api/v1/ask-genius/conversations/' + conversation_id,
                                           headers=headers, json={'title': title})
                    if renamed.status_code != 200:
                        raise ValueError('Could not label the saved demonstration chat as mocked.')
                metadata = answer['structured_data']
                links = []
                for source in metadata.get('sources', []):
                    if source.get('kind') != 'survey' or source.get('href') != '/surveys/' + source['survey_id']:
                        raise ValueError('A survey evidence link was not source-aware.')
                    original = client.get('/api/v1/surveys/' + source['survey_id'], headers=headers)
                    if original.status_code != 200 or original.json().get('status') != 'submitted':
                        raise ValueError('A survey evidence link did not resolve to its authorized final original.')
                    links.append({'survey_id': source['survey_id'], 'href': source['href'], 'detail_http_status': 200})
                results.append({'question': question, 'answer': answer['answer'],
                                'survey_counts': metadata.get('survey_counts'), 'evidence_links': links})
            shared = client.post('/api/v1/ask-genius/conversations/' + conversation_id + '/share', headers=headers)
            if shared.status_code != 422:
                raise ValueError('Survey-backed chat sharing was not blocked as required.')
    return {'verification_mode': 'offline_mock', 'live_model_calls': 0,
            'counts_source': 'application_records', 'conversation_id': conversation_id,
            'conversation_title': title, 'open_history_at': '/ask-genius',
            'sharing_status': 'unavailable', 'mocked_model_calls': model_calls, 'results': results,
            'message': 'Saved a clearly labeled mocked verification chat. Application AI/provider configuration was not changed.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Create a fictional community in an otherwise empty migrated database.')
    from src.services.survey_catalog import EVENT_LABELS
    verify = commands.add_parser('verify-ask', help='Save a clearly mocked, offline Ask Genius verification chat using actual routes and survey records.')
    verify.add_argument('--event-type', choices=tuple(EVENT_LABELS), default='maintenance_completed')
    simulate = commands.add_parser('simulate', help='Ingest fictional maintenance event JSON through the real workflow.')
    simulate.add_argument('event', type=Path, help='JSON file, or - to read JSON from standard input.')
    for name in ('inspect', 'link'):
        command = commands.add_parser(name, help='Inspect the persisted simulated invitation and survey.' if name == 'inspect' else 'Print the actual saved resident link.')
        command.add_argument('event_id')
    args = parser.parse_args(argv)
    require_demo_mode()
    from src.database.session import SessionLocal
    from src.services.surveys import ingest_simulated_event, serialize_survey
    with SessionLocal() as db:
        if args.command == 'init':
            result = initialize_demo(db)
        elif args.command == 'verify-ask':
            result = verify_ask(db, args.event_type)
        elif args.command == 'simulate':
            from src.api.routes.surveys import MaintenanceCompletedEvent
            community = demo_community(db)
            raw = sys.stdin.read() if str(args.event) == '-' else args.event.read_text(encoding='utf-8')
            event = MaintenanceCompletedEvent.model_validate_json(raw)
            if event.community_id != community.id:
                raise ValueError('The event must use the fictional demo community ID.')
            result = serialize_survey(ingest_simulated_event(db, event), manager=True)
        else:
            survey = find_survey(db, args.event_id)
            if args.command == 'link':
                print(survey.invitation.survey_url)
                return 0
            result = serialize_survey(survey, manager=True)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from None

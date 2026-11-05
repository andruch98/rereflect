"""Explicit one-recipient email test; fictional event, real delivery tracked separately.

No provider calls here. The Mac helper reserves once in the database before sending.
A reserved/failed attempt never becomes sendable again, including after a crash.
"""
from datetime import datetime, timezone
from html import escape
import argparse
import json
import os
import re
from typing import Literal

from src.services.survey_catalog import EVENT_LABELS

RECIPIENT = 'andres.feuerberg.ch@gmail.com'
SENDER = 'BoomSay <andres@boomsay.com>'
BASE = 'http://127.0.0.1:53004'


def operate(db, action, test_id, event_type='maintenance_completed'):
    from sqlalchemy import func
    from src.api.routes.surveys import SimulatedSurveyEvent
    from src.models.organization import Organization
    from src.models.customer_health import CustomerHealth
    from src.models.survey import SurveyInstance, SurveyInvitation, SurveyResident, SurveyEmailOptOut, MaintenanceOccurrence
    from src.services.surveys import ingest_simulated_event, public_base_url

    org = os.getenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', '')
    if (os.getenv('BOOMSAY_REVIEW_PREVIEW', '').lower() != 'true' or not org.isdecimal()
            or public_base_url() != BASE or not re.fullmatch(r'[a-z0-9-]{1,40}', test_id)):
        raise ValueError('Requires the existing local preview and a simple test name. Nothing sent.')
    if event_type not in EVENT_LABELS:
        raise ValueError('Unknown survey type. Nothing sent.')
    org_id = int(org)
    community = db.get(Organization, org_id)
    if not community or community.name != 'Lake House Apartments':
        raise ValueError('Expected Lake House Apartments in the configured preview. Nothing sent.')
    identity = 'boomsay-email-test-' + test_id
    survey = db.query(SurveyInstance).join(MaintenanceOccurrence).filter(
        SurveyInstance.organization_id == org_id, MaintenanceOccurrence.event_id == identity).first()
    if survey is None:
        if action != 'prepare':
            raise ValueError('Prepare and review this test first. Nothing sent.')
        class PreviewEmailEvent(SimulatedSurveyEvent):
            resident_email: Literal['andres.feuerberg.ch@gmail.com']
        context = {'ticket_id': 'EMAIL-TEST-' + test_id, 'request_description': 'a fictional leaking kitchen faucet'} if event_type == 'maintenance_completed' else {}
        event = PreviewEmailEvent(
            community_id=org_id, event_id=identity, occurrence_id=identity,
            event_type=event_type, occurred_at=datetime.now(timezone.utc), **context,
            resident_id=identity, resident_name='Andres (fictional email test)', resident_email=RECIPIENT,
            unit_id=identity, unit_number='EMAIL-TEST', is_simulated=True)
        survey = ingest_simulated_event(db, event)
    invitation = survey.invitation
    if (survey.occurrence.event_type != event_type or not survey.occurrence.is_simulated or invitation.recipient != RECIPIENT
            or survey.occurrence.resident_email != RECIPIENT):
        raise ValueError('Test identity does not match. Nothing sent.')
    url = BASE + '/survey/' + survey.token
    if event_type == 'maintenance_completed':
        prompt = 'Please tell us about your recent maintenance experience at Lake House Apartments.'
        disclosure = 'This is a BoomSay test using a fictional maintenance request.'
        subject = 'Lake House Apartments: how was your maintenance experience?'
    else:
        prompt = survey.questionnaire_snapshot['title']
        disclosure = f'This is a BoomSay test using a fictional {EVENT_LABELS[event_type].lower()} event.'
        subject = 'Lake House Apartments: ' + prompt
    text = (f'Hi Andres,\n\n{prompt}\n\nTake survey: {url}\n\n{disclosure}\n\n'
            f'Stop survey invitations: {url}/unsubscribe')
    html = (f'<p>Hi Andres,</p><p>{escape(prompt)}</p>'
            f'<p><a href="{escape(url, quote=True)}">Take survey</a></p><p>{escape(disclosure)}</p>'
            f'<p><a href="{escape(url, quote=True)}/unsubscribe">Stop survey invitations</a></p>')
    payload = {'from': SENDER, 'to': [RECIPIENT], 'subject': subject, 'text': text, 'html': html}
    if action == 'reserve':
        suppressed = (db.get(SurveyEmailOptOut, (org_id, RECIPIENT)) or
            db.query(SurveyResident.id).filter(SurveyResident.organization_id == org_id,
                func.lower(SurveyResident.email) == RECIPIENT, SurveyResident.email_opt_out.is_(True)).first() or
            db.query(CustomerHealth.id).filter(CustomerHealth.organization_id == org_id,
                func.lower(CustomerHealth.customer_email) == RECIPIENT, CustomerHealth.outreach_opt_out.is_(True)).first())
        if suppressed or survey.status != 'pending':
            raise ValueError('This address opted out or the survey is already completed. Nothing sent.')
        # Atomic compare-and-set: concurrent helpers cannot both claim the invitation.
        changed = db.query(SurveyInvitation).filter_by(id=invitation.id, status='simulated', is_simulated=True).update({
            'status': 'email_test_reserved', 'is_simulated': False,
            'subject': payload['subject'], 'text': text, 'html': html}, synchronize_session=False)
        if changed != 1:
            db.rollback()
            raise ValueError('A send was already attempted or this invitation is suppressed. No duplicate sent.')
        db.commit()
    elif action in ('accepted', 'failed'):
        changed = db.query(SurveyInvitation).filter_by(id=invitation.id, status='email_test_reserved', is_simulated=False).update(
            {'status': 'email_test_' + action}, synchronize_session=False)
        if changed != 1:
            db.rollback()
            raise ValueError('No reserved test attempt to update.')
        db.commit()
    elif action != 'prepare':
        raise ValueError('Unknown test action')
    return {'payload': payload, 'idempotency_key': 'boomsay-email-test/' + survey.public_id,
            'status': db.get(SurveyInvitation, invitation.id, populate_existing=True).status}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'reserve', 'accepted', 'failed'])
    parser.add_argument('test_id')
    parser.add_argument('--event-type', choices=list(EVENT_LABELS), default='maintenance_completed')
    args = parser.parse_args()
    from src.database.session import SessionLocal
    with SessionLocal() as db:
        try:
            print(json.dumps(operate(db, args.action, args.test_id, args.event_type)))
        except ValueError as exc:
            raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()

"""Prepare one named fictional lifecycle occurrence; never send or submit answers."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
import re

from src.services.survey_catalog import EVENT_LABELS


def prepare(db, community_id: int, event_type: str, test_id: str):
    from src.api.routes.surveys import SimulatedSurveyEvent
    from src.services.surveys import ingest_simulated_event
    from src.services.review_preview import require_preview_organization
    from src.models.survey import SurveyResident, SurveyUnit

    if os.getenv('BOOMSAY_SURVEY_SIMULATION', '').lower() != 'true':
        raise ValueError('Enable BOOMSAY_SURVEY_SIMULATION for this fictional demo first')
    require_preview_organization(community_id)
    if not re.fullmatch(r'[a-z0-9-]{1,50}', test_id) or event_type not in EVENT_LABELS:
        raise ValueError('Choose a supported survey type and a short lowercase test identifier')
    identity = f'fictional-lifecycle-{test_id}-{event_type}'
    email = f'{test_id}-{event_type}@example.invalid'
    resident = db.query(SurveyResident).filter_by(organization_id=community_id, resident_id=identity).first()
    unit = db.query(SurveyUnit).filter_by(organization_id=community_id, unit_id=identity).first()
    if resident and (not resident.is_simulated or resident.email != email):
        raise ValueError('This fictional identifier is already in use; nothing changed')
    if unit and unit.number != 'DEMO-LIFECYCLE':
        raise ValueError('This fictional unit identifier is already in use; nothing changed')
    values = dict(event_id=identity, occurrence_id=identity, event_type=event_type,
                  community_id=community_id, occurred_at=datetime.now(timezone.utc),
                  resident_id=identity, resident_name=f'Fictional {EVENT_LABELS[event_type]} resident',
                  resident_email=email, unit_id=identity, unit_number='DEMO-LIFECYCLE', is_simulated=True)
    if event_type == 'maintenance_completed':
        values.update(ticket_id=f'FICTIONAL-{test_id}', request_description='a fictional kitchen faucet repair')
    return ingest_simulated_event(db, SimulatedSurveyEvent(**values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--community-id', type=int, required=True)
    parser.add_argument('--event', choices=tuple(EVENT_LABELS), required=True)
    parser.add_argument('--test-id', required=True, help='Reuse this ID to reopen the same occurrence')
    args = parser.parse_args()
    from src.database.session import SessionLocal
    with SessionLocal() as db:
        row = prepare(db, args.community_id, args.event, args.test_id)
        print(f'{EVENT_LABELS[args.event]}: {row.invitation.survey_url}')
        print('Prepared fictional survey only. No email sent. Existing answers are preserved.')


if __name__ == '__main__':
    main()

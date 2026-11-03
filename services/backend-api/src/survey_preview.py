"""Create one fictional survey in the configured, existing local BoomSay preview.

No initialization, credential changes, live email, model calls or answer submission.
Repeating the command returns the same invitation and preserves saved answers.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os


def simulate_preview(db):
    from src.api.routes.surveys import MaintenanceCompletedEvent
    from src.models.organization import Organization
    from src.models.survey import SurveyResident, SurveyUnit
    from src.services.surveys import ingest_simulated_event, public_base_url

    community = os.getenv('BOOMSAY_PREVIEW_ORGANIZATION_ID', '')
    if os.getenv('BOOMSAY_REVIEW_PREVIEW', '').lower() != 'true' or not community.isdecimal() or int(community) < 1:
        raise ValueError('This command requires the configured local BoomSay review preview. Nothing changed.')
    if public_base_url() != 'http://127.0.0.1:53004':
        raise ValueError('This command is only for the existing preview on http://127.0.0.1:53004. Nothing changed.')
    org_id = int(community)
    if db.get(Organization, org_id) is None:
        raise ValueError('The configured preview community was not found. Nothing changed.')
    resident_id, unit_id = 'boomsay-fictional-preview-resident', 'boomsay-fictional-preview-unit'
    resident = db.query(SurveyResident).filter_by(organization_id=org_id, resident_id=resident_id).first()
    unit = db.query(SurveyUnit).filter_by(organization_id=org_id, unit_id=unit_id).first()
    if resident and (not resident.is_simulated or resident.email != 'preview-resident@example.invalid'):
        raise ValueError('The fictional resident identifier is already in use. Nothing changed.')
    if unit and unit.number != 'DEMO-204':
        raise ValueError('The fictional unit identifier is already in use. Nothing changed.')
    event = MaintenanceCompletedEvent(
        community_id=org_id, event_id='boomsay-fictional-preview-maintenance-001',
        occurrence_id='boomsay-fictional-preview-occurrence-001', event_type='maintenance_completed',
        ticket_id='DEMO-WO-1001', request_description='a fictional leaking kitchen faucet',
        completed_at=datetime.now(timezone.utc), resident_id=resident_id,
        resident_name='Jamie Example (fictional)', resident_email='preview-resident@example.invalid',
        unit_id=unit_id, unit_number='DEMO-204', is_simulated=True)
    row = ingest_simulated_event(db, event)
    if not row.invitation or not row.invitation.is_simulated:
        raise ValueError('No simulated invitation is available.')
    return row


def main():
    from src.database.session import SessionLocal
    with SessionLocal() as db:
        try:
            row = simulate_preview(db)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        print(row.invitation.survey_url)


if __name__ == '__main__':
    main()

"""Apply community timing and opt-outs to the simulated survey workflow."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta

from sqlalchemy import func, or_, select

from src.models.customer_health import CustomerHealth
from src.models.survey import SurveyEmailOptOut, SurveyInstance, SurveyInvitation, SurveyOccurrence, SurveyResident, utcnow
from src.services.agent_settings import survey_settings
from src.services.review_preview import preview_organization_id
from src.services.survey_delivery import SimulatedSurveySender


def suppression_reason(db, survey, settings):
    occurrence = survey.occurrence
    email = occurrence.resident_email.lower()
    org_id = survey.organization_id
    if not settings.schedule[occurrence.event_type].enabled:
        return 'suppressed_disabled'
    if survey.submitted_at is not None:
        return 'suppressed_submitted'
    if (occurrence.resident.email_opt_out or db.get(SurveyEmailOptOut, (org_id, email))
            or db.query(SurveyResident.id).filter(
                SurveyResident.organization_id == org_id,
                func.lower(SurveyResident.email) == email,
                SurveyResident.email_opt_out.is_(True)).first()
            or db.query(CustomerHealth.id).filter(
                CustomerHealth.organization_id == org_id,
                func.lower(CustomerHealth.customer_email) == email,
                CustomerHealth.outreach_opt_out.is_(True)).first()):
        return 'suppressed_opt_out'
    return None


def cancel_simulated_work(db, survey_ids, reason):
    """Stop any outstanding simulated invitation/reminder without rewriting delivery history."""
    pending = db.query(SurveyInvitation).filter(
        SurveyInvitation.survey_id.in_(survey_ids), SurveyInvitation.is_simulated.is_(True))
    pending.filter(SurveyInvitation.status == 'scheduled').update(
        {SurveyInvitation.status: reason}, synchronize_session=False)
    pending.filter(SurveyInvitation.reminder_due_at.is_not(None)).update(
        {SurveyInvitation.reminder_due_at: None}, synchronize_session=False)


def cancel_paused_simulations(db, organization_id, settings):
    disabled = [kind for kind, entry in settings.schedule.items() if not entry.enabled]
    if disabled:
        affected = select(SurveyInstance.id).join(SurveyOccurrence).where(
            SurveyInstance.organization_id == organization_id, SurveyOccurrence.event_type.in_(disabled))
        cancel_simulated_work(db, affected, 'suppressed_disabled')
    if settings.reminder_hours is None:
        db.query(SurveyInvitation).filter_by(
            organization_id=organization_id, is_simulated=True).filter(
            SurveyInvitation.reminder_due_at.is_not(None)).update(
            {SurveyInvitation.reminder_due_at: None}, synchronize_session=False)


def simulate_initial(invitation, settings, now):
    invitation.status = SimulatedSurveySender().send(invitation)
    if settings.reminder_hours is not None:
        invitation.reminder_due_at = now + timedelta(hours=settings.reminder_hours)


def schedule_invitation(db, survey, invitation, event_time):
    settings = survey_settings(db, survey.organization_id)
    suppressed = suppression_reason(db, survey, settings)
    if suppressed:
        invitation.status = suppressed
        return
    now = utcnow()
    entry = settings.schedule[survey.occurrence.event_type]
    due_at = event_time + timedelta(hours=entry.delay_hours)
    if due_at > now:
        invitation.scheduled_for = due_at
        invitation.status = 'scheduled'
    else:
        simulate_initial(invitation, settings, now)


def process_due_simulations(db, now=None, batch_size=100):
    """Only simulated rows enter this queue; a marker prevents reminder replays."""
    now = now or utcnow()
    due = db.query(SurveyInvitation).filter(
        SurveyInvitation.is_simulated.is_(True),
        or_((SurveyInvitation.status == 'scheduled') & (SurveyInvitation.scheduled_for <= now),
            (SurveyInvitation.status == 'simulated') & (SurveyInvitation.reminder_due_at <= now)
            & SurveyInvitation.reminder_simulated_at.is_(None)),
    )
    bound = preview_organization_id()
    if bound is not None:
        due = due.filter(SurveyInvitation.organization_id == bound)
    rows = due.order_by(SurveyInvitation.id).limit(batch_size).with_for_update(skip_locked=True).all()
    for invite in rows:
        settings = survey_settings(db, invite.organization_id)
        suppressed = suppression_reason(db, invite.survey, settings)
        if invite.status == 'scheduled':
            if suppressed:
                invite.status = suppressed
            else:
                simulate_initial(invite, settings, now)
        else:
            if not suppressed and settings.reminder_hours is not None:
                SimulatedSurveySender().send(invite)
                invite.reminder_simulated_at = now
            invite.reminder_due_at = None
    db.commit()
    return len(rows)


@asynccontextmanager
async def simulated_delivery_timer():
    """Check the durable preview queue while the API runs; catch up after restart."""
    if os.getenv('BOOMSAY_SURVEY_SIMULATION', '').lower() != 'true':
        yield
        return
    from src.database.session import SessionLocal
    stop = asyncio.Event()

    def tick():
        with SessionLocal() as db:
            process_due_simulations(db)

    async def run():
        while not stop.is_set():
            try:
                await asyncio.to_thread(tick)
            except Exception:
                logging.getLogger(__name__).exception('Survey simulation timer failed')
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass

    runner = asyncio.create_task(run())
    try:
        yield
    finally:
        stop.set()
        await runner

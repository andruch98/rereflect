"""Draft, approve and edit one community's replies without publishing to review platforms."""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.agent_settings import CommunityAgentSettings
from src.models.feedback import FeedbackItem
from src.models.feedback_workflow_event import FeedbackWorkflowEvent
from src.models.organization import Organization
from src.models.review_reply import ReviewReply
from src.services.agent_settings import review_section
from src.services.review_preview import require_preview_organization
from src.services.review_reply_writer import ReviewWriterError, approval_policy, write_reply

logger = logging.getLogger(__name__)
APARTMENT_SOURCES = ('apartment_review_ai', 'apartment_review_fallback')


def scoped_review(db: Session, org_id, review_id, lock=False):
    require_preview_organization(org_id)
    query = db.query(FeedbackItem).filter(FeedbackItem.organization_id == org_id,
                                        FeedbackItem.id == review_id, FeedbackItem.source.in_(APARTMENT_SOURCES))
    # Serialize the first draft, retries and manager edits even before a reply row exists.
    if lock:
        query = query.with_for_update()
    review = query.one_or_none()
    if review is None:
        raise HTTPException(404, 'Review not found.')
    return review


def utc_time(value):
    # SQLite drops offsets. Approval timestamps are created in UTC.
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def view(reply, review_id, settings_version):
    return {'review_id': review_id, 'settings_confirmed': settings_version > 0, 'publishing_connected': False,
            'uses_previous_settings': bool(reply and reply.settings_version < settings_version),
            'status': reply.status if reply else 'not_drafted', 'text': reply.text if reply else '',
            'reason': reply.reason if reply else '', 'version': reply.version if reply else 0,
            'generation_method': reply.generation_method if reply else None, 'error': reply.error if reply else None,
            'approved_by': reply.approved_by if reply else None, 'approved_at': utc_time(reply.approved_at) if reply else None,
            'published_at': utc_time(reply.published_at) if reply else None}


def audit(db, review, reply, event, before, user_id):
    db.add(FeedbackWorkflowEvent(feedback_id=review.id, organization_id=review.organization_id,
        actor_id=user_id, event_type=event, old_value=before, new_value=reply.status,
        metadata_={'version': reply.version, 'settings_version': reply.settings_version,
                   'reason': reply.reason, 'generation_method': reply.generation_method}))


async def draft(db, org, review_id, user_id=None):
    review = scoped_review(db, org.id, review_id, lock=True)
    setup = review_section(db, org)
    if not setup.configured:
        raise HTTPException(409, 'Confirm Review Responses in Agent Settings before drafting a reply.')
    reply = db.get(ReviewReply, review.id)
    if reply and reply.status != 'failed':
        return view(reply, review.id, setup.version)
    before = reply.status if reply else 'not_drafted'
    if reply is None:
        reply = ReviewReply(review_id=review.id, version=1)
        db.add(reply)
    else:
        reply.version += 1
    reply.settings_version = setup.version
    current_version = setup.version
    try:
        reply.text, reply.generation_method, reply.generation_usage = await write_reply(
            db, org.id, setup.values, review.text or '', review.star_rating,
            (review.source_metadata or {}).get('author_name') if isinstance(review.source_metadata, dict) else None)
    except Exception as exc:
        # Never echo raw provider exceptions, which can include credentials or private review text.
        logger.warning('Review draft failed for review %s (%s)', review.id, type(exc).__name__)
        reply.status, reply.text = 'failed', ''
        reply.reason = 'BoomSay could not generate a draft.'
        reply.error = str(exc) if isinstance(exc, ReviewWriterError) else 'Check the community’s AI connection and try again.'
        reply.generation_method, reply.generation_usage = None, None
    else:
        # A manager may have changed the contacts or approval policy during generation.
        # Lock only for this final decision; the manager can save while the writer runs.
        with db.no_autoflush:
            current_version = db.scalar(select(CommunityAgentSettings.version).where(
                CommunityAgentSettings.organization_id == org.id,
                CommunityAgentSettings.section == 'reviews',
            ).with_for_update(read=True))
        if current_version == setup.version:
            reply.status, reply.reason = approval_policy(setup.values, review.text, review.star_rating)
        else:
            reply.status = 'pending_approval'
            reply.reason = 'Review settings changed while this draft was being prepared.'
        reply.error = None
        if reply.status == 'approved':
            reply.approved_by = 'BoomSay'
            reply.approved_at = datetime.now(timezone.utc)
    audit(db, review, reply, 'review_reply_drafted' if reply.status != 'failed' else 'review_reply_failed', before, user_id)
    db.commit()
    return view(reply, review.id, current_version or 0)


def change_draft(db, user, review_id, version, text, approve):
    review = scoped_review(db, user.organization_id, review_id, lock=True)
    reply = db.get(ReviewReply, review.id)
    if not reply or reply.version != version:
        raise HTTPException(409, 'This reply changed. Reload it before saving.')
    if reply.status not in {'pending_approval', 'approved'}:
        raise HTTPException(409, 'Only a draft or an unpublished approved reply can be edited.')
    if text is not None:
        reply.text = text
    before = reply.status
    if approve:
        reply.status, reply.reason = 'approved', 'Approved by a community manager.'
        reply.approved_at = datetime.now(timezone.utc)
        reply.approved_by = user.email
    else:
        reply.status, reply.reason = 'pending_approval', 'This edited reply is waiting for manager approval.'
        reply.approved_at, reply.approved_by = None, None
    reply.version += 1
    audit(db, review, reply, 'review_reply_approved' if approve else 'review_reply_edited', before, user.id)
    db.commit()
    return view(reply, review.id, review_section(db, user.organization).version)


async def draft_new_reviews(org_id, review_ids):
    """After the import commits, prepare only its new reviews for an opted-in community."""
    from src.database.session import SessionLocal
    with SessionLocal() as db:
        try:
            require_preview_organization(org_id)
            org = db.get(Organization, org_id)
            if org is None or not review_section(db, org).configured:
                return
        except HTTPException:
            return
        for review_id in review_ids:
            try:
                await draft(db, org, review_id)
            except Exception as exc:
                db.rollback()
                logger.warning('New review draft unavailable for review %s (%s)', review_id, type(exc).__name__)

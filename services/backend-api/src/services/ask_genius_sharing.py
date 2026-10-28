"""Allowlisted public snapshots, containing only the chat and its attached evidence.

The capability token is stored only as a hash. Public reads never query conversation
messages or feedback records: subsequent changes cannot broaden an existing share.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from src.models.conversation_message import ConversationMessage
from src.models.feedback import FeedbackItem
from src.services import ask_genius as service
from src.services.ask_genius_periods import Period

MAX_SNAPSHOT_MESSAGES = 1000
MAX_SNAPSHOT_BYTES = 2_000_000
TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9_-]{43}$')


class ReviewSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    original_review: str
    star_rating: int | None = None
    original_posting_date: str | None = None
    saved_analysis: dict


class SourceSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_id: int = Field(gt=0)
    label: str
    excerpt: str
    excerpt_truncated: bool = False
    kind: str
    topic: str | None = None
    review: ReviewSnapshot


class MessageMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str = 'ask_genius'
    sources: list[SourceSnapshot]
    period: Period | None = None
    period_label: str | None = None


class SnapshotMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int
    role: str
    content: str
    created_at: str
    structured_data: MessageMetadata | None = None


class PublicSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    created_at: str
    messages: list[SnapshotMessage]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def _iso(value: datetime) -> str:
    return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat()


def _source_snapshot(source: dict, row: FeedbackItem, local_id: int) -> dict:
    original = row.text or ''
    excerpt = source.get('excerpt')
    truncated = source.get('excerpt_truncated') is True
    if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in original:
        # Legacy sources have only a review ID and link. Use actual content as the label.
        excerpt = original[:300] if original.strip() else 'Rating only - no written review'
        truncated = len(original) > 300
    analysis = service.read_saved_analysis(row.apartment_analysis)
    topic = source.get('topic')
    known_topic = next((t['name'] for t in analysis.get('topics', []) if t['name'] == topic), None)
    return {
        'review_id': local_id,  # snapshot-local, never a live feedback identifier
        'kind': 'analysis' if source.get('kind') == 'analysis' else 'review',
        'label': excerpt, 'excerpt': excerpt, 'excerpt_truncated': truncated,
        **({'topic': known_topic} if known_topic else {}),
        'review': {'original_review': original, 'star_rating': row.star_rating,
                   'original_posting_date': row.review_date.isoformat() if row.review_date else None,
                   'saved_analysis': analysis},
    }


def build_snapshot(conversation, db) -> dict:
    messages = db.query(ConversationMessage).filter_by(conversation_id=conversation.id).order_by(
        ConversationMessage.id).limit(MAX_SNAPSHOT_MESSAGES + 1).all()
    if len(messages) > MAX_SNAPSHOT_MESSAGES:
        raise ValueError('This chat is too large to share. Start a shorter chat with the findings you want to share.')
    if not messages:
        raise ValueError('Send a message before sharing this chat.')
    requested_ids = set()
    for message in messages:
        metadata = message.structured_data if isinstance(message.structured_data, dict) else {}
        for source in metadata.get('sources', []) if isinstance(metadata.get('sources'), list) else []:
            if isinstance(source, dict) and type(source.get('review_id')) is int:
                requested_ids.add(source['review_id'])
    # Revalidate ownership even for stored metadata. Never trust a source's supplied href
    # or embedded document as authority to publish a different community's data.
    rows = db.query(FeedbackItem).filter(
        FeedbackItem.organization_id == conversation.organization_id,
        FeedbackItem.source.in_(service.SOURCES),
        FeedbackItem.id.in_(requested_ids),
    ).all() if requested_ids else []
    authorized = {row.id: row for row in rows}
    local_ids = {key: index for index, key in enumerate(sorted(authorized), 1)}
    published = []
    for message in messages:
        if message.role not in {'user', 'assistant'}:
            continue
        metadata = message.structured_data if isinstance(message.structured_data, dict) else {}
        sources = []
        replacements = {}
        for source in metadata.get('sources', []) if isinstance(metadata.get('sources'), list) else []:
            if not isinstance(source, dict) or type(source.get('review_id')) is not int:
                continue
            row = authorized.get(source['review_id'])
            if row is None:
                continue
            copied = _source_snapshot(source, row, local_ids[row.id])
            if copied not in sources:
                sources.append(copied)
            replacements[row.id] = copied['excerpt']
        content = message.content
        if message.role == 'assistant':
            # Older chats rendered authenticated review links inline. They must not send
            # a public reader to private routes, or use opaque review-number labels.
            content = re.sub(r'\[[^\]]*\]\(/feedbacks/(\d+)\)',
                             lambda m: re.sub(r'([\\`*_{}\[\]<>()#+!|])', r'\\\1',
                                              replacements.get(int(m[1]), 'Supporting review unavailable')),
                             content)
        item = {'id': len(published) + 1, 'role': message.role, 'content': content,
                'created_at': _iso(message.created_at)}
        if message.role == 'assistant':
            cleaned = {'kind': 'ask_genius', 'sources': sources}
            if isinstance(metadata.get('period'), dict):
                try:
                    cleaned['period'] = Period.model_validate(metadata['period']).model_dump(mode='json', exclude_none=True)
                except ValueError:
                    pass
            if isinstance(metadata.get('period_label'), str):
                cleaned['period_label'] = metadata['period_label'][:200]
            item['structured_data'] = cleaned
        published.append(item)
    snapshot = PublicSnapshot.model_validate({
        'title': conversation.title or 'Shared chat', 'created_at': _iso(datetime.utcnow()), 'messages': published,
    }).model_dump(mode='json', exclude_none=True)
    if len(json.dumps(snapshot, ensure_ascii=False).encode('utf-8')) > MAX_SNAPSHOT_BYTES:
        raise ValueError('This chat contains too much material to share. Start a shorter chat with the findings you want to share.')
    return snapshot

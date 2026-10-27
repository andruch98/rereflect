"""Private community questions, personal chat history and explicit personal period preferences."""
from __future__ import annotations

import os
import openai
import time
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.database.session import get_db
from src.models.conversation import Conversation
from src.models.conversation_message import ConversationMessage
from src.models.user import User
from src.services import ask_genius as service
from src.services.ask_genius_periods import Period, parse_question_period, preference_command, resolve_period
from src.services.review_preview import require_preview_organization

router = APIRouter(prefix='/api/v1/ask-genius', tags=['ask-genius'])
_locks: dict[tuple[int, int], threading.Lock] = {}
_locks_guard = threading.Lock()


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[UUID] = None
    request_id: UUID = Field(default_factory=uuid4)
    period: Optional[Period] = None


class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    default_period: Optional[Period]


def authorize(user: User) -> None:
    # This first increment must never become an unscoped general endpoint.
    if os.getenv('BOOMSAY_REVIEW_PREVIEW', '').lower() != 'true':
        raise HTTPException(404, 'Ask Genius preview is not enabled')
    require_preview_organization(user.organization_id)


def conversations_for(user, db):
    return db.query(Conversation).filter(Conversation.organization_id == user.organization_id,
                                        Conversation.created_by_user_id == user.id,
                                        Conversation.context_scope == service.SCOPE,
                                        Conversation.is_active.is_(True))


def owned_conversation(public_id, user, db):
    conversation = conversations_for(user, db).filter(Conversation.public_id == str(public_id)).first()
    if conversation is None:
        raise HTTPException(404, 'Conversation not found')
    return conversation


@contextmanager
def single_question(user, db):
    """Reject overlap locally and across PostgreSQL application workers."""
    key = (user.organization_id, user.id)
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(409, 'A question is already being answered. Please wait.')
    connection = None
    acquired_db = False
    try:
        if db.get_bind().dialect.name == 'postgresql':
            connection = db.get_bind().connect()
            # Dedicated session-level lock survives the chat audit commits below.
            acquired_db = bool(connection.execute(text('SELECT pg_try_advisory_lock(:namespace, :user_id)'),
                                                   {'namespace': 170171, 'user_id': user.id}).scalar())
            if not acquired_db:
                raise HTTPException(409, 'A question is already being answered. Please wait.')
        yield
    finally:
        try:
            if connection is not None:
                try:
                    if acquired_db:
                        connection.execute(text('SELECT pg_advisory_unlock(:namespace, :user_id)'),
                                           {'namespace': 170171, 'user_id': user.id})
                finally:
                    connection.close()
        finally:
            lock.release()


def period_dict(period: Period | None) -> dict | None:
    return period.model_dump(mode='json', exclude_none=True) if period else None


def default_period_for(user: User) -> Period | None:
    stored = user.ask_genius_default_period
    return Period.model_validate(stored) if stored else None


def conversation_period(conversation, db) -> Period | None:
    if conversation is None:
        return None
    latest = db.query(ConversationMessage).filter_by(conversation_id=conversation.id, role='assistant').order_by(ConversationMessage.id.desc()).first()
    stored = (latest.structured_data or {}).get('period') if latest and isinstance(latest.structured_data, dict) else None
    return Period.model_validate(stored) if stored else None


def answer_payload(conversation, message):
    metadata = message.structured_data or {}
    return {'conversation_id': conversation.public_id, 'title': conversation.title,
            'answer': message.content, 'message_id': message.id, 'structured_data': metadata,
            'period': metadata.get('period'), 'period_label': metadata.get('period_label'),
            'default_period': metadata.get('default_period'),
            'preference_updated': metadata.get('preference_updated', False)}


@router.get('/status')
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user)
    _, reason = service.configured_llm(user.organization_id, db)
    return {'ready': reason is None, 'reason': reason,
            'default_period': period_dict(default_period_for(user)),
            'available_sources': ['reviews', 'analysis'], 'timezone': 'America/New_York',
            'date_coverage': service.date_coverage(user.organization_id, db)}


@router.put('/preferences')
def update_preferences(body: Preferences, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user)
    if body.default_period:
        try:
            resolve_period(body.default_period)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
    with single_question(user, db):
        user.ask_genius_default_period = period_dict(body.default_period)
        db.commit()
    return {'default_period': period_dict(default_period_for(user))}


@router.get('/conversations')
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user)
    rows = conversations_for(user, db).order_by(Conversation.updated_at.desc(), Conversation.id.desc()).all()
    return {'conversations': [{'public_id': c.public_id, 'title': c.title, 'updated_at': c.updated_at} for c in rows], 'total': len(rows)}


@router.get('/conversations/{public_id}')
def get_conversation(public_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user)
    conversation = owned_conversation(public_id, user, db)
    messages = db.query(ConversationMessage).filter_by(conversation_id=conversation.id).order_by(ConversationMessage.id).all()
    # Audit context/provider payloads are deliberately not part of the client API.
    return {'public_id': conversation.public_id, 'title': conversation.title,
            'period': period_dict(conversation_period(conversation, db)),
            'messages': [{'id': m.id, 'role': m.role, 'content': m.content,
                          'structured_data': m.structured_data, 'created_at': m.created_at} for m in messages]}


@router.post('/questions')
async def ask_question(body: Question, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user)
    question = body.question.strip()
    if not question:
        raise HTTPException(422, 'Enter a question first')
    conversation = owned_conversation(body.conversation_id, user, db) if body.conversation_id else None
    requested_period = period_dict(body.period)
    request_binding = {'question': question, 'conversation_id': str(body.conversation_id) if body.conversation_id else None,
                       'period': requested_period}
    with single_question(user, db):
        previous = db.query(ConversationMessage).join(Conversation).filter(
            Conversation.organization_id == user.organization_id,
            Conversation.created_by_user_id == user.id,
            Conversation.context_scope == service.SCOPE,
            ConversationMessage.role == 'user',
            ConversationMessage.raw_request['request_id'].as_string() == str(body.request_id),
        ).first()
        if previous:
            previous_state = previous.raw_request or {}
            old_binding = previous_state.get('binding')
            if old_binding != request_binding:
                raise HTTPException(409, 'That request identifier was already used for another question or period.')
            if previous_state.get('status') == 'completed':
                response = db.query(ConversationMessage).filter_by(id=previous_state['answer_message_id'], conversation_id=previous.conversation_id).one()
                prior_conversation = owned_conversation(db.get(Conversation, previous.conversation_id).public_id, user, db)
                return answer_payload(prior_conversation, response)
            if previous_state.get('status') == 'failed':
                raise HTTPException(502, {'code': 'ask_genius_failed', 'message': 'This answer could not be completed. Ask again to start a new request.'})
            raise HTTPException(409, 'This question was already attempted. Check its conversation before asking again.')

        history = []
        if conversation:
            recent = db.query(ConversationMessage).filter_by(conversation_id=conversation.id).order_by(ConversationMessage.id.desc()).limit(10).all()
            history = [{'role': m.role, 'content': m.content} for m in reversed(recent)]
        prior_period = conversation_period(conversation, db)
        saved_default = default_period_for(user)
        try:
            command = preference_command(question)
            explicit_period = parse_question_period(question)
            selected = explicit_period or body.period or prior_period or saved_default
            local_answer = None
            preference_updated = False
            if command:
                action, command_period = command
                if action == 'clear':
                    next_default = None
                    # Clearing a default affects future conversations, not the current period.
                    selected = body.period or prior_period
                    local_answer = 'Your default period has been removed. Choose a period when starting a new conversation.'
                else:
                    selected = command_period or body.period or prior_period
                    if selected is None:
                        raise ValueError('Choose the period you want to save as your default first.')
                    next_default = period_dict(selected)
                    label = resolve_period(selected)['label']
                    local_answer = f'Your default period is now {label}. New conversations will use it until you change or remove it.'
                preference_updated = True
            elif selected is None:
                raise ValueError('Choose a period before asking a question, or explicitly save a default period.')
            if selected:
                resolve_period(selected)
            if command:
                user.ask_genius_default_period = next_default
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

        evidence = None
        if local_answer is None:
            try:
                evidence = service.build_evidence(user.organization_id, db, selected)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            local_answer = service.no_data_answer(evidence)
        expanded = service.evidence_requested(question, history)
        config = None
        messages = []
        if local_answer is None:
            config, reason = service.configured_llm(user.organization_id, db)
            if config is None:
                raise HTTPException(503, reason)
            messages = service.build_messages(question, evidence, history, expanded, period_dict(saved_default))
        if conversation is None:
            conversation = Conversation(organization_id=user.organization_id, created_by_user_id=user.id,
                                        title=question[:100], context_scope=service.SCOPE)
            db.add(conversation)
            db.flush()
        audit = {'request_id': str(body.request_id), 'binding': request_binding, 'status': 'attempted',
                 'messages': messages, 'period': period_dict(selected),
                 'resolved_period': resolve_period(selected) if selected else None,
                 'evidence_requested': expanded, 'preference_updated': preference_updated,
                 'model': config.model if config else None, 'provider': config.provider if config else None,
                 'max_completion_tokens': 1200 if config else 0, 'max_retries': 0}
        user_message = ConversationMessage(conversation_id=conversation.id, role='user', content=question,
                                           context_scope=service.SCOPE, raw_request=audit,
                                           llm_provider=config.provider if config else None,
                                           llm_model=config.model if config else None)
        db.add(user_message)
        db.commit()  # Persist explicit preference changes / attempted model requests before returning.
        started = time.monotonic()
        sources = []
        result = None
        if local_answer is None:
            try:
                result = await service.generate_answer(messages, config)
                user_message.raw_response = result.raw_response
                user_message.tokens_in = result.tokens_in
                user_message.tokens_out = result.tokens_out
                if not result.answer or result.finish_reason != 'stop':
                    raise ValueError('IncompleteModelAnswer')
                answer_text, sources = service.validate_answer(result.answer, evidence, expanded)
            except Exception as exc:
                safe_error = ('InvalidModelAnswer' if isinstance(exc, ValueError) else
                              'ProviderTimeout' if isinstance(exc, openai.APITimeoutError) else
                              'ProviderHTTPError' if isinstance(exc, openai.APIStatusError) else 'ProviderRequestFailed')
                user_message.raw_request = {**audit, 'status': 'failed', 'error': safe_error,
                                            'http_status': exc.status_code if isinstance(exc, openai.APIStatusError) else None}
                user_message.latency_ms = int((time.monotonic() - started) * 1000)
                db.commit()
                message = ('Ask Genius could not return a complete answer within its format and length limits. Please try a narrower question.'
                           if safe_error == 'InvalidModelAnswer' else
                           'The AI connection timed out. Please try your question again.'
                           if safe_error == 'ProviderTimeout' else
                           'Ask Genius could not reach its AI connection. Please try your question again.')
                raise HTTPException(502, {'code': 'ask_genius_failed', 'message': message}) from None
        else:
            answer_text = local_answer
        metadata = {'kind': 'ask_genius', 'period': period_dict(selected),
                    'period_label': resolve_period(selected)['label'] if selected else None,
                    'default_period': period_dict(default_period_for(user)),
                    'preference_updated': preference_updated, 'sources': sources}
        answer = ConversationMessage(conversation_id=conversation.id, role='assistant', content=answer_text,
                                     structured_data=metadata, context_scope=service.SCOPE, query_type='analysis',
                                     llm_provider=config.provider if config else None, llm_model=config.model if config else None,
                                     tokens_in=result.tokens_in if result else None, tokens_out=result.tokens_out if result else None,
                                     cost_cents=None, latency_ms=int((time.monotonic() - started) * 1000))
        db.add(answer)
        db.flush()
        user_message.raw_request = {**audit, 'status': 'completed', 'answer_message_id': answer.id}
        user_message.tokens_in = None
        user_message.tokens_out = None
        conversation.updated_at = datetime.utcnow()
        db.commit()
        return answer_payload(conversation, answer)

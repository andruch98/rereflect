"""Private, one-community Ask Genius. Writes chat history only, never feedback."""
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
from src.services.review_preview import require_preview_organization

router = APIRouter(prefix='/api/v1/ask-genius', tags=['ask-genius'])
_locks: dict[tuple[int, int], threading.Lock] = {}
_locks_guard = threading.Lock()


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[UUID] = None
    request_id: UUID = Field(default_factory=uuid4)


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


def answer_payload(conversation, message):
    return {'conversation_id': conversation.public_id, 'title': conversation.title,
            'answer': message.content, 'message_id': message.id, 'structured_data': message.structured_data}


@router.get('/status')
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user)
    _, reason = service.configured_llm(user.organization_id, db)
    return {'ready': reason is None, 'reason': reason}


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
            'messages': [{'id': m.id, 'role': m.role, 'content': m.content,
                          'structured_data': m.structured_data, 'created_at': m.created_at} for m in messages]}


@router.post('/questions')
async def ask_question(body: Question, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user)
    question = body.question.strip()
    if not question:
        raise HTTPException(422, 'Enter a question first')
    config, reason = service.configured_llm(user.organization_id, db)
    if config is None:
        raise HTTPException(503, reason)
    conversation = owned_conversation(body.conversation_id, user, db) if body.conversation_id else None
    with single_question(user, db):
        # An idempotency key cannot be rebound to a different question or conversation.
        previous = db.query(ConversationMessage).join(Conversation).filter(
            Conversation.organization_id == user.organization_id,
            Conversation.created_by_user_id == user.id,
            Conversation.context_scope == service.SCOPE,
            ConversationMessage.role == 'user',
            ConversationMessage.raw_request['request_id'].as_string() == str(body.request_id),
        ).first()
        if previous:
            if previous.content != question or (conversation is not None and previous.conversation_id != conversation.id):
                raise HTTPException(409, 'That request identifier was already used for another question.')
            previous_state = previous.raw_request or {}
            if previous_state.get('status') == 'completed':
                response = db.query(ConversationMessage).filter_by(id=previous_state['answer_message_id'], conversation_id=previous.conversation_id).one()
                prior_conversation = owned_conversation(db.get(Conversation, previous.conversation_id).public_id, user, db)
                return answer_payload(prior_conversation, response)
            if previous_state.get('status') == 'failed':
                raise HTTPException(502, {'code': 'ask_genius_failed', 'message': 'This answer could not be completed. Ask again to start a new request.'})
            raise HTTPException(409, 'This question was already attempted. Check its conversation before asking again.')
        try:
            evidence = service.build_evidence(user.organization_id, db)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        history = []
        if conversation:
            recent = db.query(ConversationMessage).filter_by(conversation_id=conversation.id).order_by(ConversationMessage.id.desc()).limit(10).all()
            history = [{'role': m.role, 'content': m.content} for m in reversed(recent)]
        messages = service.build_messages(question, evidence, history)
        if conversation is None:
            conversation = Conversation(organization_id=user.organization_id, created_by_user_id=user.id,
                                        title=question[:100], context_scope=service.SCOPE)
            db.add(conversation)
            db.flush()
        audit = {'request_id': str(body.request_id), 'status': 'attempted', 'messages': messages,
                 'model': config.model, 'provider': config.provider, 'max_completion_tokens': 1200, 'max_retries': 0}
        user_message = ConversationMessage(conversation_id=conversation.id, role='user', content=question,
                                           context_scope=service.SCOPE, raw_request=audit,
                                           llm_provider=config.provider, llm_model=config.model)
        db.add(user_message)
        db.commit()  # Record the attempted request before contacting the provider.
        started = time.monotonic()
        try:
            result = await service.generate_answer(messages, config)
            user_message.raw_response = result.raw_response
            user_message.tokens_in = result.tokens_in
            user_message.tokens_out = result.tokens_out
            if not result.answer or result.finish_reason != 'stop':
                user_message.raw_request = {**audit, 'status': 'failed', 'error': 'IncompleteModelAnswer'}
                user_message.latency_ms = int((time.monotonic() - started) * 1000)
                db.commit()
                raise HTTPException(502, {'code': 'ask_genius_failed', 'message': 'The AI did not return a complete answer. Please try a new question.'})
        except HTTPException:
            raise
        except Exception as exc:
            # No exception strings, response headers or credentials leak into storage/UI.
            safe_error = 'ProviderTimeout' if isinstance(exc, openai.APITimeoutError) else 'ProviderHTTPError' if isinstance(exc, openai.APIStatusError) else 'ProviderRequestFailed'
            user_message.raw_request = {**audit, 'status': 'failed', 'error': safe_error,
                                        'http_status': exc.status_code if isinstance(exc, openai.APIStatusError) else None}
            user_message.latency_ms = int((time.monotonic() - started) * 1000)
            db.commit()
            raise HTTPException(502, {'code': 'ask_genius_failed', 'message': 'Ask Genius could not complete this answer. Please try a new question.'}) from None
        answer = ConversationMessage(conversation_id=conversation.id, role='assistant', content=result.answer,
                                     context_scope=service.SCOPE, query_type='analysis',
                                     llm_provider=config.provider, llm_model=config.model,
                                     tokens_in=result.tokens_in, tokens_out=result.tokens_out,
                                     cost_cents=None, latency_ms=int((time.monotonic() - started) * 1000))
        db.add(answer)
        db.flush()
        user_message.raw_request = {**audit, 'status': 'completed', 'answer_message_id': answer.id}
        # Usage is counted once on the assistant row; raw audit remains with the request.
        user_message.tokens_in = None
        user_message.tokens_out = None
        conversation.updated_at = datetime.utcnow()
        db.commit()
        return answer_payload(conversation, answer)

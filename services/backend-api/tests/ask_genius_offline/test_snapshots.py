"""A public capability exposes only its frozen, explicitly shared chat/evidence."""
import json

from src.models.ask_genius_share import AskGeniusShare
from src.models.conversation import Conversation
from src.models.conversation_message import ConversationMessage
from src.models.feedback import FeedbackItem
from src.models.organization import Organization
from src.services import ask_genius_sharing as sharing

BASE = '/api/v1/ask-genius'


def share_chat(flow):
    row = flow['rows'][0]
    flow['model']['evidence'] = [{'review_id': row.id, 'kind': 'review', 'excerpt': 'Repairs took two weeks.'}]
    answer = flow['ask']('Show supporting reviews.', period={'preset': 'all_time'})
    assert answer.status_code == 200, answer.text
    chat = answer.json()['conversation_id']
    response = flow['client'].post(f'{BASE}/conversations/{chat}/share', headers=flow['headers'])
    assert response.status_code == 201, response.text
    return chat, response.json()


def test_snapshot_is_public_and_has_only_attached_review_content(flow):
    chat, created = share_chat(flow)
    token = created['token']
    assert len(token) == 43 and created['path'] == f'/share/ask-genius/{token}'
    public = flow['client'].get(f'{BASE}/shared/{token}')
    assert public.status_code == 200, public.text
    assert public.headers['cache-control'] == 'no-store'
    assert public.headers['x-robots-tag'] == 'noindex, nofollow'
    data = public.json()
    assert set(data) == {'title', 'created_at', 'messages'}
    assert len(data['messages']) == 2
    source = data['messages'][1]['structured_data']['sources'][0]
    assert source['excerpt'] == 'Repairs took two weeks.'
    assert source['review']['original_review'] == flow['rows'][0].text
    assert source['review']['saved_analysis']['topics'][0]['name'] == 'Maintenance'
    assert 'href' not in source
    forbidden = ['synthetic-never-sent', 'raw_request', 'raw_response', 'tokens_in', 'llm_model',
                 'default_period', 'organization_id', 'created_by_user_id', 'Friendly leasing team.', '/feedbacks/']
    for value in forbidden:
        assert value not in public.text
    stored = flow['db'].query(AskGeniusShare).one()
    assert stored.token_hash == sharing.token_hash(token) and token not in json.dumps(stored.snapshot)
    assert flow['client'].get(f'{BASE}/conversations/{chat}').status_code in {401, 403}


def test_snapshot_is_frozen_after_messages_title_review_and_analysis_change(flow):
    chat, created = share_chat(flow)
    path = f'{BASE}/shared/{created["token"]}'
    before = flow['client'].get(path).json()
    flow['model']['evidence'] = []
    assert flow['ask']('A new question', conversation_id=chat).status_code == 200
    assert flow['client'].patch(f'{BASE}/conversations/{chat}', headers=flow['headers'], json={'title': 'Changed title'}).status_code == 200
    row = flow['rows'][0]; row.text = 'Changed private review'; row.apartment_analysis = {'secret': 'changed analysis'}
    flow['db'].commit()
    assert flow['client'].get(path).json() == before
    # Removing private history is distinct from deactivating a published link (deferred).
    assert flow['client'].delete(f'{BASE}/conversations/{chat}', headers=flow['headers']).status_code == 204
    assert flow['client'].get(path).json() == before


def test_each_share_is_a_new_snapshot_not_an_update_to_old_link(flow):
    chat, first = share_chat(flow)
    flow['model']['evidence'] = []
    assert flow['ask']('How many?', conversation_id=chat).status_code == 200
    second = flow['client'].post(f'{BASE}/conversations/{chat}/share', headers=flow['headers']).json()
    assert first['token'] != second['token']
    assert len(flow['client'].get(f'{BASE}/shared/{first["token"]}').json()['messages']) == 2
    assert len(flow['client'].get(f'{BASE}/shared/{second["token"]}').json()['messages']) == 4


def test_unknown_invalid_tokens_and_disabled_preview_return_no_snapshot(flow, monkeypatch):
    _, created = share_chat(flow)
    for token in ['x', 'x'*44, sharing.new_token()]:
        assert flow['client'].get(f'{BASE}/shared/{token}').status_code == 404
    monkeypatch.setenv('BOOMSAY_REVIEW_PREVIEW', 'false')
    assert flow['client'].get(f'{BASE}/shared/{created["token"]}').status_code == 404


def test_legacy_links_are_content_labels_and_unrelated_source_metadata_is_never_shared(flow):
    db = flow['db']
    org = Organization(name='Other'); db.add(org); db.flush()
    foreign = FeedbackItem(organization_id=org.id, source='apartment_review_ai', text='FOREIGN SECRET', star_rating=1)
    db.add(foreign); db.flush()
    local = flow['rows'][2]
    conv = Conversation(organization_id=flow['org'].id, created_by_user_id=flow['user'].id,
                        context_scope='boomsay_reviews', title='Legacy')
    db.add(conv); db.flush()
    message = ConversationMessage(conversation_id=conv.id, role='assistant',
        content=f'Here is a source [Review #{local.id}](/feedbacks/{local.id}).',
        raw_request={'private': 'DO NOT PUBLISH'}, raw_response={'private': 'MODEL SECRET'},
        structured_data={'kind': 'ask_genius', 'default_period': {'preset': 'year_to_date'}, 'evil': 'METADATA SECRET',
            'sources': [{'review_id': local.id, 'label': 'Fake label', 'href': 'https://attacker.invalid',
                         'review': {'original_review': 'INJECTED CONTENT', 'author': 'AUTHOR SECRET'}},
                        {'review_id': foreign.id, 'excerpt': 'FOREIGN SECRET', 'review': {'original_review': 'FOREIGN SECRET'}}]})
    db.add(message); db.commit()
    created = flow['client'].post(f'{BASE}/conversations/{conv.public_id}/share', headers=flow['headers']).json()
    data = flow['client'].get(f'{BASE}/shared/{created["token"]}').json()
    text = json.dumps(data)
    assert 'Parking was crowded.' in data['messages'][0]['content']
    assert 'Review #' not in data['messages'][0]['content']
    assert len(data['messages'][0]['structured_data']['sources']) == 1
    assert data['messages'][0]['structured_data']['sources'][0]['review_id'] == 1
    for forbidden in ['FOREIGN SECRET', 'INJECTED CONTENT', 'AUTHOR SECRET', 'attacker.invalid', 'METADATA SECRET', 'MODEL SECRET', 'DO NOT PUBLISH']:
        assert forbidden not in text


def test_share_bounds_and_empty_chats_fail_without_creating_link(flow, monkeypatch):
    db = flow['db']; empty = Conversation(organization_id=flow['org'].id, created_by_user_id=flow['user'].id,
                                         context_scope='boomsay_reviews', title='Empty')
    db.add(empty); db.commit()
    assert flow['client'].post(f'{BASE}/conversations/{empty.public_id}/share', headers=flow['headers']).status_code == 422
    monkeypatch.setattr(sharing, 'MAX_SNAPSHOT_BYTES', 10)
    answer = flow['ask']('What are the complaints?', period={'preset': 'all_time'}).json()
    assert flow['client'].post(f'{BASE}/conversations/{answer["conversation_id"]}/share', headers=flow['headers']).status_code == 422
    assert db.query(AskGeniusShare).count() == 0

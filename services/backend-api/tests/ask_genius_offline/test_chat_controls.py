"""Authenticated per-manager controls; every new endpoint remains community-scoped."""
import pytest

from conftest import headers_for
from src.models.conversation import Conversation
from src.models.organization import Organization
from src.models.user import User

BASE = '/api/v1/ask-genius'


def create_chat(flow, text='What are the main complaints?'):
    result = flow['ask'](text, period={'preset': 'all_time'})
    assert result.status_code == 200, result.text
    return result.json()['conversation_id']


def test_rename_pin_order_and_remove_are_persisted(flow):
    first = create_chat(flow)
    second = create_chat(flow, 'Which topics appear?')
    client, headers = flow['client'], flow['headers']
    patch = client.patch(f'{BASE}/conversations/{first}', headers=headers,
                         json={'title': '  Repairs to investigate  ', 'is_pinned': True})
    assert patch.status_code == 200
    assert patch.json()['title'] == 'Repairs to investigate'
    assert patch.json()['is_pinned'] is True
    listed = client.get(f'{BASE}/conversations', headers=headers).json()['conversations']
    assert [row['public_id'] for row in listed] == [first, second]
    loaded = client.get(f'{BASE}/conversations/{first}', headers=headers).json()
    assert loaded['title'] == 'Repairs to investigate' and loaded['is_pinned']
    # Follow-up answers never overwrite a manager's name.
    followup = flow['ask']('How many?', conversation_id=first)
    assert followup.status_code == 200
    assert followup.json()['title'] == 'Repairs to investigate'
    unpin = client.patch(f'{BASE}/conversations/{first}', headers=headers, json={'is_pinned': False})
    assert unpin.status_code == 200 and not unpin.json()['is_pinned']
    assert client.delete(f'{BASE}/conversations/{first}', headers=headers).status_code == 204
    assert client.get(f'{BASE}/conversations/{first}', headers=headers).status_code == 404
    assert flow['ask']('More', conversation_id=first).status_code == 404
    assert [c['public_id'] for c in client.get(f'{BASE}/conversations', headers=headers).json()['conversations']] == [second]


@pytest.mark.parametrize('body', [{}, {'title': '   '}, {'title': 'x'*201}, {'title': None},
                                 {'is_pinned': None}, {'is_pinned': 'true'}, {'is_active': False}])
def test_invalid_control_payloads_are_rejected(flow, body):
    chat = create_chat(flow)
    assert flow['client'].patch(f'{BASE}/conversations/{chat}', headers=flow['headers'], json=body).status_code == 422


def test_controls_cannot_touch_other_users_or_unrelated_scopes(flow):
    chat = create_chat(flow)
    headers = headers_for(flow['other_user'])
    for method, suffix, kwargs in [('patch', '', {'json': {'title': 'Hijacked'}}),
                                    ('delete', '', {}), ('post', '/share', {})]:
        result = getattr(flow['client'], method)(f'{BASE}/conversations/{chat}{suffix}', headers=headers, **kwargs)
        assert result.status_code == 404
    db = flow['db']
    unrelated = Conversation(organization_id=flow['org'].id, created_by_user_id=flow['user'].id,
                             context_scope='all_data', title='Private copilot')
    db.add(unrelated); db.commit()
    assert flow['client'].patch(f'{BASE}/conversations/{unrelated.public_id}', headers=flow['headers'],
                                json={'is_pinned': True}).status_code == 404


def test_controls_require_login_and_preview_community(flow):
    chat = create_chat(flow)
    for method, suffix, kwargs in [('patch', '', {'json': {'title': 'Hijacked'}}),
                                    ('delete', '', {}), ('post', '/share', {})]:
        assert getattr(flow['client'], method)(f'{BASE}/conversations/{chat}{suffix}', **kwargs).status_code in {401, 403}
    db = flow['db']; org = Organization(name='Other community'); db.add(org); db.flush()
    outsider = User(email='outsider@example.invalid', password_hash='unused', organization_id=org.id)
    db.add(outsider); db.commit()
    for method, suffix, kwargs in [('patch', '', {'json': {'title': 'Hijacked'}}),
                                    ('delete', '', {}), ('post', '/share', {})]:
        assert getattr(flow['client'], method)(f'{BASE}/conversations/{chat}{suffix}',
                                               headers=headers_for(outsider), **kwargs).status_code == 403


def test_controls_reject_overlap_with_generation(flow):
    from src.api.routes.ask_genius import single_question
    chat = create_chat(flow)
    with single_question(flow['user'], flow['db']):
        assert flow['client'].patch(f'{BASE}/conversations/{chat}', headers=flow['headers'], json={'title': 'New'}).status_code == 409
        assert flow['client'].delete(f'{BASE}/conversations/{chat}', headers=flow['headers']).status_code == 409
        assert flow['client'].post(f'{BASE}/conversations/{chat}/share', headers=flow['headers']).status_code == 409

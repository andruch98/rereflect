"""Real API conversation checks with a simulated model, never paid calls."""
from src.models.conversation_message import ConversationMessage


ALL = {'preset': 'all_time'}
TOPICS = 'Which topics came up most often in reviews during this period?'
NEGATIVE = ('Negative topics in reviews include:\n\n'
            '- **Maintenance:** A resident reported repair delays.\n'
            '- **Billing** (negative aspects): A resident reported unclear billing.')


def negative_topic_conversation(flow):
    flow['model']['answer'] = '- **Maintenance:** Reported repair delays.\n- **Staff:** Friendly leasing.'
    first = flow['ask'](TOPICS, period=ALL)
    assert first.status_code == 200
    chat = first.json()['conversation_id']
    flow['model']['answer'] = NEGATIVE
    second = flow['ask']('what are the bad topics', conversation_id=chat)
    assert second.status_code == 200
    return chat


def test_exact_reported_three_turn_flow_attaches_reviews_under_each_negative_topic(flow):
    chat = negative_topic_conversation(flow)
    # A simulated model would broaden incorrectly. The unambiguous follow-up
    # uses verified topic selectors locally and must not invoke that model.
    flow['model'].update(answer='Here are all reviews.', selections=[{}])
    result = flow['ask']('let me see each review', conversation_id=chat)
    assert result.status_code == 200
    body = result.json()
    assert body['answer'] == NEGATIVE
    assert [(s['topic'], s['review_id']) for s in body['structured_data']['sources']] == [
        ('Maintenance', flow['rows'][0].id), ('Billing', flow['rows'][3].id),
    ]
    assert len(flow['calls']) == 2
    latest = flow['db'].query(ConversationMessage).filter_by(role='user').order_by(ConversationMessage.id.desc()).first()
    assert latest.raw_request['status'] == 'completed'
    assert latest.raw_request['max_completion_tokens'] == 0
    restored = flow['client'].get('/api/v1/ask-genius/conversations/' + chat, headers=flow['headers'])
    assert restored.status_code == 200
    assert restored.json()['messages'][-1]['structured_data']['sources'] == body['structured_data']['sources']


def test_explicit_broadening_uses_model_and_preserves_all_matching_sources(flow):
    chat = negative_topic_conversation(flow)
    flow['model'].update(answer='There are five saved reviews.', selections=[{}])
    result = flow['ask']('Show all reviews from this period, including positive ones.', conversation_id=chat)
    assert result.status_code == 200
    assert len(flow['calls']) == 3
    assert len(result.json()['structured_data']['sources']) == 5


def test_changed_period_does_not_reuse_previous_answer_or_sources(flow):
    chat = negative_topic_conversation(flow)
    flow['model'].update(answer='One review matches this period.', selections=[{}])
    result = flow['ask']('let me see each review', conversation_id=chat, period={'preset': 'last_7_days'})
    assert result.status_code == 200
    assert len(flow['calls']) == 3
    assert [s['review_id'] for s in result.json()['structured_data']['sources']] == [flow['rows'][0].id]


def test_changed_source_records_use_model_to_reassess_prior_claims(flow):
    chat = negative_topic_conversation(flow)
    flow['rows'][0].text = 'The resident updated their review.'
    flow['db'].commit()
    flow['model']['answer'] = 'The review content has changed.'
    result = flow['ask']('let me see each review', conversation_id=chat)
    assert result.status_code == 200
    assert result.json()['answer'] == 'The review content has changed.'
    assert len(flow['calls']) == 3


def test_consolidated_policy_and_length_context_are_sent_on_each_model_turn(flow):
    negative_topic_conversation(flow)
    for messages in flow['calls']:
        policy = messages[0]['content']
        assert policy.count('1. AUTHORITY AND AVAILABLE INFORMATION') == 1
        assert policy.count('OUTPUT CONTRACT') == 1
        assert 'Resolve this distinction BEFORE' in policy
        assert 'ILLUSTRATIVE; NEVER TREAT AS COMMUNITY DATA' in policy
        assert 'expanded_limit_requires_written_source_detail' in messages[1]['content']

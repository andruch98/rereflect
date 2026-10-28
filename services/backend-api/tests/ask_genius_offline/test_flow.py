"""Meaningful integration checks with actual routes, JWT, ORM and model adapter seam."""
import json
from datetime import date
from uuid import uuid4

import pytest
import httpx
import openai

from conftest import headers_for
from src.models.conversation import Conversation
from src.models.conversation_message import ConversationMessage
from src.models.feedback import FeedbackItem
from src.models.organization import Organization
from src.services import ask_genius as service
from src.services.ask_genius_periods import Period

ALL = {'preset': 'all_time'}
LAST7 = {'preset': 'last_7_days'}


def evidence(flow, index=-1):
    return json.loads(flow['calls'][index][1]['content'].split('\n',1)[1])


def test_status_has_no_implicit_default_and_actual_date_coverage(flow):
    result = flow['client'].get('/api/v1/ask-genius/status',headers=flow['headers']).json()
    assert result['default_period'] is None
    assert result['date_coverage'] == {'total_reviews':5,'dated_reviews':4,'undated_reviews':1}
    assert result['available_sources'] == ['reviews','analysis']
    assert result['timezone'] == 'America/New_York'


def test_first_question_requires_period_and_makes_no_model_call(flow):
    assert flow['ask']().status_code == 422
    assert not flow['calls']
    assert flow['db'].query(Conversation).count() == 0


def test_period_is_filtered_in_code_before_model_and_counts_match(flow):
    result = flow['ask'](period=LAST7)
    assert result.status_code == 200
    context = evidence(flow)
    assert [x['review_id'] for x in context['reviews']] == [flow['rows'][0].id]
    assert context['calculated']['review_count'] == 1
    assert context['calculated']['star_rating_counts'] == {'1':0,'2':1,'3':0,'4':0,'5':0}
    assert context['excluded_undated_review_count'] == 1
    assert result.json()['period'] == LAST7


def test_all_history_includes_undated_but_not_import_time_as_review_date(flow):
    result = flow['ask'](period=ALL)
    assert result.status_code == 200
    assert evidence(flow)['calculated']['review_count'] == 5
    assert evidence(flow)['calculated']['missing_posting_date_count'] == 1
    assert evidence(flow)['excluded_undated_review_count'] == 0
    assert next(r for r in evidence(flow)['reviews'] if r['review_id']==flow['rows'][3].id)['original_posting_date'] is None


def test_missing_dates_are_honest_without_calling_provider_or_widening(flow):
    for row in flow['rows']: row.review_date = None
    flow['db'].commit()
    result = flow['ask'](period=LAST7)
    assert result.status_code == 200
    assert 'cannot reliably answer' in result.json()['answer']
    assert '5 saved review(s) have no posting date' in result.json()['answer']
    assert result.json()['period'] == LAST7
    assert not flow['calls']


def test_empty_but_complete_date_cohort_is_not_confused_with_missing_dates(flow):
    flow['rows'][3].review_date = date(2026,8,1);flow['db'].commit()
    result=flow['ask'](period={'preset':'custom','start_date':'2025-01-01','end_date':'2025-01-31'})
    assert result.status_code == 200
    assert 'no saved reviews dated within' in result.json()['answer']
    assert not flow['calls']


def test_preferences_persist_for_only_current_user_and_can_clear(flow):
    client=flow['client']
    save=client.put('/api/v1/ask-genius/preferences',headers=flow['headers'],json={'default_period':LAST7})
    assert save.status_code == 200
    assert client.get('/api/v1/ask-genius/status',headers=flow['headers']).json()['default_period']==LAST7
    other=client.get('/api/v1/ask-genius/status',headers=headers_for(flow['other_user'])).json()
    assert other['default_period'] is None
    assert flow['ask']().status_code==200
    client.put('/api/v1/ask-genius/preferences',headers=flow['headers'],json={'default_period':None})
    assert flow['ask']().status_code==422


def test_explicit_chat_default_is_saved_without_model_and_clear_is_real(flow):
    result=flow['ask']('Use last 30 days as my default going forward')
    assert result.status_code==200
    assert result.json()['preference_updated'] is True
    assert result.json()['default_period']=={'preset':'last_30_days'}
    assert not flow['calls']
    clear=flow['ask']('Remove my default',conversation_id=result.json()['conversation_id'])
    assert clear.json()['default_period'] is None
    assert clear.json()['period']=={'preset':'last_30_days'}
    assert flow['user'].ask_genius_default_period is None


def test_current_period_default_and_hypothetical_do_not_write(flow):
    first=flow['ask'](period=LAST7).json()
    save=flow['ask']('Make this period my default',conversation_id=first['conversation_id'])
    assert save.json()['default_period']==LAST7
    hypothetical=flow['ask']('What if I use last 30 days as my default?',conversation_id=first['conversation_id'])
    assert hypothetical.status_code==200
    assert hypothetical.json()['preference_updated'] is False
    assert flow['user'].ask_genius_default_period==LAST7


def test_explicit_question_override_does_not_change_saved_default(flow):
    flow['client'].put('/api/v1/ask-genius/preferences',headers=flow['headers'],json={'default_period':{'preset':'last_30_days'}})
    result=flow['ask']('What complaints appeared in the last 7 days?',period=ALL)
    assert result.json()['period']==LAST7
    assert result.json()['default_period']=={'preset':'last_30_days'}
    assert len(evidence(flow)['reviews'])==1


def test_followup_reuses_conversation_period_and_reopening_restores_it(flow):
    first=flow['ask'](period=LAST7).json()
    next_answer=flow['ask']('Explain that finding',conversation_id=first['conversation_id'])
    assert next_answer.json()['period']==LAST7
    detail=flow['client'].get('/api/v1/ask-genius/conversations/'+first['conversation_id'],headers=flow['headers']).json()
    assert detail['period']==LAST7
    assert len(detail['messages'])==4
    assert 'raw_request' not in json.dumps(detail)
    assert 'synthetic-never-sent' not in json.dumps(detail)


def test_request_replay_does_not_generate_again_or_accept_changed_period(flow):
    key=str(uuid4())
    first=flow['ask'](period=LAST7,request_id=key)
    replay=flow['ask'](period=LAST7,request_id=key)
    assert first.json()==replay.json()
    assert len(flow['calls'])==1
    assert flow['ask'](period=ALL,request_id=key).status_code==409


def test_personal_history_and_other_org_are_isolated(flow):
    other_org=Organization(name='Other private community',plan='enterprise')
    flow['db'].add(other_org);flow['db'].flush()
    flow['db'].add(FeedbackItem(organization_id=other_org.id,source='apartment_review_ai',text='PRIVATE FOREIGN REVIEW'))
    flow['db'].add(FeedbackItem(organization_id=flow['org'].id,source='survey',text='PRIVATE DISCONNECTED SURVEY'))
    flow['db'].commit()
    first=flow['ask'](period=ALL).json()
    assert 'PRIVATE' not in json.dumps(evidence(flow))
    other_headers=headers_for(flow['other_user'])
    assert flow['client'].get('/api/v1/ask-genius/conversations',headers=other_headers).json()['total']==0
    assert flow['ask'](period=ALL,conversation_id=first['conversation_id'],headers=other_headers).status_code==404


@pytest.mark.parametrize('raw',['x'*1001,json.dumps({'answer':'x'*1001,'evidence':[]})])
def test_oversized_explanation_rejected_in_full_without_retry(flow,raw):
    flow['model']['raw']=raw
    result=flow['ask']('Explain more',period=ALL)
    assert result.status_code==502
    assert 'length limits' in result.json()['detail']['message']
    assert len(flow['calls'])==1
    assert flow['db'].query(ConversationMessage).filter_by(role='assistant').count()==0


def test_requested_evidence_is_verified_and_links_built_from_authorized_records(flow):
    flow['model'].update(answer='This review describes repair delays.',evidence=[{'review_id':flow['rows'][0].id,'kind':'review','excerpt':'Repairs took two weeks.'}])
    result=flow['ask']('Show me the supporting reviews',period=LAST7)
    assert result.status_code==200
    body=result.json()
    assert body['answer'] == 'This review describes repair delays.'
    source = body['structured_data']['sources'][0]
    assert source['review_id'] == flow['rows'][0].id
    assert source['label'] == source['excerpt'] == 'Repairs took two weeks.'
    assert source['href'] == f'/feedbacks/{flow["rows"][0].id}'
    assert source['review']['original_review'] == flow['rows'][0].text
    assert service.displayed_answer_length(body['answer'], body['structured_data']['sources']) <= 3000


def test_saved_analysis_evidence_uses_stored_topic_and_quote(flow):
    flow['model'].update(answer='The saved analysis identifies maintenance as negative.',evidence=[{'review_id':flow['rows'][0].id,'kind':'analysis','topic':'Maintenance','excerpt':'Repairs took two weeks.'}])
    result=flow['ask']('Show saved analysis',period=LAST7)
    assert result.status_code==200
    source = result.json()['structured_data']['sources'][0]
    assert source['kind'] == 'analysis'
    assert source['topic'] == 'Maintenance'
    assert source['excerpt'] == 'Repairs took two weeks.'
    assert source['review']['saved_analysis']['topics'][0]['sentiment'] == 'negative'


@pytest.mark.parametrize('item',[
    {'review_id':99999,'kind':'review','excerpt':'Invented quote.'},
    {'review_id':1,'kind':'review','excerpt':'Invented quote.'},
    {'review_id':1,'kind':'analysis','topic':'Invented topic'},
])
def test_invalid_or_invented_evidence_fails_closed(flow,item):
    flow['model']['evidence']=[item]
    assert flow['ask']('Show supporting reviews',period=ALL).status_code==502


def test_unrequested_evidence_or_short_citation_does_not_unlock_long_answers(flow):
    flow['model']['evidence']=[{'review_id':flow['rows'][0].id,'kind':'review','excerpt':'Helpful staff.'}]
    assert flow['ask']('Explain more',period=ALL).status_code==502
    flow['model'].update(raw='Read [this](https://external.invalid).')
    assert flow['ask']('Show supporting reviews',period=ALL).status_code==502


def test_explicit_yes_to_offer_expands_but_explanation_alone_does_not(flow):
    flow['model']['answer']='Maintenance delays came up. Would you like to see the supporting reviews?'
    first=flow['ask'](period=ALL).json()
    flow['model'].update(answer='Here is the review.',evidence=[{'review_id':flow['rows'][0].id,'kind':'review','excerpt':'Repairs took two weeks.'}])
    assert flow['ask']('Yes',conversation_id=first['conversation_id']).status_code==200
    assert evidence(flow)['evidence_requested'] is True


def test_evidence_continuation_accepts_yes_or_show_more_with_pronoun_offer():
    history=[{'role':'assistant','content':'More supporting information is available. Would you like to see it?'}]
    assert service.evidence_requested('yes',history)
    assert service.evidence_requested('show more',history)
    assert not service.evidence_requested('Explain more',history)
    assert not service.evidence_requested('Yes',[{'role':'assistant','content':'Would you like it?'}])


def test_oversized_evidence_is_rejected_without_dropping_records_or_changing_claims(flow):
    # Seven distinct card previews exceed the visible 3,000-character budget even
    # though full originals now live in popups rather than the assistant text.
    record = flow['rows'][0]
    quotes = [str(i) + ' ' + ('source words ' * 39) for i in range(7)]
    record.text = '\n'.join(quotes)
    flow['db'].commit()
    flow['model'].update(answer='These excerpts show the reported experiences.', evidence=[
        {'review_id':record.id,'kind':'review','excerpt':quote} for quote in quotes])
    result=flow['ask']('Show supporting reviews',period=ALL)
    assert result.status_code==502
    assert flow['db'].query(ConversationMessage).filter_by(role='assistant').count()==0
    assert len(flow['calls'])==1


def test_invalid_custom_preference_rejected_with_validation_status(flow):
    result=flow['client'].put('/api/v1/ask-genius/preferences',headers=flow['headers'],json={
        'default_period':{'preset':'custom','start_date':'2026-01-01','end_date':'2099-01-01'}})
    assert result.status_code==422
    assert flow['user'].ask_genius_default_period is None


def test_preference_extra_identity_fields_and_anonymous_are_rejected(flow):
    client=flow['client']
    assert client.put('/api/v1/ask-genius/preferences',json={'default_period':LAST7}).status_code in (401,403)
    assert client.put('/api/v1/ask-genius/preferences',headers=flow['headers'],json={'default_period':LAST7,'user_id':flow['other_user'].id}).status_code==422


def test_provider_timeout_has_connection_message_and_no_automatic_retry(flow):
    flow['model']['exception']=openai.APITimeoutError(request=httpx.Request('POST','https://example.invalid'))
    result=flow['ask'](period=ALL)
    assert result.status_code==502
    assert 'connection timed out' in result.json()['detail']['message']
    assert len(flow['calls'])==1


def test_source_data_remains_unchanged_after_answers_and_preferences(flow):
    original=[(r.text,r.review_date,r.star_rating,r.apartment_analysis) for r in flow['rows']]
    assert flow['ask'](period=ALL).status_code==200
    assert flow['ask']('Use last 7 days as my default').status_code==200
    assert [(r.text,r.review_date,r.star_rating,r.apartment_analysis) for r in flow['rows']]==original

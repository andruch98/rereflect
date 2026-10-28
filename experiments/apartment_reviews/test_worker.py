"""Real worker/provider modules, with the external SDK transport mocked."""
import json
import hashlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'services/worker-service'),str(ROOT/'services/analysis-engine/src')]
from src.apartment_reviews import messages, TOPICS, SENTIMENTS
from src.llm import experiment
from src.llm.providers.openai import OpenAIProvider
from src.llm.types import LLMRequest
from src.llm_client import categorize_apartment_feedback
from src.tasks import analysis


@pytest.fixture
def context(tmp_path,monkeypatch):
    text='Quiet neighbors. The pool was lovely last year. '+'full text '*300+'The pool is dirty.'
    records=[{'source_id':'fiction-'+str(i),'text':text,'star_rating':3} for i in range(6)]
    path=tmp_path/'manifest.json';path.write_text(json.dumps({'records':records}))
    monkeypatch.setenv('APARTMENT_EXPERIMENT_MANIFEST',str(path))
    monkeypatch.setenv('APARTMENT_EXPERIMENT_LEDGER',str(tmp_path/'ledger.sqlite'))
    monkeypatch.setenv('APARTMENT_EXPERIMENT_ORG_ID','1')
    monkeypatch.setenv('OPENAI_API_KEY','offline-fictional-key')
    reference=tmp_path/'review_analysis_test_runs_v1.txt'
    reference.write_bytes(b'Fictional reviewed history.\r\nKeep both sides of a topic.\r\n')
    monkeypatch.setenv('APARTMENT_ANALYSIS_TEST_RUNS_PATH',str(reference))
    monkeypatch.setattr(analysis,'_EXPERIMENT_ACTIVE',True)
    output={'sentiment':'mixed','topics':[{'name':'Noise & neighbors','sentiment':'positive','quotations':['Quiet neighbors.']},{'name':'Amenities','sentiment':'negative','quotations':['The pool is dirty.']}]}
    for topic in output['topics']:
        topic['quotations']=[{'text':q,'sentiment':topic['sentiment']} for q in topic['quotations']]
    client=MagicMock()
    client.with_options.return_value=client
    raw=json.dumps(output)
    response=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw),finish_reason='stop')],usage=SimpleNamespace(prompt_tokens=10,completion_tokens=20,total_tokens=30),model_dump=lambda **kw:{'choices':[{'message':{'content':raw},'finish_reason':'stop'}]})
    client.chat.completions.create.return_value=response
    monkeypatch.setattr(OpenAIProvider,'_get_client',lambda _:client)
    return text,client,response,output


def test_real_provider_boundary_counts_once_no_retries_full_input(context):
    text,client,response,output=context
    found=categorize_apartment_feedback(text,3,'fiction-0','gpt-4.1-mini')
    assert found['parsed_result']==output
    assert found['usage']['total_tokens']==30
    kwargs=client.chat.completions.create.call_args.kwargs
    assert found['request']==kwargs
    reference=Path(os.environ['APARTMENT_ANALYSIS_TEST_RUNS_PATH']).read_bytes()
    assert json.loads(kwargs['messages'][1]['content'])=={'analysis_test_runs_reference':reference.decode('utf-8')}
    assert found['reference_file']=={'sha256':hashlib.sha256(reference).hexdigest(),'bytes':len(reference)}
    assert 'Before analyzing the current review, read this file' in kwargs['messages'][0]['content']
    schema=kwargs['response_format']['json_schema']
    assert kwargs['response_format']['type']=='json_schema' and schema['strict'] is True
    topic=schema['schema']['properties']['topics']['items']
    assert topic['properties']['name']['enum']==list(TOPICS) and len(TOPICS)==21
    assert set(schema['schema']['properties']['sentiment']['enum'])==SENTIMENTS
    quotation=topic['properties']['quotations']['items']
    assert set(quotation['properties']['sentiment']['enum'])==SENTIMENTS-{'mixed'}
    for obj in (schema['schema'],topic,quotation):
        assert obj['additionalProperties'] is False
        assert set(obj['required'])==set(obj['properties'])
    assert json.loads(kwargs['messages'][-1]['content'])=={'text':text,'star_rating':3}
    client.with_options.assert_called_once_with(max_retries=0)
    again=categorize_apartment_feedback(text,3,'fiction-0','gpt-4.1-mini')
    assert again['parsed_result'] is None
    assert client.chat.completions.create.call_count==1
    with experiment.connection() as db:
        row=db.execute('SELECT request,response FROM attempts').fetchone()
    assert json.loads(row[0])==kwargs and json.loads(row[1])==response.model_dump()


@pytest.mark.parametrize('raw,finish', [('not json','stop'),('{"sentiment":"neutral","topics":[]}','length'),('{"sentiment":"mixed","topics":[{"name":"Amenities","sentiment":"negative","quotations":["not in source"]}]}','stop')])
def test_raw_invalid_or_incomplete_output_retained(context,raw,finish):
    text,client,response,_=context
    response.choices[0].message.content=raw
    response.choices[0].finish_reason=finish
    found=categorize_apartment_feedback(text,3,'fiction-0','gpt-4.1-mini')
    assert found['raw_output']==raw and found['parsed_result'] is None
    assert found['validation']['passed'] is False


def feedback(text,source='apartment_review_ai'):
    return SimpleNamespace(id=1,organization_id=1,source=source,source_external_id='fiction-0',text=text,star_rating=3,apartment_analysis=None, is_urgent=False,pain_point_category=None)


def session():
    db=MagicMock()
    org=SimpleNamespace(ai_analysis_enabled=True)
    db.query.return_value.filter.return_value.first.return_value=org
    db.query.return_value.filter_by.return_value.first.return_value=SimpleNamespace(default_provider='openai',model_categorization='gpt-4.1-mini')
    return db


def test_worker_preserves_mixed_and_topic_sentiments(context):
    text,client,_,output=context
    item=feedback(text)
    analysis._analyze_feedback_item(item,session())
    assert item.sentiment_label=='mixed'
    assert item.apartment_analysis['final_result']['topics']==output['topics']
    assert item.llm_analyzed is True and item.llm_analysis_pending is False
    assert item.pain_point_category is None and item.is_urgent is False
    analysis._analyze_feedback_item(item,session())
    assert client.chat.completions.create.call_count==1


def test_worker_saves_cleaned_result_and_keeps_raw_output_and_audit(context):
    text,client,response,output=context
    messy=json.loads(json.dumps(output))
    messy['sentiment']=' Mixed '
    messy['confidence']=0.9
    messy['topics'][0]['name']='Noise and neighbors'
    messy['topics'][0]['quotations']=['', {'text':'Quiet\tneighbors.','sentiment':' Positive '}]
    raw=json.dumps(messy)
    response.choices[0].message.content=raw
    item=feedback(text)
    analysis._analyze_feedback_item(item,session())
    audit=item.apartment_analysis['ai_attempt']
    assert audit['raw_output']==raw
    assert audit['parsed_result']==output
    assert audit['normalizations']
    assert audit['validation']['passed'] is True
    assert item.apartment_analysis['final_result']['method']=='ai_model'
    assert item.apartment_analysis['final_result']['topics']==output['topics']
    assert item.text==text and item.star_rating==3
    assert item.llm_analyzed is True and item.llm_analysis_pending is False
    assert client.chat.completions.create.call_count==1


def test_conflicting_topics_still_save_fallback_without_paid_retry(context):
    text,client,response,output=context
    duplicate=dict(output['topics'][0],sentiment='negative')
    raw=json.dumps(dict(output,topics=output['topics']+[duplicate]))
    response.choices[0].message.content=raw
    item=feedback(text)
    analysis._analyze_feedback_item(item,session())
    audit=item.apartment_analysis['ai_attempt']
    assert audit['raw_output']==raw and audit['parsed_result'] is None
    assert 'Conflicting duplicate topic' in audit['failure_reason']
    assert item.apartment_analysis['final_result']['method']=='keyword_fallback'
    assert item.llm_analyzed is False and item.llm_analysis_pending is False
    assert client.chat.completions.create.call_count==1


def test_failure_routes_to_actual_keyword_sentiment_without_second_call(context):
    text,client,_,_=context
    client.chat.completions.create.side_effect=RuntimeError('simulated provider failure')
    item=feedback(text)
    analysis._analyze_feedback_item(item,session())
    assert item.apartment_analysis['final_result']['method']=='keyword_fallback'
    assert item.apartment_analysis['ai_attempt']['failure_reason']=='RuntimeError (HTTP None)'
    assert item.llm_analyzed is False and item.llm_analysis_pending is False
    assert all(t['sentiment']=='unknown' for t in item.apartment_analysis['final_result']['topics'])
    assert client.chat.completions.create.call_count==1


def test_separate_fallback_never_calls_provider(context):
    text,client,_,_=context
    item=feedback(text,'apartment_review_fallback')
    analysis._analyze_feedback_item(item,session())
    assert item.apartment_analysis['ai_attempt'] is None
    client.chat.completions.create.assert_not_called()


def test_authentication_failure_stops_later_provider_calls(context):
    import httpx
    from openai import AuthenticationError
    text,client,_,_=context
    client.chat.completions.create.side_effect=AuthenticationError('fictional auth failure', response=httpx.Response(401,request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')),body=None)
    first=categorize_apartment_feedback(text,3,'fiction-0','gpt-4.1-mini')
    second=categorize_apartment_feedback(text,3,'fiction-1','gpt-4.1-mini')
    assert first['failure_reason']=='AuthenticationError (HTTP 401)'
    assert 'stopped' in second['failure_reason']
    assert client.chat.completions.create.call_count==1


def test_worker_saves_both_sides_of_one_mixed_topic(context):
    text,client,response,_=context
    output={'sentiment':'mixed','topics':[{'name':'Amenities','sentiment':'mixed','quotations':[
        {'text':'The pool was lovely last year.','sentiment':'positive'},
        {'text':'The pool is dirty.','sentiment':'negative'}]}]}
    response.choices[0].message.content=json.dumps(output)
    item=feedback(text)
    analysis._analyze_feedback_item(item,session())
    assert item.apartment_analysis['final_result']['topics']==output['topics']
    assert item.apartment_analysis['final_result']['method']=='ai_model'
    assert item.apartment_analysis['ai_attempt']['raw_output']==json.dumps(output)
    assert client.chat.completions.create.call_count==1


def test_worker_derives_mixed_and_restores_opening_case_with_raw_unchanged(context):
    text,client,response,_=context
    output={'sentiment':'negative','topics':[{'name':'Amenities','sentiment':'negative','quotations':[
        {'text':'The pool was lovely last year.','sentiment':'positive'},
        {'text':'the pool is dirty.','sentiment':'negative'}]}]}
    raw=json.dumps(output)
    response.choices[0].message.content=raw
    item=feedback(text)
    analysis._analyze_feedback_item(item,session())
    result=item.apartment_analysis['final_result']
    audit=item.apartment_analysis['ai_attempt']
    assert result['method']=='ai_model' and result['sentiment']=='negative'
    assert result['topics'][0]['sentiment']=='mixed'
    assert result['topics'][0]['quotations'][1]['text']=='The pool is dirty.'
    assert audit['raw_output']==raw and item.text==text
    assert {c['change'] for c in audit['normalizations']}=={
        'original_source_quotation_restored','mixed_topic_derived_from_quotation_labels'}
    client.chat.completions.create.assert_called_once()


@pytest.mark.parametrize('problem',['unset','relative','missing','empty','invalid_utf8','directory'])
def test_unavailable_reference_never_spends_a_request(context,monkeypatch,tmp_path,problem):
    text,client,_,_=context
    path=Path(os.environ['APARTMENT_ANALYSIS_TEST_RUNS_PATH'])
    if problem=='unset': monkeypatch.delenv('APARTMENT_ANALYSIS_TEST_RUNS_PATH')
    elif problem=='relative': monkeypatch.setenv('APARTMENT_ANALYSIS_TEST_RUNS_PATH','reference.txt')
    elif problem=='missing': path.unlink()
    elif problem=='empty': path.write_text(' \n\t')
    elif problem=='invalid_utf8': path.write_bytes(b'\xff')
    else: monkeypatch.setenv('APARTMENT_ANALYSIS_TEST_RUNS_PATH',str(tmp_path))
    found=categorize_apartment_feedback(text,3,'fiction-0','gpt-4.1-mini')
    assert found['validation']['passed'] is False
    assert 'APARTMENT_ANALYSIS_TEST_RUNS_PATH' in found['failure_reason']
    assert found['provider_attempted'] is False and found['raw_output'] is None
    assert not Path(os.environ['APARTMENT_EXPERIMENT_LEDGER']).exists()
    client.chat.completions.create.assert_not_called()


def test_reference_is_read_again_for_each_request_without_truncation(context):
    text,client,_,_=context
    first=categorize_apartment_feedback(text,3,'fiction-0','gpt-4.1-mini')
    updated='Fictional review history.\n'*1500+'Last approved lesson. 🏡\n'
    Path(os.environ['APARTMENT_ANALYSIS_TEST_RUNS_PATH']).write_bytes(updated.encode('utf-8'))
    second=categorize_apartment_feedback(text,3,'fiction-1','gpt-4.1-mini')
    assert second['validation']['passed'] is True
    kwargs=client.chat.completions.create.call_args.kwargs
    assert json.loads(kwargs['messages'][1]['content'])['analysis_test_runs_reference']==updated
    assert first['reference_file']['sha256']!=second['reference_file']['sha256']
    assert client.chat.completions.create.call_count==2


def test_keyword_comparison_does_not_require_reference_file(context,monkeypatch):
    text,client,_,_=context
    monkeypatch.delenv('APARTMENT_ANALYSIS_TEST_RUNS_PATH')
    item=feedback(text,'apartment_review_fallback')
    analysis._analyze_feedback_item(item,session())
    assert item.apartment_analysis['final_result']['method']=='keyword_fallback'
    assert item.apartment_analysis['ai_attempt'] is None
    client.chat.completions.create.assert_not_called()


@pytest.mark.parametrize('json_mode',[True,False])
def test_ordinary_openai_requests_keep_existing_format(context,monkeypatch,json_mode):
    _,client,_,_=context
    monkeypatch.delenv('APARTMENT_EXPERIMENT_ORG_ID')
    OpenAIProvider('offline-fictional-key','gpt-4.1-mini').complete(
        LLMRequest(messages=[{'role':'user','content':'Fictional ordinary request'}],json_mode=json_mode))
    kwargs=client.chat.completions.create.call_args.kwargs
    if json_mode: assert kwargs['response_format']=={'type':'json_object'}
    else: assert 'response_format' not in kwargs
    assert len(kwargs['messages'])==1


def test_schema_and_reference_reach_real_sdk_without_network(context,monkeypatch):
    import httpx
    from openai import OpenAI
    text,_,_,output=context
    sent=[]
    def transport(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={
            'id':'fictional-completion','object':'chat.completion','created':0,'model':'gpt-4.1-mini',
            'choices':[{'index':0,'message':{'role':'assistant','content':json.dumps(output)},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}})
    with OpenAI(api_key='offline-fictional-key',http_client=httpx.Client(transport=httpx.MockTransport(transport))) as sdk:
        monkeypatch.setattr(OpenAIProvider,'_get_client',lambda _:sdk)
        found=categorize_apartment_feedback(text,3,'fiction-0','gpt-4.1-mini')
    assert found['validation']['passed'] is True and len(sent)==1
    assert sent[0]==found['request']
    assert sent[0]['response_format']['json_schema']['strict'] is True
    assert len(sent[0]['messages'])==3

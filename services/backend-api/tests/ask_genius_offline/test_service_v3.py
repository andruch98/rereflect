"""Source-backed cards, bounded answers and follow-up evidence contracts; no live LLM."""
import json
from types import SimpleNamespace

import pytest

from src.services import ask_genius as service
from src.services.ask_genius_periods import Period

ALL = {'preset': 'all_time'}


@pytest.mark.parametrize('question', [
    "tie each topic to it's original review",
    'Link each complaint to the original review',
    'this is not helpful, i want to see the actual review',
    'Open the review behind that',
    'Which reviews mention billing?',
    'Which reviews are negative?',
    'Read the actual review',
])
def test_contextual_source_requests_enable_cards(question):
    assert service.evidence_requested(question, [])


@pytest.mark.parametrize('question', [
    'What are the main themes in staff and customer service?',
    'Explain more', 'Be more detailed',
    "Don't show reviews, just explain the finding", 'Without supporting evidence please',
])
def test_explanation_requests_and_declines_do_not_enable_evidence_allowance(question):
    assert not service.evidence_requested(question, [])


def test_whole_review_selector_avoids_repeating_long_original_in_model_output(flow):
    row = flow['rows'][0]
    row.text = 'Repairs took two weeks. ' + ('Here is more original review detail. ' * 200)
    flow['db'].commit()
    flow['model'].update(answer='The review reports a delay in repairs.', evidence=[
        {'review_id': row.id, 'kind': 'review'}])
    result = flow['ask']('I want to see the actual review', period=ALL)
    assert result.status_code == 200
    body = result.json()
    source = body['structured_data']['sources'][0]
    assert source['excerpt'] in row.text
    assert len(source['excerpt']) <= service.SOURCE_PREVIEW_CHARS
    assert source['excerpt_truncated'] is True
    assert source['review']['original_review'] == row.text
    assert 'Review #' not in body['answer']
    assert len(body['answer']) <= 1000
    assert service.displayed_answer_length(body['answer'], [source]) <= 3000
    assert len(flow['calls']) == 1


def test_topic_quotation_selector_preserves_exact_quote_and_saved_sentiment(flow):
    row = flow['rows'][0]
    row.apartment_analysis = {'final_result': {'method': 'ai_model', 'sentiment': 'mixed', 'topics': [
        {'name': 'Staff', 'sentiment': 'mixed', 'quotations': [
            {'text': 'Helpful staff.', 'sentiment': 'positive'},
            {'text': 'Repairs took two weeks.', 'sentiment': 'negative'},
        ]}]}}
    flow['db'].commit()
    flow['model'].update(answer='The saved analysis includes a negative repair experience.', evidence=[
        {'review_id': row.id, 'kind': 'analysis', 'topic': 'Staff', 'quotation_index': 1}])
    response = flow['ask']('Show the saved analysis', period=ALL)
    assert response.status_code == 200
    source = response.json()['structured_data']['sources'][0]
    assert source['excerpt'] == 'Repairs took two weeks.'
    assert source['review']['saved_analysis']['topics'][0]['sentiment'] == 'mixed'


def test_analysis_text_not_in_original_is_never_shown_as_resident_quote(flow):
    row = flow['rows'][0]
    row.apartment_analysis = {'final_result': {'method': 'ai_model', 'sentiment': 'negative', 'topics': [
        {'name': 'Maintenance', 'sentiment': 'negative', 'quotations': [
            {'text': 'The maintenance experience was unsatisfactory.', 'sentiment': 'negative'},
        ]}]}}
    flow['db'].commit()
    flow['model'].update(answer='The saved analysis identifies maintenance concerns.', evidence=[
        {'review_id': row.id, 'kind': 'analysis', 'topic': 'Maintenance', 'quotation_index': 0}])
    response = flow['ask']('Show the saved analysis', period=ALL)
    assert response.status_code == 200
    source = response.json()['structured_data']['sources'][0]
    assert source['excerpt'] == row.text
    assert source['review']['saved_analysis']['topics'][0]['quotations'][0]['text'] == 'The maintenance experience was unsatisfactory.'


@pytest.mark.parametrize('item', [
    {'kind': 'review', 'topic': 'Maintenance', 'quotation_index': 999},
    {'kind': 'analysis', 'topic': 'Not a saved topic'},
    {'kind': 'review', 'quotation_index': 0},
    {'kind': 'review', 'topic': 'Maintenance', 'quotation_index': 0, 'excerpt': 'Repairs took two weeks.'},
    {'kind': 'review', 'excerpt': 'They fixed everything immediately.'},
])
def test_invalid_selectors_or_invented_excerpts_fail_without_model_retry(flow, item):
    flow['model'].update(evidence=[{'review_id': flow['rows'][0].id, **item}])
    assert flow['ask']('Show the original review', period=ALL).status_code == 502
    assert len(flow['calls']) == 1


def test_card_snapshot_excludes_author_and_other_source_metadata(flow):
    row = flow['rows'][0]
    row.source_metadata = {'author_name': 'Known reviewer', 'author_email': 'never-share@example.invalid',
                           'private_note': 'not part of review'}
    flow['db'].commit()
    prepared = service.build_evidence(flow['org'].id, flow['db'], Period(preset='all_time'))
    record = next(record for record in prepared['reviews'] if record['review_id'] == row.id)
    assert record['author_name'] == 'Known reviewer'
    assert 'never-share' not in json.dumps(prepared)
    assert 'private_note' not in json.dumps(prepared)
    _, cards = service.validate_answer(json.dumps({'answer': 'Here is the original review.', 'evidence': [
        {'review_id': row.id, 'kind': 'review'}]}), prepared, True)
    assert 'author' not in json.dumps(cards)
    assert 'Known reviewer' not in json.dumps(cards)


def test_rating_only_review_card_does_not_invent_written_content(flow):
    row = flow['rows'][4]
    flow['model'].update(answer='This review contains only a star rating.', evidence=[
        {'review_id': row.id, 'kind': 'review'}])
    response = flow['ask']('Show that review', period=ALL)
    assert response.status_code == 200
    source = response.json()['structured_data']['sources'][0]
    assert source['excerpt'] == 'Rating only - no written review'
    assert source['review']['original_review'] == ''


def test_prior_cards_remain_available_as_references_without_full_private_payload():
    message = SimpleNamespace(role='assistant', content='This review mentions repairs.', structured_data={
        'sources': [{'review_id': 3, 'excerpt': 'Repairs took two weeks.', 'kind': 'review',
                     'review': {'original_review': 'FULL ORIGINAL NOT NEEDED AGAIN', 'author_name': 'PRIVATE AUTHOR'}}],
        'raw_request': 'SECRET AUDIT'})
    history = service.history_message(message)
    assert 'Attached source cards:' in history['content']
    assert 'Repairs took two weeks.' in history['content']
    assert 'FULL ORIGINAL' not in history['content']
    assert 'PRIVATE AUTHOR' not in history['content']
    assert 'SECRET AUDIT' not in history['content']
    assert service.evidence_requested('show more', [history])
    assert service.evidence_requested('show them', [history])
    assert not service.evidence_requested('show them', [])


def test_code_calculated_topic_counts_have_matching_source_ids(flow):
    prepared = service.build_evidence(flow['org'].id, flow['db'], Period(preset='all_time'))
    for topic in prepared['calculated']['topics'].values():
        assert topic['review_count'] == len(topic['review_ids'])
        for sentiment, count in topic['sentiments'].items():
            assert count == len(topic['review_ids_by_sentiment'][sentiment])
        for sentiment, count in topic['review_counts_by_quotation_sentiment'].items():
            assert count == len(topic['review_ids_by_quotation_sentiment'][sentiment])


def test_only_json_transport_fence_is_unwrapped_not_answer_content(flow):
    flow['model']['raw'] = '```json\n' + json.dumps({'answer': 'Maintenance delays were reported.', 'evidence': []}) + '\n```'
    assert flow['ask'](period=ALL).status_code == 200
    flow['model']['raw'] = '```json\n' + json.dumps({'answer': 'x' * 1001, 'evidence': []}) + '\n```'
    assert flow['ask'](period=ALL).status_code == 502


def test_review_quote_selector_cannot_attach_foreign_record(flow):
    prepared = service.build_evidence(flow['org'].id, flow['db'], Period(preset='all_time'))
    with pytest.raises(ValueError, match='Unknown evidence record'):
        service.validate_answer(json.dumps({'answer': 'Here is the source.', 'evidence': [
            {'review_id': 9999999, 'kind': 'review'}]}), prepared, True)

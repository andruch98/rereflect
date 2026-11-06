"""Only equivalent, resolvable references may change shape before showing original sources."""
import json

import pytest

from src.services import ask_genius as service
from src.services.ask_genius_source_text import recovered_excerpt


TOPIC = 'Staff & Service'
REVIEW = {'review_id': 42, 'star_rating': 1, 'original_review': 'It’s noisy at night.\nStaff helped.',
          'saved_analysis': {'sentiment': 'negative', 'topics': [
              {'name': TOPIC, 'sentiment': 'mixed', 'quotations': [
                  {'text': 'Staff helped.', 'sentiment': 'positive'}]}]}}
SURVEY_ID = 'dc0cc723-9ee2-4c65-bc74-36fca9e61232'
SURVEY = {'survey_id': SURVEY_ID, 'questions': [{'id': 'follow_up_requested', 'answer': 'Yes'}]}
DATA = {'reviews': [REVIEW], 'surveys': [SURVEY]}


def validate(fields, **kwargs):
    return service.validate_answer(json.dumps({'answer': 'A finding.', **fields}), DATA, True, **kwargs)


@pytest.mark.parametrize('rating', ['1', 1, ['1']])
def test_equivalent_filters_select_the_same_authorized_record(rating):
    _, sources = validate({'selections': [{'topic': '  staff and SERVICE  ', 'sentiment': ' MIXED ',
                                           'star_ratings': rating}]})
    assert [(s['review_id'], s['topic']) for s in sources] == [(42, TOPIC)]


@pytest.mark.parametrize('field,value', [('review_id', True), ('review_id', '42.0'), ('review_id', '43'),
                                         ('quotation_index', False), ('quotation_index', '1e0')])
def test_untrusted_identifiers_remain_invalid(field, value):
    with pytest.raises(ValueError):
        validate({'evidence': [{'review_id': 42, 'kind': 'review', field: value}]})


def test_matching_index_and_quote_are_validated_against_same_saved_quote():
    ref = {'review_id': '42', 'kind': ' Analysis ', 'topic': 'staff and Service',
           'quotation_index': '0', 'excerpt': 'Staff helped.'}
    _, sources = validate({'evidence': [ref]})
    assert (sources[0]['kind'], sources[0]['label'], sources[0]['topic']) == ('analysis', 'Staff helped.', TOPIC)
    with pytest.raises(ValueError, match='Invalid saved quotation selector'):
        validate({'evidence': [{**ref, 'excerpt': 'It’s noisy at night.'}]})


def test_card_renders_stored_characters_and_never_semantic_approximation():
    ref = {'review_id': '42', 'kind': 'review', 'excerpt': "It's noisy at night. Staff helped."}
    _, sources = validate({'evidence': [ref]})
    assert sources[0]['excerpt'] == REVIEW['original_review']
    for paraphrase in ("It's not noisy", 'staff helped.', 'Staff didn’t help.'):
        with pytest.raises(ValueError, match='match the original'):
            validate({'evidence': [{**ref, 'excerpt': paraphrase}]})
    assert recovered_excerpt('It’s late. It‘s late.', "It's late") is None


def test_case_equivalent_source_ids_are_resolved_to_the_supplied_source():
    ctx = []
    _, _ = validate({'survey_context': [{'kind': 'SURVEY', 'survey_id': SURVEY_ID.upper(),
                                         'question_id': ' FOLLOW_UP_REQUESTED '}]}, survey_context=ctx)
    assert [(r['survey_id'], r['question_id']) for r in ctx] == [(SURVEY_ID, 'follow_up_requested')]
    with pytest.raises(ValueError, match='Unknown survey'):
        validate({'survey_context': [{'survey_id': SURVEY_ID.upper(), 'question_id': 'other'}]})


@pytest.mark.parametrize('field', ['selections', 'survey_selections'])
def test_empty_or_absent_filter_never_expands_to_every_record(field):
    for shape in ({}, [{}], [], None):
        _, cards = validate({field: shape})
        assert cards == []
    with pytest.raises(ValueError):
        validate({field: [{'unknown_filter': 'anything'}]})


def test_canonical_topic_collision_is_rejected():
    from copy import deepcopy
    data = deepcopy(DATA)
    data['reviews'][0]['saved_analysis']['topics'].append(
        {'name': 'Staff and Service', 'sentiment': 'negative', 'quotations': []})
    with pytest.raises(ValueError, match='Unknown saved analysis topic'):
        service.validate_answer(json.dumps({'answer': 'A finding.',
                                             'selections': [{'topic': 'staff and service'}]}), data, True)


def test_diagnostics_only_name_safe_fields_and_types():
    with pytest.raises(ValueError) as caught:
        validate({'selections': [{'star_ratings': 'private-message', 'api-key-SECRET': 'private-value'}]})
    diagnostic = service.validation_failure(caught.value)
    assert diagnostic['validation_reason'] == 'invalid_structure'
    detail = diagnostic['validation_detail']
    assert 'selections[0].star_ratings' in detail and 'list_type' in detail
    assert 'extra_forbidden' in detail
    assert all(word not in detail for word in ['private', 'SECRET', 'api-key'])

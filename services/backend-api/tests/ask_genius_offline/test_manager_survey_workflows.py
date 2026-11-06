"""Regression cases at the manager's survey/source, count, and model boundaries."""
import json

import pytest

from src.services import ask_genius as ai, ask_genius_surveys as surveys
from test_surveys import ALL, context, survey_flow


def test_original_answers_and_counts_select_the_intended_cohort(survey_flow):
    f = survey_flow
    subset = f['create_survey']()
    f['create_survey']('resolved')
    f['create_survey'](event_type='move_in_completed')

    def start():
        result = f['ask']('Show unresolved maintenance surveys.', period=ALL)
        assert result.json()['structured_data']['survey_match_ids'] == [subset.public_id]
        return result.json()['conversation_id']

    for name in ('Show me all surveys', 'Show me all submissions',
                 'How many survey responses did we receive during this period?', 'How many surveys did we receive in total?'):
        result = f['ask'](name, conversation_id=start())
        assert len(result.json()['structured_data']['survey_match_ids']) == 3
        assert result.json()['structured_data']['survey_event_types'] == []
    for name in ('Show the original answers behind that', 'How many of those surveys?', 'How many?'):
        result = f['ask'](name, conversation_id=start()).json()
        assert result['structured_data']['survey_match_ids'] == [subset.public_id]
        if name.startswith('How many'):
            assert 'preceding selection' in result['answer']
    assert not f['calls']


def test_review_imperative_does_not_add_review_records(survey_flow):
    f = survey_flow
    f['create_survey'](event_type='lease_month_3')
    result = f['ask']('Review the 3-month surveys.', period=ALL)
    assert result.status_code == 200
    assert context(f)['source_scope'] == 'surveys'
    assert not context(f)['reviews']
    assert surveys.source_scope('Review both the surveys and the reviews.') == 'mixed'
    assert surveys.source_scope('Which positive comment came from a public review rather than a survey?') == 'reviews'


def test_follow_up_counts_distinguish_submissions_people_and_missing_questions(survey_flow):
    f = survey_flow
    for resident, choice in [('a', 'yes'), ('a', 'yes'), ('b', 'no')]:
        record = f['create_survey'](event_type='lease_month_3', resident=resident)
        record.answers = {**record.answers, 'follow_up_requested': choice}
    f['create_survey'](event_type='move_in_completed')
    f['db'].commit()
    start = f['ask']('How many surveys requested follow-up?', period=ALL).json()
    assert start['answer'].startswith('2 survey response(s) answered Yes')
    assert '3 submission(s) recorded Yes or No' in start['answer']
    for question, expected in [('How many distinct residents requested follow-up?', '1 distinct resident(s) answered Yes'),
                               ('How many submissions did not request follow-up?', '1 survey response(s) answered No'),
                               ('How many 3-month survey responses said no when we asked if they wanted follow-up?', '1 survey response(s) answered No')]:
        result = f['ask'](question, conversation_id=start['conversation_id']).json()
        assert result['answer'].startswith(expected)
    compound = f['ask']('How many surveys requested follow-up about repairs?', period=ALL).json()
    assert 'no stored survey classification' in compound['answer']
    assert not f['calls']


def test_optional_findings_can_reference_a_subset_and_broad_notes_can_share_a_survey():
    sid, other = 'a' * 36, 'b' * 36
    template = {'questions': [{'id': 'quality'}, {'id': 'comment'}]}
    evidence = {'reviews': [], 'surveys': [{**template, 'survey_id': k} for k in (sid, other)]}
    notes = [{'survey_id': sid, 'question_ids': ['quality'], 'finding': 'Good overall.'},
             {'survey_id': sid, 'question_ids': ['comment'], 'finding': 'Needs follow-up.'}]
    def validate(e=None):
        return ai.validate_answer(json.dumps({'answer': 'Mixed.', 'survey_findings': notes}), e or evidence, False)
    assert validate()[0] == 'Mixed.'
    with pytest.raises(ValueError, match='cover the supplied cohort'):
        validate({**evidence, 'survey_findings_required': True})
    notes.append({'survey_id': other, 'question_ids': ['quality'], 'finding': 'Okay.'})
    assert validate({**evidence, 'survey_findings_required': True})[0] == 'Mixed.'
    notes[-1]['question_ids'] = ['invented']
    with pytest.raises(ValueError, match='Invalid survey finding'):
        validate()


def test_typographic_survey_excerpt_returns_original_or_rejects():
    row = {'survey_id': 'a' * 36, 'questions': [
        {'id': 'comment', 'answer': 'I can’t pay  15 today.'}, {'id': 'other', 'answer': 'fine'}]}
    src = surveys.source(row, "I can't pay 15 today.", question_id='comment')
    assert src['excerpt'] == src['label'] == 'I can’t pay  15 today.'
    for candidate, q in [('I can pay 15 today.', 'comment'), ("I can't pay 15 today.", 'other')]:
        with pytest.raises(ValueError, match='excerpt'):
            surveys.source(row, candidate, question_id=q)


def test_count_phrasings_for_overall_breakdown_and_empty_type(survey_flow):
    f = survey_flow
    f['create_survey']()
    f['create_survey'](event_type='lease_month_9')
    result = f['ask']('How many completed survey responses did this community receive during the selected period?', period=ALL)
    assert result.json()['answer'].startswith('2 completed survey')
    chat = result.json()['conversation_id']
    zero = f['ask']('How many lease-renewal-completed surveys came in?', conversation_id=chat).json()
    assert zero['answer'].startswith('0 completed lease renewal')
    types = f['ask']('How many responses did we get for each survey type?', conversation_id=chat).json()
    assert types['answer'].startswith('2 completed survey')
    assert all(line in types['answer'] for line in ['Maintenance: 1', '9-month renewal planning: 1', 'Lease renewal: 0'])
    assert len(types['structured_data']['survey_match_ids']) == 2
    assert not f['calls']


def test_survey_sentiment_request_interprets_originals_unless_asking_for_stored_analysis(survey_flow):
    f = survey_flow
    f['create_survey']()
    question = 'What is the overall sentiment in the maintenance survey comments?'
    result = f['ask'](question, period=ALL)
    assert result.status_code == 200 and f['calls'][-1][-1]['content'] == question
    assert len(context(f)['surveys']) == 1
    stored = f['ask']('Show me the stored survey sentiment.', period=ALL).json()
    assert 'not available' in stored['answer']
    assert len(f['calls']) == 1


def test_priorities_across_all_named_count_need_complete_coverage(survey_flow):
    f = survey_flow
    f['create_survey']()
    f['create_survey'](event_type='lease_month_3')
    first = f['ask']('Show maintenance surveys.', period=ALL).json()
    result = f['ask']('Based on all seven surveys, what should the property team address first?',
                      conversation_id=first['conversation_id'])
    assert result.status_code == 200
    model_data = context(f)
    assert model_data['survey_findings_required']
    assert len(model_data['surveys']) == 2
    assert not surveys.needs_findings('How many of all seven surveys requested follow-up?', model_data)


def test_type_union_and_renewal_comparison_select_authorized_types(survey_flow):
    f = survey_flow
    rows = {kind: f['create_survey'](event_type=kind) for kind in
            ('move_in_completed', 'move_out_completed', 'lease_renewed', 'lease_month_9')}
    response = f['ask']('Show me move-in or move-out surveys.', period=ALL)
    assert response.status_code == 200
    selected = response.json()['structured_data']
    assert set(selected['survey_match_ids']) == {rows[k].public_id for k in ('move_in_completed', 'move_out_completed')}
    assert not f['calls']
    ambiguous = f['ask']('Were those move-in or move-out surveys?', period=ALL)
    assert ambiguous.status_code == 422
    compare = f['ask']('Compare the move-in survey and the 9-month planning survey on apartment condition.', period=ALL)
    assert compare.status_code == 200
    assert {r['survey_id'] for r in context(f)['surveys']} == {rows['move_in_completed'].public_id, rows['lease_month_9'].public_id}


def test_reviewer_and_survey_identity_have_no_verified_link(survey_flow):
    f = survey_flow
    f['create_survey']()
    question = 'Did the faucet reviewer also submit the maintenance survey that mentioned nearly slipping?'
    answer = f['ask'](question, period=ALL).json()
    assert answer['structured_data']['source_scope'] == 'mixed'
    assert 'no verified identity link' in answer['answer']
    assert not f['calls']


@pytest.mark.parametrize('relation', ['recommendations', 'answer'])
def test_sources_behind_previous_recommendations_do_not_add_records(survey_flow, relation):
    f = survey_flow
    first = f['create_survey']()
    second = f['create_survey']('partially_resolved', resident='other')
    f['create_survey']('resolved', resident='uncited')
    cited = [row.public_id for row in (first, second)]
    f['model'].update(answer='Follow up on leaking faucets.', survey_context=[
        {'survey_id': sid, 'kind': 'survey', 'question_id': 'maintenance_comment'} for sid in cited])
    prior = f['ask']('What are the main improvements suggested by all surveys?', period=ALL)
    assert set(prior.json()['structured_data']['survey_match_ids']) == set(cited)
    result = f['ask'](f'Show me the survey responses behind your {relation}.',
                      conversation_id=prior.json()['conversation_id']).json()
    assert {s['survey_id'] for s in result['structured_data']['sources']} == set(cited)
    assert {s['question_id'] for s in result['structured_data']['sources']} == {'maintenance_comment'}
    assert len(f['calls']) == 1


def test_read_both_report_only_public_reviews(survey_flow):
    f = survey_flow
    f['create_survey']()
    result = f['ask']('Read both sets, but show only complaints in public reviews.', period=ALL)
    assert result.status_code == 200
    supplied = context(f)
    assert supplied['source_scope'] == 'mixed'
    assert supplied['reviews'] and supplied['surveys']
    assert supplied['display_sources_only'] == 'reviews'
    assert all(source.get('kind') != 'survey' for source in result.json()['structured_data']['sources'])


@pytest.mark.parametrize(('month', 'expected'), [('3', 'lease_month_3'), ('9', 'lease_month_9')])
def test_milestone_resident_names_a_survey_type(month, expected):
    question = f'What did the {month}-month resident say?'
    assert surveys.source_scope(question) == 'surveys'
    assert surveys.survey_types(question) == [expected]

"""Exact source cohorts, topic mapping and message-only limits; no provider calls."""
import json
import pytest
from src.services import ask_genius as service


def records():
    return {'reviews': [
        {'review_id': i, 'original_review': f'Actual review {i}. ' + 'Original content. ' * 300,
         'star_rating': 1 if i <= 78 else 5,
         'saved_analysis': {'status': 'available', 'sentiment': 'negative' if i <= 78 else 'positive',
                            'topics': [{'name': 'Staff', 'sentiment': 'mixed',
                                        'quotations': [{'text': f'Actual review {i}.', 'sentiment': 'negative' if i <= 78 else 'positive'}]}]}}
        for i in range(1, 101)]}


def test_filter_selects_all_78_matching_records_in_stable_order_without_model_transcription():
    answer, sources = service.validate_answer(json.dumps({'answer': 'Found 78 one-star reviews.',
        'selections': [{'star_ratings': [1, 2]}]}), records(), True)
    assert [s['review_id'] for s in sources] == list(range(1, 79))
    assert all(len(s['review']['original_review']) > 3000 for s in sources)
    assert service.displayed_answer_length(answer, sources) == len(answer)


def test_topic_filters_use_quote_sentiment_and_preserve_links_across_overlapping_topics():
    data = records()
    data['reviews'][0]['saved_analysis']['topics'].append({'name': 'Billing', 'sentiment': 'negative', 'quotations': []})
    _, sources = service.validate_answer(json.dumps({'answer': '- **Staff:** Complaints.\n- **Billing:** Fees.',
        'selections': [{'topic': 'Staff', 'sentiment': 'negative'}, {'topic': 'Billing'}]}), data, True)
    assert len([s for s in sources if s['topic'] == 'Staff']) == 78
    assert [(s['review_id'], s['topic']) for s in sources if s['topic'] == 'Billing'] == [(1, 'Billing')]


@pytest.mark.parametrize('selection', [{'star_ratings': [6]}, {'star_ratings': [True]}, {'star_ratings': ['1']}, {'topic': 'Invented'}, {'organization_id': 9}])
def test_untrusted_filters_fail_closed(selection):
    with pytest.raises(ValueError):
        service.validate_answer(json.dumps({'answer': 'Results.', 'selections': [selection]}), records(), True)


def test_selection_requires_permission_and_zero_matches_are_not_fabricated():
    with pytest.raises(ValueError):
        service.validate_answer(json.dumps({'answer': 'Results.', 'selections': [{}]}), records(), False)
    _, sources = service.validate_answer(json.dumps({'answer': 'No two-star reviews.', 'selections': [{'star_ratings': [2]}]}), records(), True)
    assert sources == []


def test_explanations_stay_1000_but_requested_analysis_can_use_3000():
    for expanded in (False, True):
        with pytest.raises(ValueError):
            service.validate_answer(json.dumps({'answer': 'a' * 1001, 'selections': [{}] if expanded else []}), records(), expanded)
    payload = {'answer': 'a' * 3000, 'evidence': [{'review_id': 1, 'kind': 'analysis', 'topic': 'Staff'}]}
    assert len(service.validate_answer(json.dumps(payload), records(), True)[0]) == 3000
    payload['answer'] += 'a'
    with pytest.raises(ValueError):
        service.validate_answer(json.dumps(payload), records(), True)

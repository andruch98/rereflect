"""Unambiguous source follow-ups preserve the preceding negative-topic scope."""
import json

import pytest

from src.services import ask_genius as service
from src.services.ask_genius_followups import topic_review_followup


def topic(name, sentiment='negative', quote_sentiment=None):
    return {
        'name': name, 'sentiment': sentiment,
        'quotations': [{'text': f'{name} feedback.',
                        'sentiment': quote_sentiment or sentiment}],
    }


def record(review_id, topics, overall='negative', stars=1):
    return {
        'review_id': review_id,
        'original_review': ' '.join(item['quotations'][0]['text'] for item in topics),
        'star_rating': stars,
        'saved_analysis': {'status': 'available', 'sentiment': overall, 'topics': topics},
    }


@pytest.fixture
def evidence():
    return {'reviews': [
        record(1, [topic('Staff'), topic('Billing')]),
        record(2, [topic('Staff', 'positive')], overall='positive', stars=5),
        # Topic evidence, not the overall review sentiment/rating, determines
        # eligibility. A mixed topic's negative quotation is sufficient.
        record(3, [topic('Staff', 'mixed', 'negative')], overall='positive', stars=5),
        record(4, [topic('Parking')]),
        record(5, [topic('Billing')]),
        record(6, [topic('Maintenance', 'positive')], overall='positive', stars=5),
    ]}


ANSWER = ('Negative topics in reviews include:\n\n'
          '- **Billing:** Residents reported unclear charges.\n'
          '- **Staff** (negative aspects): Residents reported poor responsiveness.')


def history(answer=ANSWER, question='What are the bad topics?', frequent=False):
    previous = []
    if frequent:
        previous = [
            {'role': 'user', 'content': 'Which topics came up most often in reviews during this period?'},
            {'role': 'assistant', 'content': '- **Staff:** Mentioned in 3 reviews.\n- **Billing:** Mentioned in 2 reviews.'},
        ]
    return previous + [
        {'role': 'user', 'content': question},
        {'role': 'assistant', 'content': answer},
    ]


def test_exact_three_turn_exchange_attaches_only_negative_sources_by_topic(evidence):
    result = topic_review_followup('let me see each review', evidence, history(frequent=True))
    assert result is not None
    answer, sources = result
    assert answer == ANSWER
    assert [(s['topic'], s['review_id']) for s in sources] == [
        ('Billing', 1), ('Billing', 5), ('Staff', 1), ('Staff', 3),
    ]
    assert 2 not in [s['review_id'] for s in sources]  # purely positive
    assert 4 not in [s['review_id'] for s in sources]  # unrelated negative topic
    assert all(s['kind'] == 'review' and s['review']['original_review'] for s in sources)


@pytest.mark.parametrize('question', [
    'Let me see each review.', 'Show me all reviews', 'Show those reviews',
    'Please show me the supporting reviews!', 'Give me these reviews please',
    'Let me see the reviews for each', 'List the reviews for each topic',
])
def test_short_source_only_followups(evidence, question):
    assert topic_review_followup(question, evidence, history()) is not None


@pytest.mark.parametrize('question', [
    'What are the bad topics?', 'What are the negative topics in reviews?',
    'Which topics had negative feedback in reviews during this period?',
    'Which topics had negative feedback for the selected period?',
])
def test_broad_negative_topic_requests(evidence, question):
    assert topic_review_followup('let me see each review', evidence, history(question=question)) is not None


@pytest.mark.parametrize('question', [
    'Now show all reviews, including positive ones.',
    'Show me positive reviews', 'Show all reviews from this period',
    'Show me every review in all available history',
    'Show me the one- and two-star reviews', 'Show all reviews and summarize them',
    'Let me see each review about late fees', 'Do not show me supporting reviews',
    'Show me each review from last month', 'Show me all survey responses',
    'Tell me who wrote each review', 'Yes please',
])
def test_explicit_scope_changes_and_other_requests_use_normal_path(evidence, question):
    assert topic_review_followup(question, evidence, history()) is None


@pytest.mark.parametrize('prior_question', [
    'What are the late fee complaints?', 'What are the negative themes in billing?',
    'Which topics had negative feedback in one-star reviews during this period?',
    'Which staff members got complaints?', 'What do residents praise?',
    'Which topics came up most often in reviews during this period?',
])
def test_prior_theme_rating_positive_and_ambiguous_scopes_use_normal_path(evidence, prior_question):
    assert topic_review_followup('let me see each review', evidence, history(question=prior_question)) is None


def test_earlier_rating_filter_is_not_silently_dropped(evidence):
    messages = [
        {'role': 'user', 'content': 'Show me the one-star reviews'},
        {'role': 'assistant', 'content': 'Here are the one-star reviews.'},
        *history(),
    ]
    assert topic_review_followup('let me see each review', evidence, messages) is None


@pytest.mark.parametrize('heading', [
    'Staff:', '**Staff:**', '**Staff**:', 'Staff (negative aspects):',
    '**Staff** (negative aspects):', '**Staff (negative aspects):**',
    '**Staff (negative feedback)**:',
])
def test_known_topic_heading_variants(evidence, heading):
    result = topic_review_followup('let me see each review', evidence,
                                  history(answer=f'- {heading} Poor responsiveness.'))
    assert result is not None
    assert [s['review_id'] for s in result[1]] == [1, 3]


@pytest.mark.parametrize('answer', [
    '- **Unknown:** Complaints.',
    '- **Staff:** Complaints.\n- **Unknown:** More complaints.',
    '- **Staff:** Complaints.\n- **Staff:** Other complaints.',
    '- **Staff:**',
    '- **Staff:** Complaints.\n  - Billing: Fees.',
    '  - Staff:\n- Billing: Fees.',
    '- **Staff:** Complaints.\nAnother issue is Billing.',
    'Staff has complaints.',
    '- **Staff** (late fees): Complaints.',
    '- **St**aff: Complaints.',
    '- **Staff and Billing:** Complaints.',
    '- **Staff:** Complaints.\n\nWould you like to see supporting reviews?',
    '- **Staff:** Complaints.\n\nAttached source cards: []',
])
def test_malformed_incomplete_or_narrower_topic_mapping_falls_back(evidence, answer):
    assert topic_review_followup('let me see each review', evidence, history(answer=answer)) is None


def test_any_topic_without_actual_negative_sources_falls_back(evidence):
    answer = '- Staff: Poor responsiveness.\n- Maintenance: Reported delays.'
    assert topic_review_followup('let me see each review', evidence, history(answer=answer)) is None


def test_answer_limit_is_not_bypassed_by_popup_sources(evidence):
    answer = '- Staff: ' + 'x' * 1000
    assert topic_review_followup('let me see each review', evidence, history(answer=answer)) is None


def test_uses_existing_validator_with_explicit_topic_and_sentiment(evidence, monkeypatch):
    original = service.validate_answer
    calls = []

    def validate(raw, actual_evidence, expanded):
        calls.append((json.loads(raw), actual_evidence, expanded))
        return original(raw, actual_evidence, expanded)

    monkeypatch.setattr(service, 'validate_answer', validate)
    result = topic_review_followup('let me see each review', evidence, history())
    assert result is not None
    assert calls == [({'answer': ANSWER, 'selections': [
        {'topic': 'Billing', 'sentiment': 'negative'},
        {'topic': 'Staff', 'sentiment': 'negative'},
    ]}, evidence, True)]


def test_does_not_generate_counts_or_rewrite_prior_answer(evidence):
    result = topic_review_followup('let me see each review', evidence, history())
    assert result is not None
    assert result[0] == ANSWER
    assert not any(character.isdigit() for character in result[0])
    # The actual selectors, not invented totals or review IDs in prose, drive UI counts.
    assert len({s['review_id'] for s in result[1]}) == 3
    assert len(result[1]) == 4  # one review belongs to both topics


@pytest.mark.parametrize('answer', [
    '- Staff: 9 reviews mention poor responsiveness.',
    '- Staff: Nine reviews mention poor responsiveness.',
    '- Staff: The majority of reviews criticize service.',
    '- Staff: Half of reviews criticize service.',
    '- Staff: Review 1 describes poor responsiveness.',
])
def test_prior_numeric_claims_are_not_reused_as_factual_authority(evidence, answer):
    assert topic_review_followup('let me see each review', evidence, history(answer=answer)) is None


def test_validator_failure_falls_back(evidence, monkeypatch):
    def validate(*args, **kwargs):
        raise ValueError('Invalid source data')

    monkeypatch.setattr(service, 'validate_answer', validate)
    assert topic_review_followup('let me see each review', evidence, history()) is None


@pytest.mark.parametrize('messages', [[], [{'role': 'user', 'content': 'What are the bad topics?'}],
    [{'role': 'assistant', 'content': ANSWER}, {'role': 'user', 'content': 'What are the bad topics?'}],
])
def test_missing_or_incomplete_exchange_falls_back(evidence, messages):
    assert topic_review_followup('let me see each review', evidence, messages) is None

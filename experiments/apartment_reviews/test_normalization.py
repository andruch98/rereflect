"""Formatting cleanup must preserve evidence and reject substantive changes."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/worker-service'))
from src.apartment_reviews import TOPICS, validate_result


TEXT = 'The maintenance team was helpful. The pool is dirty.'
VALID = {'sentiment': 'mixed', 'topics': [
    {'name': 'Maintenance & repairs', 'sentiment': 'positive',
     'quotations': ['The maintenance team was helpful.']},
    {'name': 'Amenities', 'sentiment': 'negative',
     'quotations': ['The pool is dirty.']},
]}


def check(data, text=TEXT, rating=3):
    raw = json.dumps(data, ensure_ascii=False)
    before = copy.deepcopy(data)
    corrections = []
    accepted = validate_result(raw, text, rating, normalizations=corrections)
    assert data == before
    assert raw == json.dumps(before, ensure_ascii=False)
    assert all(q in text for t in accepted['topics'] for q in t['quotations'])
    return accepted, corrections


def test_combined_safe_formatting_preserves_analysis_and_audits_corrections():
    messy = {'sentiment': ' MIXED\n', 'summary': 'ignored extra field', 'topics': [
        {'name': ' maintenance   and repairs ', 'sentiment': 'Positive ',
         'quotes': 'The maintenance\nteam was helpful.', 'confidence': 0.9},
        {'name': ' AMENITIES ', 'sentiment': 'NEGATIVE',
         'quotations': ['', ' \t', 'The pool is dirty.', 'The pool is dirty.']},
    ]}
    messy['topics'].append(copy.deepcopy(messy['topics'][0]))
    accepted, corrections = check(messy)
    assert accepted == VALID
    assert corrections
    assert any(c['change'] == 'original_source_quotation_restored' for c in corrections)
    # Revalidation is idempotent and no additional correction is necessary.
    assert check(accepted) == (VALID, [])


@pytest.mark.parametrize('name', TOPICS)
def test_only_taxonomy_and_explicit_and_aliases_are_canonicalized(name):
    data = {'sentiment': 'neutral', 'topics': {
        'name': name.replace('&', 'and').upper() + ' ',
        'sentiment': ' Neutral ', 'quotations': 'A fictional sentence.',
    }}
    accepted, corrections = check(data, 'A fictional sentence.')
    assert accepted['topics'] == [{'name': name, 'sentiment': 'neutral',
                                   'quotations': ['A fictional sentence.']}]
    assert corrections


@pytest.mark.parametrize('source,quote', [
    ('Efficient  and helpful.', 'Efficient and helpful.'),
    ('Efficient\n\tand helpful.', 'Efficient and helpful.'),
    ('Efficient and helpful.', '  Efficient\tand helpful.  '),
    ('They said “we’re ready”.', 'They said "we\'re ready".'),
    ('They said "we\'re ready".', 'They said “we’re ready”.'),
    ('Price: $100.00 (paid).', 'Price:  $100.00 (paid).'),
    ('she became rude.', 'She became rude.'),
    ('She became rude.', 'she became rude.'),
    ('“she became rude.”', '"She  became rude."'),
])
def test_quotes_are_replaced_with_contiguous_original_source(source, quote):
    data = {'sentiment': 'neutral', 'topics': [
        {'name': 'Staff & customer service', 'sentiment': 'neutral', 'quotations': [quote]}]}
    accepted, corrections = check(data, source)
    assert accepted['topics'][0]['quotations'] == [source]
    assert any(c['change'] == 'original_source_quotation_restored' for c in corrections)


def test_null_topics_is_explicit_empty_list_not_missing_information():
    accepted, corrections = check({'sentiment': ' Positive ', 'topics': None}, '', 4)
    assert accepted == {'sentiment': 'positive', 'topics': []}
    assert corrections
    # Text-bearing reviews may legitimately have no matching topic as before.
    assert check({'sentiment': 'neutral', 'topics': None}, 'A general remark.')[0]['topics'] == []
    with pytest.raises(ValueError):
        check({'sentiment': 'positive'}, '', 4)


def test_identical_json_keys_are_removed_but_conflicts_still_fail():
    changes = []
    raw = '{"sentiment":"positive","sentiment":"positive","topics":[]}'
    assert validate_result(raw, '', 4, normalizations=changes) == {'sentiment': 'positive', 'topics': []}
    assert changes[0]['change'] == 'identical_duplicate_key_removed'
    for raw in [
        '{"sentiment":"positive","sentiment":"negative","topics":[]}',
        '{"sentiment":"positive","topics":[],"extra":{"x":false},"extra":{"x":0}}',
    ]:
        with pytest.raises(ValueError, match='Conflicting duplicate JSON key'):
            validate_result(raw, '', 4)


@pytest.mark.parametrize('quote', [
    'The maintenance team was not helpful.',  # Added negation.
    'The maintenence team was helpful.',  # Typo correction/matching is deferred.
    'The maintenance team was helpful...The pool is dirty.',  # Joined passages.
    'The Pool is dirty.',  # Only an opening letter's case may change.
    'THE pool is dirty.',  # Not a case-insensitive search of the whole passage.
    'The pool was dirty.',  # Changed wording.
])
def test_unsupported_evidence_still_rejects_the_whole_result(quote):
    data = copy.deepcopy(VALID)
    data['topics'][1]['quotations'] = [quote]
    with pytest.raises(ValueError, match='Quotation does not match source'):
        check(data)


@pytest.mark.parametrize('bad', [None, 0, {}, [], ['', ' \t']])
def test_missing_or_unusable_evidence_still_fails(bad):
    data = copy.deepcopy(VALID)
    data['topics'][0]['quotations'] = bad
    with pytest.raises(ValueError):
        check(data)


def test_blank_quotes_do_not_hide_a_nonblank_invalid_quote():
    data = copy.deepcopy(VALID)
    data['topics'][0]['quotations'] += ['', 'An unsupported quotation.']
    with pytest.raises(ValueError):
        check(data)


def test_conflicting_duplicate_topics_are_not_merged_or_partially_saved():
    for changed_field, value in [('sentiment', 'negative'), ('quotations', ['helpful'])]:
        data = copy.deepcopy(VALID)
        duplicate = copy.deepcopy(data['topics'][0])
        duplicate[changed_field] = value
        data['topics'].append(duplicate)
        with pytest.raises(ValueError, match='Conflicting duplicate topic'):
            check(data)


@pytest.mark.parametrize('name', ['Maintenance', 'Maintenance and repair', 'system_crash'])
def test_no_fuzzy_topic_mapping(name):
    data = copy.deepcopy(VALID)
    data['topics'][0]['name'] = name
    with pytest.raises(ValueError, match='Unknown topic'):
        check(data)


def test_alias_conflicts_missing_fields_and_invalid_labels_still_fail():
    variations = []
    data = copy.deepcopy(VALID)
    data['topics'][0]['quotes'] = ['helpful']
    variations.append(data)
    data = copy.deepcopy(VALID)
    del data['topics'][0]['sentiment']
    variations.append(data)
    data = copy.deepcopy(VALID)
    data['topics'][0]['sentiment'] = 'mostly positive'
    variations.append(data)
    variations += [{'sentiment': 'other', 'topics': []}, {'sentiment': 'neutral', 'topics': ''}]
    for data in variations:
        with pytest.raises(ValueError):
            check(data)


@pytest.mark.parametrize('prefix,suffix', [('```json\n', '\n```'), ('Here is the analysis: ', '')])
def test_json_extraction_remains_deferred(prefix, suffix):
    with pytest.raises(ValueError):
        validate_result(prefix + json.dumps(VALID) + suffix, TEXT, 3)


def test_rating_only_mapping_is_not_relaxed():
    with pytest.raises(ValueError, match='rating-only'):
        check({'sentiment': 'unknown', 'topics': None}, '', 4)


def test_normalized_case_match_prefers_existing_case_before_opening_cleanup():
    source='she  was rude. She  was rude.'
    data={'sentiment':'negative','topics':[{'name':'Staff & customer service',
          'sentiment':'negative','quotations':['She was rude.']}]}
    accepted,_=check(data,source)
    assert accepted['topics'][0]['quotations']==['She  was rude.']


def test_unrelated_inputs_are_still_validated_before_output_cleanup():
    for rating in [True, '4', 4.0, 0, 6]:
        with pytest.raises(ValueError):
            check({'sentiment': 'positive', 'topics': None}, '', rating)

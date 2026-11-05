"""Approved examples are request instructions, never current property evidence."""
import json
from pathlib import Path

import pytest

from test_surveys import ALL, context, survey_flow
from src.services import ask_genius as service


@pytest.mark.parametrize('question,scope', [
    ('Summarize the maintenance surveys.', 'surveys'),
    ('Summarize the reviews.', 'reviews'),
    ('Compare surveys and reviews.', 'mixed'),
])
def test_complete_bank_reaches_each_model_request_separate_from_evidence(survey_flow, question, scope):
    f = survey_flow
    f['create_survey'](comment='Unique current survey comment.')
    response = f['ask'](question, period=ALL)
    assert response.status_code == 200, response.text
    bank = Path(service.__file__).with_name('ask_genius_survey_examples.md').read_text(encoding='utf-8')
    messages = f['calls'][-1]
    assert messages[0]['role'] == 'system'
    assert messages[0]['content'].count(bank) == 1
    assert bank.count('## Example ') == 5
    assert '**Complete source-question appendix:**' in bank
    evidence = context(f)
    assert evidence['source_scope'] == scope
    assert bank not in messages[1]['content']
    assert 'PARKING TOO hrd at night' not in json.dumps(evidence)
    assert evidence.get('survey_calculated', {}).get('submission_count') == (None if scope == 'reviews' else 1)
    if scope == 'reviews':
        assert 'surveys' not in evidence
        assert evidence['calculated']['review_count'] == 5
        assert evidence['reviews'][0]['saved_analysis']['status'] == 'available'
    followup = f['ask']('Explain that further.', conversation_id=response.json()['conversation_id'])
    assert followup.status_code == 200, followup.text
    assert f['calls'][-1][0]['content'].count(bank) == 1


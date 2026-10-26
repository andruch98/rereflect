"""Quotation labels preserve both sides without guessing from duplicate topics."""
import copy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'services/worker-service'))
from src.apartment_reviews import validate_result, messages
from export_results import grouped_analysis

TEXT = 'Alex was helpful. Sam was rude.'
VALID = {'sentiment':'mixed','topics':[{'name':'Staff & customer service','sentiment':'mixed','quotations':[
    {'text':'Alex was helpful.','sentiment':'positive'},
    {'text':'Sam was rude.','sentiment':'negative'}]}]}

def check(data, text=TEXT):
    return validate_result(json.dumps(data), text, 3, require_labeled_quotations=True)

def test_both_sides_preserved_and_grouped():
    assert check(VALID)==VALID
    rendered=grouped_analysis(check(VALID))
    assert rendered.index('**Positive**') < rendered.index('Alex was helpful') < rendered.index('**Negative**') < rendered.index('Sam was rude')
    assert rendered.count('Staff')==1

def test_tagged_normalization_and_idempotence():
    data=copy.deepcopy(VALID)
    data['topics'][0]['quotations'][0]={'text':'Alex  was helpful.','sentiment':' Positive ','confidence':0.9}
    changes=[]
    found=validate_result(json.dumps(data),TEXT,3,require_labeled_quotations=True,normalizations=changes)
    assert found==VALID and changes
    assert check(found)==found

@pytest.mark.parametrize('bad',[None,{},'Alex was helpful.',{'text':'Alex was helpful.'},{'text':'Alex was helpful.','sentiment':'mixed'},{'text':'Alex was not helpful.','sentiment':'negative'}])
def test_bad_evidence_is_not_guessed(bad):
    data=copy.deepcopy(VALID);data['topics'][0]['quotations'][0]=bad
    with pytest.raises(ValueError): check(data)

def test_mixed_requires_both_sides():
    data=copy.deepcopy(VALID);data['topics'][0]['quotations'].pop()
    with pytest.raises(ValueError,match='requires positive and negative'): check(data)

def test_both_sides_require_mixed_topic():
    data=copy.deepcopy(VALID);data['topics'][0]['sentiment']='positive'
    with pytest.raises(ValueError,match='require a mixed'): check(data)

def test_same_quote_cannot_supply_both_sides():
    data=copy.deepcopy(VALID);data['topics'][0]['quotations'][1]['text']='Alex was helpful.'
    with pytest.raises(ValueError,match='Conflicting sentiments'): check(data)

def test_single_object_and_duplicates_are_cleaned():
    data={'sentiment':'positive','topics':[{'name':'Staff & customer service','sentiment':'positive','quotations':VALID['topics'][0]['quotations'][0]}]}
    found=check(data);assert len(found['topics'][0]['quotations'])==1
    found['topics'][0]['quotations']*=2
    assert len(check(found)['topics'][0]['quotations'])==1

def test_legacy_results_are_not_relabelled():
    data={'sentiment':'positive','topics':[{'name':'Staff & customer service','sentiment':'positive','quotations':['Alex was helpful.']}]}
    assert validate_result(json.dumps(data),TEXT,3)==data
    assert '**Unlabeled**' in grouped_analysis(data)
    with pytest.raises(ValueError,match='sentiment is required'):check(data)

def test_rating_only_and_prompt():
    assert validate_result('{"sentiment":"positive","topics":[]}', '',4,require_labeled_quotations=True)['topics']==[]
    prompt=messages(TEXT,3)[0]['content']
    assert 'Never return separate entries' in prompt
    assert 'different employees' in prompt

def test_review_text_cannot_inject_markdown():
    data=copy.deepcopy(VALID);data['topics'][0]['quotations'][0]['text']='<script>evil</script>\n# fake heading'
    rendered=grouped_analysis(data)
    assert '<script>' not in rendered and '\n# fake' not in rendered

"""Fictional offline checks; never call a live provider."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'services/worker-service'))
from src.apartment_reviews import KEYWORDS, keyword_result, messages, validate_result
from src.llm import experiment


def result(text, rating=3):
    return keyword_result(text, rating, lambda _: {'label': 'neutral'})


def names(text):
    return {t['name'] for t in result(text)['topics']}


def test_every_approved_term_and_case():
    for name, terms in KEYWORDS.items():
        for term in terms:
            assert name in names(term.upper()), (name, term)


@pytest.mark.parametrize('text', ['across toward neighborhood', 'friendly helpful rude', 'Lake House', 'cool air water', 'charge a device', 'approved denied applied', 'keys first week first month'])
def test_no_word_fragments_or_unapproved_keywords(text):
    topics = names(text)
    if text == 'across toward neighborhood':
        assert topics == {'Location, views & surroundings'}
    else:
        assert topics == set()


@pytest.mark.parametrize('topic,excluded,valid', [
 ('Cleanliness & trash','garbage disposal; clean record; clean background','dirty garbage'),
 ('Security & safety','security deposit','security cameras'),
 ('Amenities','pool of water','pool'),
 ('Pricing & value','rent an apartment','rent'),
 ('Management & ownership','dog owners; pet owner; car owner','owner'),
 ('Location, views & surroundings','close to giving up','close to shopping'),
])
def test_occurrence_specific_exclusions(topic, excluded, valid):
    assert topic not in names(excluded)
    assert topic in names(excluded+'; '+valid)


def test_overlaps_and_exact_evidence():
    text = 'The AC repaired by maintenance staff. Dirty pool and washer in laundry room. Security deposit and electric bill.'
    found = result(text)['topics']
    assert len(found) == len({t['name'] for t in found})
    assert {'Maintenance & repairs','Air conditioning','Staff & customer service','Amenities','Appliances & in-unit equipment','Fees, deposits & billing','Utilities','Cleanliness & trash'} <= {t['name'] for t in found}
    assert 'Security & safety' not in {t['name'] for t in found}
    for topic in found:
        assert topic['sentiment'] == 'unknown'
        for match in topic['matches']:
            assert text[match['start']:match['end']] == match['text']


@pytest.mark.parametrize('rating,label', [(1,'negative'),(2,'negative'),(3,'neutral'),(4,'positive'),(5,'positive')])
def test_rating_only(rating,label):
    def no_engine(_): raise AssertionError('Rating-only should not need the text sentiment engine')
    found=keyword_result('', rating, no_engine)
    assert found['topics']==[] and found['sentiment']==label
    assert validate_result(json.dumps({'sentiment':label,'topics':[]}), '', rating)


def test_full_text_and_prompt_names_only():
    text = '  fictional text\n'*1000 + 'unique end 🏡\n'
    request = messages(text, 4)
    assert json.loads(request[-1]['content']) == {'text':text,'star_rating':4}
    assert 'work order' not in request[0]['content']
    assert 'system_crash' not in request[0]['content']


def test_validation():
    text = 'Quiet neighbors. The pool is dirty.'
    data = {'sentiment':'mixed','topics':[{'name':'Noise & neighbors','sentiment':'positive','quotations':['Quiet neighbors.']}, {'name':'Amenities','sentiment':'negative','quotations':['The pool is dirty.']}]}
    assert validate_result(json.dumps(data),text,3)==data
    for invalid in [dict(data, sentiment='other'), dict(data, topics=data['topics']*2), dict(data, summary='extra'), dict(data, topics=[{'name':'Amenities','sentiment':'negative','quotations':['The pool was dirty.']}]), dict(data, topics=[{'name':'system_crash','sentiment':'negative','quotations':['dirty']}])]:
        with pytest.raises(ValueError): validate_result(json.dumps(invalid),text,3)
    with pytest.raises(ValueError): validate_result('{"sentiment":"neutral","sentiment":"mixed","topics":[]}',text,3)


@pytest.fixture
def budget(tmp_path,monkeypatch):
    records=[{'source_id':'fiction-'+str(i),'text':'Quiet '+str(i),'star_rating':4} for i in range(6)]
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'records':records}))
    monkeypatch.setenv('APARTMENT_EXPERIMENT_MANIFEST',str(manifest))
    monkeypatch.setenv('APARTMENT_EXPERIMENT_LEDGER',str(tmp_path/'ledger.sqlite'))
    return records


def test_budget_duplicate_unknown_and_stop(budget):
    for record in budget:
        experiment.reserve(record['source_id'],{'messages':messages(record['text'],4)})
    with pytest.raises(experiment.ExperimentBlocked): experiment.reserve('fiction-0',{'messages':messages('Quiet 0',4)})
    with pytest.raises(experiment.ExperimentBlocked): experiment.reserve('fiction-7',{'messages':messages('Quiet 7',4)})
    with experiment.connection() as db: assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==6


def test_shared_configuration_error_stops_next_request(budget):
    experiment.reserve('fiction-0',{'messages':messages('Quiet 0',4)})
    experiment.finish('fiction-0',error='AuthenticationError (HTTP 401)',stop=True)
    with pytest.raises(experiment.ExperimentBlocked,match='stopped'):
        experiment.reserve('fiction-1',{'messages':messages('Quiet 1',4)})


def test_wrong_input_fails_before_reservation(budget):
    with pytest.raises(experiment.ExperimentBlocked):
        experiment.reserve('fiction-0',{'messages':messages('truncated',4)})


def load_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_private_selection_and_import(tmp_path):
    import csv
    prepare=load_file('prepare',Path(__file__).with_name('prepare_input.py')).prepare
    validate_rows=load_file('apartment_import',ROOT/'services/backend-api/src/services/apartment_import.py').validate_rows
    ids=['fiction-'+str(i) for i in range(6)]
    (tmp_path/'ids.json').write_text(json.dumps(ids))
    text='  Full text\n'+('x'*3000)+'🦋\n'
    with (tmp_path/'input.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['id','review','rating','old_response'])
        for i in reversed(range(7)): writer.writerow(['fiction-'+str(i),text if i else '',4,'private old response excluded'])
    before=(tmp_path/'input.csv').read_bytes()
    manifest=prepare(tmp_path/'input.csv',tmp_path/'ids.json',tmp_path/'selected','id','review','rating')
    assert (tmp_path/'input.csv').read_bytes()==before
    assert [r['source_id'] for r in manifest['records']]==ids
    assert manifest['records'][1]['text']==text
    with (tmp_path/'selected/ai.csv').open(newline='') as f: rows=validate_rows(list(csv.DictReader(f)))
    assert rows[0]['text']=='' and rows[1]['text']==text
    assert 'old_response' not in json.dumps(rows)
    with pytest.raises(ValueError): validate_rows(rows[:5])

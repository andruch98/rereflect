"""Offline transport test with a migrated isolated PostgreSQL DB and Redis.

Run with backend-api on PYTHONPATH and DATABASE_URL/REDIS_* pointing ONLY at a
new disposable experiment stack. Uses auth dependency overrides; does not test
login or the frontend. The child worker ALWAYS mocks the OpenAI transport.
"""
import csv
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime,timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from src.api.routes.feedback import router
from src.api.dependencies import get_current_org,get_current_user,get_current_usage
from src.database.session import SessionLocal,get_db
from src.models.organization import Organization
from src.models.usage import UsageRecord
from src.models.feedback import FeedbackItem

ROOT=Path(__file__).resolve().parents[2]
private=Path(tempfile.mkdtemp(prefix='apartment-offline-',dir=os.environ['APARTMENT_TEST_WORKDIR']))
text='  Quiet neighbors.\n'+('Full fictional text. '*200)+'The pool is dirty.\n'
records=[{'source_id':'fiction-'+str(i),'text':text if i else '', 'star_rating':4 if i==0 else 3} for i in range(6)]
manifest=private/'manifest.json';manifest.write_text(json.dumps({'records':records}))
with SessionLocal() as db:
    org=Organization(name='Offline apartment workflow fixture',ai_analysis_enabled=True)
    db.add(org);db.commit();db.refresh(org)
    org_id=org.id
    usage=UsageRecord(organization_id=org_id,period_start=datetime.utcnow(),period_end=datetime.utcnow()+timedelta(days=30))
    db.add(usage);db.commit();db.refresh(usage)
    usage_id=usage.id
os.environ['APARTMENT_EXPERIMENT_ORG_ID']=str(org_id)
app=FastAPI();app.include_router(router)
# Use a fresh session per API request, like the real application.
def db_override():
    with SessionLocal() as db: yield db
app.dependency_overrides[get_db]=db_override
app.dependency_overrides[get_current_org]=lambda: SimpleNamespace(id=org_id,plan='free',ai_analysis_enabled=True,auto_assignment_enabled=False)
app.dependency_overrides[get_current_user]=lambda: SimpleNamespace(id=1,organization_id=org_id,role='owner')
def usage_override(db=Depends(get_db)):
    return db.get(UsageRecord,usage_id)
app.dependency_overrides[get_current_usage]=usage_override
# The importer, queue, worker, ORM and response schema are real.
child_env=dict(os.environ, PYTHONPATH=str(ROOT/'services/worker-service')+':'+str(ROOT/'services/analysis-engine/src'),
               APARTMENT_EXPERIMENT_MANIFEST=str(manifest),APARTMENT_EXPERIMENT_LEDGER=str(private/'ledger.sqlite'),
               APARTMENT_EXPERIMENT_MODEL='gpt-4.1-mini',OPENAI_API_KEY='offline-fictional-key')
log=(private/'worker.log').open('w')
worker=subprocess.Popen([sys.executable,str(Path(__file__).with_name('mock_worker.py'))],env=child_env,stdout=log,stderr=log)
try:
    with TestClient(app) as client:
        for mode in ('ai','fallback'):
            stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=['text','star_rating','source_external_id','source']);writer.writeheader()
            for r in records: writer.writerow(dict(text=r['text'],star_rating=r['star_rating'],source_external_id=r['source_id'],source='apartment_review_'+mode))
            response=client.post('/api/v1/feedback/import-csv',files={'file':(mode+'.csv',stream.getvalue(),'text/csv')})
            assert response.status_code==200,response.text
            assert response.json()['imported_count']==6 and response.json()['failed_count']==0
            duplicate=client.post('/api/v1/feedback/import-csv',files={'file':(mode+'.csv',stream.getvalue(),'text/csv')})
            assert duplicate.status_code==409,duplicate.text
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            with SessionLocal() as db:
                count=db.query(FeedbackItem).filter(FeedbackItem.organization_id==org_id,FeedbackItem.apartment_analysis.isnot(None)).count()
            if count==12: break
            if worker.poll() is not None: raise RuntimeError('Mock worker exited; see '+str(private/'worker.log'))
            time.sleep(.2)
        assert count==12,'Worker did not persist all records; see '+str(private/'worker.log')
        listing=client.get('/api/v1/feedback/',params={'page_size':100}).json()
        assert listing['total']==12,listing
        with SessionLocal() as db:
            assert db.get(UsageRecord,usage_id).feedback_count==12
        for item in listing['items']:
            original=next(r for r in records if r['source_id']==item['source_external_id'])
            assert item['text']==original['text'] and item['star_rating']==original['star_rating']
            detail=client.get('/api/v1/feedback/'+str(item['id'])).json()
            assert detail['apartment_analysis']==item['apartment_analysis']
            with SessionLocal() as db:
                saved=db.get(FeedbackItem,item['id'])
                assert saved.apartment_analysis==detail['apartment_analysis']
            final=item['apartment_analysis']['final_result']
            if item['source']=='apartment_review_ai':
                assert final['method']=='ai_model'
                assert item['sentiment_label']==('positive' if not item['text'] else 'mixed')
            else:
                assert final['method']=='keyword_fallback'
                assert item['apartment_analysis']['ai_attempt'] is None
    with sqlite3.connect(private/'ledger.sqlite') as db:
        assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==6
    from export_results import export
    report=export({'records':records,'source_sha256':'fictional-fixture'},listing['items'],private/'ledger.sqlite',private/'export','offline-fixture')
    assert report['successful_ai_analyses']==6
    assert all(r['approval']=='' and all(c['passed'] for c in r['code_checks']) for r in report['reviews'])
    print(json.dumps({'passed':True,'fixture_records':12,'mocked_provider_calls':6,'paid_calls':0,
                      'verified':['real CSV router','Redis queue','Celery worker','OpenAI provider with mocked SDK transport','PostgreSQL save','list/detail API readback','duplicate import rejection'],
                      'not_verified':['authentication','frontend','live provider','private six reviews'], 'logs':str(private)}))
finally:
    worker.terminate()
    try: worker.wait(timeout=10)
    except subprocess.TimeoutExpired: worker.kill();worker.wait()
    log.close()

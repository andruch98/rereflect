"""Offline integration worker. The SDK transport is always replaced, never live."""
import json
from types import SimpleNamespace

from src.llm.providers.openai import OpenAIProvider
from src.celery_app import celery_app


class OfflineClient:
    def __init__(self):
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def with_options(self, **kwargs):
        assert kwargs == {'max_retries':0}
        return self

    def create(self, **kwargs):
        record=json.loads(kwargs['messages'][-1]['content'])
        text=record['text']
        sentiment='positive' if record['star_rating'] >= 4 else 'negative' if record['star_rating'] <= 2 else 'neutral'
        topics=[]
        if text:
            sentiment='mixed'
            topics=[{'name':'Noise & neighbors','sentiment':'positive','quotations':['Quiet neighbors.']},
                    {'name':'Amenities','sentiment':'negative','quotations':['The pool is dirty.']}]
        content=json.dumps({'sentiment':sentiment,'topics':topics})
        raw={'choices':[{'message':{'content':content},'finish_reason':'stop'}], 'model':kwargs['model'], 'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}, 'offline_mock':True}
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content),finish_reason='stop')],usage=SimpleNamespace(prompt_tokens=0,completion_tokens=0,total_tokens=0),model_dump=lambda **kw:raw)


OpenAIProvider._get_client=lambda self: OfflineClient()
assert celery_app.conf.beat_schedule == {}
celery_app.worker_main(['worker','--pool=solo','--concurrency=1','--loglevel=INFO','--without-gossip','--without-mingle','--without-heartbeat'])

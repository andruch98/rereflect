"""Private review surface from API readback + the durable provider ledger."""
import argparse
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx


def grouped_analysis(result):
    """Readable grouping; never infer labels for legacy or keyword evidence."""
    def safe(value):
        # Encode punctuation too: review text cannot create Markdown or HTML.
        return ''.join(c if c.isalnum() or c == ' ' else f'&#{ord(c)};' for c in str(value))
    sections = ['**Overall sentiment:** ' + safe(result['sentiment'])]
    for index, topic in enumerate(result['topics'], 1):
        sections.append(f"**{index}. {safe(topic['name'])} — {safe(topic['sentiment'])}**")
        groups = {}
        for quotation in topic['quotations']:
            label = quotation['sentiment'] if isinstance(quotation, dict) else 'unlabeled'
            text = quotation['text'] if isinstance(quotation, dict) else quotation
            groups.setdefault(label, []).append(text)
        for label in ('positive', 'negative', 'neutral', 'unknown', 'unlabeled'):
            if label in groups:
                sections.append('**' + label.capitalize() + '**')
                sections.append('\n'.join('- ' + safe(q) for q in groups[label]))
    return '\n\n'.join(sections)


def export(manifest, items, ledger_path, destination, commit):
    records=manifest['records']
    if len(records)!=6 or len({r['source_id'] for r in records})!=6:
        raise ValueError('Manifest must contain exactly six distinct reviews')
    if not Path(ledger_path).is_file(): raise ValueError('Provider ledger is missing')
    with sqlite3.connect('file:'+str(Path(ledger_path).resolve())+'?mode=ro', uri=True) as db:
        rows=db.execute('SELECT source_id,request,attempted_at,response,error FROM attempts').fetchall()
    attempts={r[0]:{'request':json.loads(r[1]),'attempted_at':r[2], 'raw_provider_response':json.loads(r[3]) if r[3] else None,'error':r[4]} for r in rows}
    if len(attempts)>6 or set(attempts)-{r['source_id'] for r in records}:
        raise ValueError('Ledger contains requests outside this experiment')
    results=[]
    for record in records:
        outputs={}
        checks=[]
        for mode in ('ai','fallback'):
            matches=[i for i in items if i.get('source_external_id')==record['source_id'] and i['source']=='apartment_review_'+mode]
            if len(matches)!=1:
                checks.append({'check':mode+' saved record','passed':False,'reason':f'Expected one record, found {len(matches)}'})
                outputs[mode]=None
                continue
            item=matches[0]
            outputs[mode]=item
            input_equal=item['text']==record['text'] and item['star_rating']==record['star_rating']
            checks.append({'check':mode+' input readback','passed':input_equal,'reason':'Exact full text and rating comparison'})
            analysis=item.get('apartment_analysis')
            if not analysis:
                checks.append({'check':mode+' completion','passed':False,'reason':'No saved analysis'})
                continue
            audit=analysis.get('ai_attempt')
            if audit and audit.get('parsed_result') is not None:
                saved=analysis['final_result']
                equal=all(saved[k]==audit['parsed_result'][k] for k in ('sentiment','topics'))
                checks.append({'check':'parsed AI versus saved result','passed':equal,'reason':'Exact sentiment/topic/evidence comparison'})
            checks.append({'check':mode+' sentiment column','passed':item['sentiment_label']==analysis['final_result']['sentiment'],'reason':'Stored label versus saved payload'})
        results.append(dict(record,provider_attempt=attempts.get(record['source_id']),outputs=outputs,code_checks=checks,approval='',comments='',corrections=''))
    successful=sum(bool(r['outputs']['ai'] and r['outputs']['ai'].get('apartment_analysis') and r['outputs']['ai']['apartment_analysis']['final_result']['method']=='ai_model') for r in results)
    document={'experiment_commit':commit,'exported_at':datetime.now(timezone.utc).isoformat(), 'provider_requests_reserved':len(rows),
              'request_count_note':'Reservations are durable before the HTTP call; an interrupted in-flight attempt is conservatively counted.',
              'successful_ai_analyses':successful,'monetary_cost':'unavailable','source_sha256':manifest['source_sha256'],'reviews':results,
              'human_review_note':'Code checks do not establish interpretation correctness. Approval fields intentionally blank.'}
    out=Path(destination);out.mkdir(parents=True,exist_ok=False,mode=0o700)
    (out/'results.json').write_text(json.dumps(document,ensure_ascii=False,indent=2))
    sections=['# Apartment review experiment results',f'Commit: `{commit}`',f'Provider attempts reserved: {len(rows)}. Successful AI analyses: {successful}. Monetary cost: unavailable.',document['human_review_note']]
    for index,review in enumerate(results,1):
        encoded=json.dumps(review,ensure_ascii=False,indent=2)
        # Make even adversarial review Markdown inert inside the export.
        fence='`'*(max([len(x) for x in __import__('re').findall(r'`+',encoded)]+[2])+1)
        item=review['outputs']['ai']
        analysis=item.get('apartment_analysis') if item else None
        readable=grouped_analysis(analysis['final_result']) if analysis else 'No saved result.'
        sections += [f'## Review {index}',readable,'### Complete audit record',fence+'json\n'+encoded+'\n'+fence,'Approval: \n\nComments: \n\nCorrections: ']
    (out/'results.md').write_text('\n\n'.join(sections)+'\n')
    for p in out.iterdir():p.chmod(0o600)
    return document


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('api-url','manifest','ledger','output'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--organization-id',required=True,type=int)
    args=parser.parse_args()
    token=os.environ['REREFLECT_TOKEN']
    with httpx.Client(base_url=args.api_url,headers={'Authorization':'Bearer '+token},timeout=30) as client:
        response=client.get('/api/v1/feedback/',params={'page_size':1000});response.raise_for_status()
        page=response.json()
        if page['total_pages']>1: raise ValueError('Use an isolated experiment organization')
        items=page['items']
        if any(i['organization_id']!=args.organization_id for i in items): raise ValueError('Wrong organization')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    export(json.loads(Path(args.manifest).read_text()),items,args.ledger,args.output,commit)

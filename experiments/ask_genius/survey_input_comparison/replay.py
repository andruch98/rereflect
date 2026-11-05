"""Run inside the existing preview API container; stdin is a private prepared job.

No database access or app/config writes. At most four provider requests, no retries.
Use the installed adapter and validator, and retain original source records.
"""
import asyncio
import hashlib
import json
import sys

from src.services import ask_genius as service


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def preflight(job, config, error):
    if error or config is None:
        raise ValueError(error or 'Ask Genius is not configured.')
    if job.get('version') != 1 or len(job.get('cases', [])) != 4:
        raise ValueError('This test requires exactly four prepared questions.')
    if config.provider != job['provider'] or config.model != job['model']:
        raise ValueError('The configured model/provider differs from the baseline. Nothing sent.')
    prompt = service.SYSTEM_PROMPT + '\n\n' + service.RUNTIME_RULES
    if hashlib.sha256(prompt.encode()).hexdigest() != job['system_prompt_sha256']:
        raise ValueError('The installed instructions differ from the baseline. Nothing sent.')
    ids = set()
    for case in job['cases']:
        ids.add(case['message_id'])
        before = case['baseline_request']
        after = case['messages']
        if (before['provider'] != config.provider or before['model'] != config.model
                or before['max_completion_tokens'] != 1200 or before['max_retries'] != 0
                or after[0]['content'] != prompt or after[:1] != before['messages'][:1]
                or after[2:] != before['messages'][2:]):
            raise ValueError('A case changed generation settings, instructions or history. Nothing sent.')
        original = json.loads(before['messages'][1]['content'].split('\n', 1)[1])
        compact = json.loads(after[1]['content'].split('\n', 1)[1])
        if ({k: v for k, v in original.items() if k != 'surveys'} !=
                {k: v for k, v in compact.items() if k != 'surveys'}):
            raise ValueError('Evidence outside survey representation differs. Nothing sent.')
    if len(ids) != 4:
        raise ValueError('Duplicate cases. Nothing sent.')


async def run(job):
    config, error = service.configured_llm(None, None)  # This preview reads explicit env settings only.
    try:
        preflight(job, config, error)
    except ValueError as exc:
        emit({'kind': 'preflight_failure', 'reason': str(exc), 'requests_attempted': 0})
        return 1
    for index, case in enumerate(job['cases'], 1):
        emit({'kind': 'attempt', 'index': index, 'message_id': case['message_id'],
              'model': config.model, 'provider': config.provider,
              'max_completion_tokens': 1200, 'max_retries': 0, 'messages': case['messages']})
        try:
            result = await service.generate_answer(case['messages'], config)
        except Exception as exc:
            # Do not log exception text, headers, credentials or configured URLs.
            emit({'kind': 'request_failure', 'index': index, 'error_type': type(exc).__name__,
                  'http_status': getattr(exc, 'status_code', None),
                  'tokens_in': None, 'tokens_out': None, 'cost_cents': None})
            return 1
        record = {'kind': 'result', 'index': index, 'raw_response': result.raw_response,
                  'model_output': result.answer, 'tokens_in': result.tokens_in,
                  'tokens_out': result.tokens_out, 'cost_cents': None,
                  'finish_reason': result.finish_reason, 'human_assessment': 'Pending'}
        try:
            if result.finish_reason != 'stop':
                raise ValueError('Model did not finish normally: ' + str(result.finish_reason))
            original = json.loads(case['baseline_request']['messages'][1]['content'].split('\n', 1)[1])
            references, normalizations = [], []
            answer, sources = service.validate_answer(result.answer, original,
                original['evidence_requested'], survey_context=references, normalizations=normalizations)
            record.update(validation='passed', answer=answer, sources=sources,
                          survey_context=references, normalizations=normalizations)
        except ValueError as exc:
            record.update(validation='rejected', rejection_reason=str(exc))
        emit(record)
        if record['validation'] == 'rejected':
            return 1
    emit({'kind': 'complete', 'requests_attempted': 4,
          'human_assessment': 'Pending; valid references/format do not establish factual accuracy.'})
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(run(json.load(sys.stdin))))

"""Prepare four private, frozen-history comparisons from a saved Ask Genius export.

Run with the backend dependencies installed. Never commit its output: it contains
the user's original survey data and conversations. Makes no model calls.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'services/backend-api'))
from src.services import ask_genius as service


def prepare(messages, selected_ids):
    if len(selected_ids) != 4 or len(set(selected_ids)) != 4:
        raise ValueError('Select exactly four distinct user-message IDs.')
    by_id = {item['id']: item for item in messages}
    cases = []
    for message_id in selected_ids:
        user = by_id[message_id]
        audit = user['raw_request']
        original = audit['messages']
        if user['role'] != 'user' or audit['status'] != 'completed':
            raise ValueError('Each baseline must be a completed user request.')
        if audit['max_completion_tokens'] != 1200 or audit['max_retries'] != 0:
            raise ValueError('Baseline generation settings differ from this comparison.')
        context = json.loads(original[1]['content'].split('\n', 1)[1])
        compact = service.build_messages(original[-1]['content'], deepcopy(context), original[2:-1],
            expanded=context['evidence_requested'],
            default_period=context['personal_preferences']['default_period'])
        changed = json.loads(compact[1]['content'].split('\n', 1)[1])
        if compact[:1] != original[:1] or compact[2:] != original[2:]:
            raise ValueError('Prompt, history or question changed; comparison aborted.')
        if {k: v for k, v in context.items() if k != 'surveys'} != {
                k: v for k, v in changed.items() if k != 'surveys'}:
            raise ValueError('Evidence outside survey representation changed.')
        if [s['survey_id'] for s in context['surveys']] != [s['survey_id'] for s in changed['surveys']]:
            raise ValueError('Survey selection changed.')
        cases.append({'message_id': message_id, 'question': original[-1]['content'],
                      'baseline_request': audit, 'baseline_response': by_id[audit['answer_message_id']],
                      'messages': compact})
    model = cases[0]['baseline_request']['model']
    provider = cases[0]['baseline_request']['provider']
    prompt = cases[0]['messages'][0]['content']
    if any(c['baseline_request']['model'] != model or c['baseline_request']['provider'] != provider
           or c['messages'][0]['content'] != prompt for c in cases):
        raise ValueError('All cases must use the same prompt, model and provider.')
    return {'version': 1, 'model': model, 'provider': provider,
            'system_prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--message-ids', type=int, nargs=4, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(json.loads(args.export.read_text()), args.message_ids)
    with args.output.open('x') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print('Four frozen-history requests prepared. No model calls made.')
